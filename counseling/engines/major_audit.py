"""
Major Requirements Audit Engine.

This module handles auditing student progress against major-specific
articulation requirements.
"""

from typing import Optional

from ..models import RequirementAuditResult
from ..data import DataLoader


class MajorAuditEngine:
    """
    Audits student progress against major-specific articulation requirements.
    
    ARTICULATION EXPLAINED:
    ----------------------
    Each California university has agreements with community colleges defining
    which CC courses satisfy their degree requirements. These are maintained
    on Assist.org and we have scraped/processed them into clean JSON.
    
    The articulation data structure:
    - University course (e.g., CSULB's "CECS 274 - Data Structures")
    - SMC options (e.g., [["CS 20A"], ["CS 20B"]] - take either one)
    - Some university courses have "No Articulation" = no SMC equivalent
    
    REQUIREMENT LOGIC TYPES:
    -----------------------
    ALL_OF: Complete every item in the list
            Example: "Complete CECS 174 AND CECS 274 AND MATH 122"
            
    ONE_OF: Complete any one item from the list
            Example: "Take CS 87A OR CS 52 OR CS 55"
            
    N_OF:   Complete at least N items from the list
            Example: "Choose 2 electives from: [list of 5 options]"
    """
    
    def __init__(self, data_loader: DataLoader):
        self.loader = data_loader
    
    def find_major(self, university_name: str, major_name: str) -> Optional[dict]:
        """
        Find a specific major in the articulation data.
        
        Uses case-insensitive matching for user convenience.
        """
        try:
            data = self.loader.load_major_articulation(university_name)
        except FileNotFoundError:
            return None
        
        # Handle both list format and dict format
        majors = data.get("majors", data) if isinstance(data, dict) else data
        
        if isinstance(majors, list):
            for m in majors:
                if m.get("major", "").lower() == major_name.lower():
                    return m
        return None
    
    def list_majors(self, university_name: str) -> list:
        """List all available majors for a university."""
        try:
            data = self.loader.load_major_articulation(university_name)
        except FileNotFoundError:
            return []
        
        majors = data.get("majors", data) if isinstance(data, dict) else data
        
        if isinstance(majors, list):
            return sorted(set(m.get("major", "") for m in majors if m.get("major")))
        return []
    
    def audit(self, student_state: dict, university_name: str, major_name: str) -> dict:
        """
        Audit student against major-specific requirements.
        
        This is the main entry point for major auditing. It finds the major,
        then checks each requirement group against the student's courses.
        
        Returns:
            {
                "major": "Computer Science",
                "university": "California State University Long Beach",
                "requirements": [RequirementAuditResult, ...],
                "overall_satisfied": bool,
                "completion_percentage": float,
                "satisfied_count": int,
                "pending_count": int,
                "total_count": int,
                "general_notes": [...],
            }
        """
        major_data = self.find_major(university_name, major_name)
        if not major_data:
            return {
                "error": f"Major '{major_name}' not found at '{university_name}'",
                "available_majors": self.list_majors(university_name)[:10],
            }
        
        completed = student_state["completed"]
        in_progress = student_state["in_progress"]
        
        # Build quick lookup sets for O(1) course checking
        completed_codes = {c.code for c in completed}
        pending_codes = {c.code for c in in_progress}
        
        requirements = major_data.get("requirements", [])
        requirement_results = []
        
        for req in requirements:
            result = self._audit_requirement(req, completed_codes, pending_codes, completed, in_progress)
            requirement_results.append(result)
        
        # Calculate overall status
        total_reqs = len(requirement_results)
        satisfied_reqs = sum(1 for r in requirement_results if r.is_satisfied)
        pending_reqs = sum(1 for r in requirement_results if r.is_pending and not r.is_satisfied)
        
        overall_satisfied = all(r.is_satisfied for r in requirement_results)
        completion_pct = (satisfied_reqs / total_reqs * 100) if total_reqs > 0 else 0
        
        return {
            "major": major_data.get("major", major_name),
            "university": major_data.get("university", {}).get("names", [{}])[0].get("name", university_name),
            "requirements": requirement_results,
            "overall_satisfied": overall_satisfied,
            "completion_percentage": completion_pct,
            "satisfied_count": satisfied_reqs,
            "pending_count": pending_reqs,
            "total_count": total_reqs,
            "general_notes": major_data.get("general_texts", []),
        }
    
    def _audit_requirement(self, req: dict, completed_codes: set, pending_codes: set,
                           completed: list, in_progress: list) -> RequirementAuditResult:
        """
        Audit a single requirement group.
        
        OPTION GROUP LOGIC:
        ------------------
        smc_options is a list of "option groups". Each option group is a list
        of courses that together satisfy the requirement.
        """
        req_id = req.get("id", "unknown")
        rule = req.get("rule", {})
        logic = rule.get("logic", "ALL_OF")
        items = req.get("items", [])
        
        min_count = rule.get("min_count")
        max_count = rule.get("max_count")
        
        satisfied_items = []
        pending_items = []
        missing_items = []
        
        for item in items:
            if item.get("type") == "COURSE":
                smc_options = item.get("smc_options", [])
                uni_course = item.get("university_course", {})
                articulation_type = item.get("articulation_type", "")
                
                # Check if student has any of the SMC options
                found_completed = False
                found_pending = False
                matched_course = None
                
                for option_group in smc_options:
                    group_codes = [c.get("code", "") for c in option_group]
                    
                    # Check if ALL courses in this option are completed
                    if all(code in completed_codes for code in group_codes):
                        found_completed = True
                        matched_course = group_codes
                        break
                    
                    # Check if ALL are at least in progress or completed
                    elif all(code in completed_codes or code in pending_codes for code in group_codes):
                        if any(code in pending_codes for code in group_codes):
                            found_pending = True
                            matched_course = group_codes
                
                # Categorize this item
                if found_completed:
                    satisfied_items.append({
                        "university_course": uni_course,
                        "satisfied_by": matched_course,
                        "status": "completed",
                    })
                elif found_pending:
                    pending_items.append({
                        "university_course": uni_course,
                        "pending_courses": matched_course,
                        "status": "pending",
                    })
                else:
                    missing_items.append({
                        "university_course": uni_course,
                        "smc_options": smc_options,
                        "articulation_type": articulation_type,
                        "status": "missing",
                    })
        
        # DETERMINE SATISFACTION based on logic type
        # 
        # IMPORTANT: Empty items list handling
        # ------------------------------------
        # If a requirement has no items but expects courses (min_count > 0),
        # it should NOT be satisfied. This usually indicates incomplete
        # articulation data from Assist.org.
        #
        if logic == "ALL_OF":
            # ALL_OF with no items = trivially satisfied (nothing to do)
            # ALL_OF with items = need all items completed
            is_satisfied = len(missing_items) == 0 and len(pending_items) == 0
            is_pending = len(missing_items) == 0 and len(pending_items) > 0
        elif logic == "ONE_OF":
            # ONE_OF requires at least 1 item to be satisfied
            is_satisfied = len(satisfied_items) >= 1
            is_pending = not is_satisfied and len(pending_items) >= 1
        elif logic in ("N_OF", "CHOOSE_N", "AT_LEAST_N"):
            # These are all "choose at least N" type requirements
            # FIX: Added CHOOSE_N and AT_LEAST_N which were falling through
            required = min_count if min_count is not None else 1
            
            # CRITICAL: If there are no items but we require some, it's NOT satisfied
            # This handles cases where articulation data is incomplete
            if len(items) == 0 and required > 0:
                is_satisfied = False
                is_pending = False
            else:
                is_satisfied = len(satisfied_items) >= required
                is_pending = not is_satisfied and (len(satisfied_items) + len(pending_items)) >= required
        else:
            # Default fallback for unknown logic types
            is_satisfied = len(missing_items) == 0 and len(pending_items) == 0
            is_pending = len(missing_items) == 0 and len(pending_items) > 0
        
        return RequirementAuditResult(
            requirement_id=req_id,
            logic=logic,
            min_required=min_count,
            items={
                "satisfied": satisfied_items,
                "pending": pending_items,
                "missing": missing_items,
            },
            satisfied_by=[s["satisfied_by"] for s in satisfied_items],
            pending=[p["pending_courses"] for p in pending_items],
            is_satisfied=is_satisfied,
            is_pending=is_pending,
        )

