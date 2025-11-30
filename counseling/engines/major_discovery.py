"""
Major Discovery Engine.

This module provides a "reverse lookup" feature that helps students discover
which majors they are closest to completing based on their current courses.

USE CASE:
---------
A student with many completed courses wants to know:
"Which majors am I closest to completing? What opportunities might I be missing?"

Instead of the student picking a major first, this engine:
1. Loads ALL majors from ALL universities
2. Checks the student's courses against each major's requirements
3. Scores each major by completion percentage
4. Returns the top N best matches

SCORING FORMULA:
----------------
score = (satisfied_count + 0.5 * in_progress_count) / total_requirements

- Satisfied requirements get full credit (1.0)
- In-progress courses get half credit (0.5) 
- Score is normalized to 0-100% for fair comparison
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import json

from ..data import DataLoader
from ..models import Course
from ..config import DATA_DIR


# ============================================================================
#  DATA STRUCTURES
# ============================================================================

@dataclass
class MajorMatch:
    """
    Represents a single major match result.
    
    Contains all the information needed to display and rank this major
    in the discovery results.
    
    RANKING PHILOSOPHY:
    -------------------
    We prioritize PERCENTAGE COMPLETION because it shows how close to done:
    - 3+1/6 (67%) is BETTER than 5+3/18 (44%) - closer to finishing
    - 5/10 (50%) beats 2/4 (50%) as tiebreaker - more work invested
    
    Small majors (1-2 requirements) are pushed to the END of the list:
    - They might be minors or have incomplete articulation data
    - A 1/1 (100%) shouldn't dominate over 5/6 (83%) in rankings
    - They're still shown, just at the bottom
    
    The ranking uses:
    1. Primary: Is it substantial? (≥3 requirements) - real majors first
    2. Secondary: Percentage completion (how close to done)
    3. Tertiary: Absolute progress (tiebreaker for same %)
    """
    university: str           # e.g., "University of California Los Angeles"
    major: str               # e.g., "Computer Science/B.S."
    
    # Requirement counts
    total_requirements: int   # Total number of requirement groups
    satisfied_count: int      # Fully satisfied by completed courses
    in_progress_count: int    # Will be satisfied when in-progress complete
    missing_count: int        # Still need courses for these
    
    # Calculated scores
    score: float              # Percentage-based (0.0 to 1.0) for display
    weighted_score: float     # Weighted score for ranking (absolute progress)
    
    # For display: what's still needed
    missing_courses: List[str]  # e.g., ["MATH 13", "PHYSCS 22"]
    
    @property
    def percentage(self) -> float:
        """Score as a percentage (0-100)."""
        return self.score * 100
    
    @property
    def display_progress(self) -> str:
        """Human-readable progress string."""
        return f"{self.satisfied_count}/{self.total_requirements}"
    
    @property
    def effective_satisfied(self) -> float:
        """Satisfied count with full credit for in-progress."""
        return self.satisfied_count + self.in_progress_count


# ============================================================================
#  MAJOR DISCOVERY ENGINE
# ============================================================================

class MajorDiscoveryEngine:
    """
    Discovers which majors a student is closest to completing.
    
    This engine scans ALL available majors across ALL universities and
    ranks them by how many requirements the student has already satisfied.
    
    USAGE:
    ------
    engine = MajorDiscoveryEngine(data_loader)
    matches = engine.discover(student_courses, top_n=10)
    
    for match in matches:
        print(f"{match.university} - {match.major}: {match.percentage:.0f}%")
    """
    
    # In-progress courses count as full courses for scoring
    # (they WILL be completed, so count them fully)
    IN_PROGRESS_WEIGHT = 1.0
    
    # Threshold for "substantial" majors vs small/trivial ones
    # Majors with fewer requirements are ranked at the END (not filtered out)
    # This prevents 1/1 (100%) from dominating over 5/6 (83%)
    SUBSTANTIAL_THRESHOLD = 3
    
    def __init__(self, data_loader: DataLoader):
        """
        Initialize with a DataLoader for accessing articulation files.
        
        Args:
            data_loader: Configured DataLoader instance
        """
        self.loader = data_loader
    
    def discover(
        self, 
        completed_courses: List[Course], 
        in_progress_courses: List[Course],
        top_n: int = 10,
        min_satisfied: int = 1
    ) -> List[MajorMatch]:
        """
        Find the top N majors that best match the student's courses.
        
        Args:
            completed_courses: List of completed Course objects
            in_progress_courses: List of in-progress Course objects
            top_n: Number of top matches to return (default 10)
            min_satisfied: Minimum satisfied requirements to include (default 1)
        
        Returns:
            List of MajorMatch objects, sorted by score (highest first)
        """
        # Build lookup sets for O(1) course checking
        completed_codes = {c.code for c in completed_courses}
        pending_codes = {c.code for c in in_progress_courses}
        
        # Collect all matches
        all_matches: List[MajorMatch] = []
        
        # Get all available university files
        universities = self._get_all_universities()
        
        for uni_name in universities:
            try:
                # Load the articulation data for this university
                uni_data = self.loader.load_major_articulation(uni_name)
                majors = uni_data.get("majors", [])
                
                for major_data in majors:
                    match = self._score_major(
                        uni_name, 
                        major_data, 
                        completed_codes, 
                        pending_codes
                    )
                    
                    # Only include if meets minimum threshold
                    if match and match.satisfied_count >= min_satisfied:
                        all_matches.append(match)
                        
            except Exception as e:
                # Skip universities with data issues
                continue
        
        # SEPARATE substantial majors from small majors
        # Small majors (1-2 requirements) are shown in a separate section
        # This prevents them from being hidden when there are many substantial majors
        substantial = [m for m in all_matches if m.total_requirements >= self.SUBSTANTIAL_THRESHOLD]
        small = [m for m in all_matches if m.total_requirements < self.SUBSTANTIAL_THRESHOLD]
        
        # RANKING STRATEGY for substantial majors:
        # -----------------
        # 1. Primary: percentage (how close to completing the major)
        #    - 3+1/6 (67%) is BETTER than 5+3/18 (44%) because it's closer to done
        # 2. Secondary: absolute progress (for same %, more reqs done = more work invested)
        #    - 5/10 (50%) is better than 2/4 (50%) because more requirements satisfied
        substantial.sort(
            key=lambda m: (m.score, m.weighted_score),
            reverse=True
        )
        
        # Same ranking for small majors
        small.sort(
            key=lambda m: (m.score, m.weighted_score),
            reverse=True
        )
        
        # Return both lists: substantial majors first, then small majors
        # The UI will display them in separate sections
        return {
            "substantial": substantial[:top_n],
            "small": small[:20]  # Show up to 20 small majors
        }
    
    def _get_all_universities(self) -> List[str]:
        """
        Get a list of all universities with articulation data.
        
        Returns:
            List of university names that have clean_majors files
        """
        clean_majors_dir = DATA_DIR / "clean_majors"
        
        if not clean_majors_dir.exists():
            return []
        
        universities = []
        for file in clean_majors_dir.glob("SMC_to_*_clean.json"):
            # Extract university name from filename
            # "SMC_to_University of California Los Angeles_clean.json"
            # -> "University of California Los Angeles"
            name = file.stem  # Remove .json
            name = name.replace("SMC_to_", "").replace("_clean", "")
            universities.append(name)
        
        return universities
    
    def _score_major(
        self,
        uni_name: str,
        major_data: Dict[str, Any],
        completed_codes: set,
        pending_codes: set
    ) -> Optional[MajorMatch]:
        """
        Score a single major based on requirement satisfaction.
        
        SCORING LOGIC:
        --------------
        For each requirement group, we check if it's satisfied:
        - ALL_OF: All items must be satisfied
        - ONE_OF: At least one item must be satisfied
        - CHOOSE_N: At least N items must be satisfied
        
        We count:
        - Fully satisfied (all needed courses completed)
        - In-progress (will be satisfied when pending courses complete)
        - Missing (still need to take courses)
        
        Args:
            uni_name: University name
            major_data: Major data from clean_majors file
            completed_codes: Set of completed course codes
            pending_codes: Set of in-progress course codes
        
        Returns:
            MajorMatch object or None if major has no requirements
        """
        major_name = major_data.get("major", "Unknown")
        requirements = major_data.get("requirements", [])
        
        # Skip majors with no requirements
        if not requirements:
            return None
        
        satisfied = 0
        in_progress = 0
        missing = 0
        missing_courses = []
        
        for req in requirements:
            items = req.get("items", [])
            rule = req.get("rule", {})
            logic = rule.get("logic", "ALL_OF")
            
            # Skip empty requirement groups
            if not items:
                continue
            
            # Check this requirement group
            req_status = self._check_requirement(
                items, logic, rule, completed_codes, pending_codes
            )
            
            if req_status["satisfied"]:
                satisfied += 1
            elif req_status["in_progress"]:
                in_progress += 1
            else:
                missing += 1
                # Add first missing course to the list (for display)
                if req_status["missing_course"]:
                    missing_courses.append(req_status["missing_course"])
        
        total = satisfied + in_progress + missing
        
        # Skip if no countable requirements
        if total == 0:
            return None
        
        # Calculate percentage score (for display)
        score = (satisfied + self.IN_PROGRESS_WEIGHT * in_progress) / total
        
        # Calculate weighted score (for ranking)
        # This prioritizes absolute progress over percentage
        # A major with 5/6 (83%) will rank higher than 1/1 (100%)
        weighted_score = satisfied + self.IN_PROGRESS_WEIGHT * in_progress
        
        return MajorMatch(
            university=uni_name,
            major=major_name,
            total_requirements=total,
            satisfied_count=satisfied,
            in_progress_count=in_progress,
            missing_count=missing,
            score=score,
            weighted_score=weighted_score,
            missing_courses=missing_courses[:3]  # Limit to first 3
        )
    
    def _check_requirement(
        self,
        items: List[Dict],
        logic: str,
        rule: Dict,
        completed_codes: set,
        pending_codes: set
    ) -> Dict[str, Any]:
        """
        Check if a single requirement group is satisfied.
        
        Args:
            items: List of course items in this requirement
            logic: "ALL_OF", "ONE_OF", "CHOOSE_N", etc.
            rule: Full rule dict with min_count, etc.
            completed_codes: Set of completed course codes
            pending_codes: Set of in-progress course codes
        
        Returns:
            Dict with keys: satisfied, in_progress, missing_course
        """
        satisfied_items = 0
        pending_items = 0
        first_missing = None
        
        for item in items:
            if item.get("type") != "COURSE":
                continue
            
            smc_options = item.get("smc_options", [])
            uni_course = item.get("university_course", {})
            
            # Check if any SMC option is completed or in-progress
            item_completed = False
            item_pending = False
            
            for option_group in smc_options:
                group_codes = [c.get("code", "") for c in option_group]
                
                # Check if ALL courses in this option are completed
                if all(code in completed_codes for code in group_codes):
                    item_completed = True
                    break
                
                # Check if ALL are at least in progress or completed
                if all(code in completed_codes or code in pending_codes 
                       for code in group_codes):
                    if any(code in pending_codes for code in group_codes):
                        item_pending = True
            
            if item_completed:
                satisfied_items += 1
            elif item_pending:
                pending_items += 1
            else:
                # Track first missing course for display
                if first_missing is None:
                    if smc_options:
                        first_missing = smc_options[0][0].get("code", "")
                    else:
                        first_missing = uni_course.get("code", "Unknown")
        
        # Determine requirement satisfaction based on logic
        min_count = rule.get("min_count") or 1
        
        if logic == "ALL_OF":
            # All items must be satisfied
            is_satisfied = (satisfied_items == len(items))
            is_pending = (satisfied_items + pending_items == len(items)) and pending_items > 0
        elif logic == "ONE_OF":
            # At least one item satisfied
            is_satisfied = satisfied_items >= 1
            is_pending = not is_satisfied and pending_items >= 1
        elif logic in ("CHOOSE_N", "N_OF", "AT_LEAST_N"):
            # At least N items satisfied
            is_satisfied = satisfied_items >= min_count
            is_pending = not is_satisfied and (satisfied_items + pending_items) >= min_count
        else:
            # Default: treat like ALL_OF
            is_satisfied = (satisfied_items == len(items))
            is_pending = (satisfied_items + pending_items == len(items)) and pending_items > 0
        
        return {
            "satisfied": is_satisfied,
            "in_progress": is_pending and not is_satisfied,
            "missing_course": first_missing if not is_satisfied and not is_pending else None
        }

