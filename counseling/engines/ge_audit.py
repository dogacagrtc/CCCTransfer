"""
GE (General Education) Audit Engine.

This module handles auditing student progress against IGETC or Cal-GETC patterns.
"""

from ..config import CAL_GETC_START_YEAR, academic_year_to_code
from ..models import Course, AreaAuditResult
from ..data import DataLoader


class GEAuditEngine:
    """
    Audits student progress against IGETC or Cal-GETC patterns.
    
    IGETC vs Cal-GETC:
    ------------------
    - IGETC (Intersegmental General Education Transfer Curriculum):
      The traditional pattern used before Fall 2025. Has slight differences
      between UC and CSU requirements (e.g., CSU requires Area 1C oral comm,
      UC requires Area 6 Language Other Than English).
      
    - Cal-GETC (California General Education Transfer Curriculum):
      The new unified pattern starting Fall 2025. Combines UC and CSU
      requirements into a single pattern (3 courses for Area 1 for both).
    
    SCHEMA v2.0 SUPPORT:
    -------------------
    This engine works with ge_rules_master.json schema v2.0:
    - Accesses patterns via systems.IGETC or systems.CalGETC
    - Uses per_target for CSU vs UC specific requirements
    - Handles subareas as dict (keyed by subarea code)
    - Applies year_overrides for policy changes (e.g., Area 4 in 2023)
    
    MATCHING LOGIC:
    ---------------
    Courses have specific GE codes like "4H" (POL SC 1) or "5A" (physics).
    GE areas have codes like "4" or "5A". We use PREFIX MATCHING:
    - "4H" matches area "4" (4H starts with 4)
    - "5A" matches area "5" and subarea "5A"
    """
    
    def __init__(self, data_loader: DataLoader):
        self.loader = data_loader
    
    def determine_ge_pattern(self, entry_year: int, entry_term: str) -> str:
        """
        Determine which GE pattern applies based on entry date.
        
        Cal-GETC became effective Fall 2025. Students who started before
        that date use IGETC; students starting Fall 2025 or later use Cal-GETC.
        
        Args:
            entry_year: Year student first enrolled at SMC
            entry_term: Term of first enrollment (Fall, Spring, Summer, Winter)
        
        Returns:
            "IGETC" or "CalGETC" (matching keys in ge_rules_master.json systems)
        """
        if entry_year > CAL_GETC_START_YEAR:
            return "CalGETC"
        elif entry_year == CAL_GETC_START_YEAR:
            # Fall 2025 and later = Cal-GETC
            if entry_term.lower() in ["fall", "winter"]:
                return "CalGETC"
        return "IGETC"
    
    def _get_year_code(self, entry_year: int) -> int:
        """Convert entry year to year code (e.g., 2023 -> 74)."""
        return academic_year_to_code(entry_year)
    
    def _apply_year_overrides(self, pattern: dict, year_code: int) -> dict:
        """
        Apply year-specific overrides to pattern areas.
        
        The ge_rules_master.json has year_overrides that modify area requirements
        based on which academic year the student started.
        """
        year_overrides = pattern.get("year_overrides", [])
        
        # Find applicable override
        for override in year_overrides:
            year_min = override.get("year_id_min", 0)
            year_max = override.get("year_id_max", 999)
            
            if year_min <= year_code <= year_max:
                # Apply overrides to areas
                override_areas = override.get("areas", {})
                for area_code, area_override in override_areas.items():
                    if area_code in pattern.get("areas", {}):
                        # Merge override into existing area
                        original = pattern["areas"][area_code]
                        if "per_target" in area_override:
                            original["per_target"] = area_override["per_target"]
                        if area_override.get("disabled"):
                            original["disabled"] = True
                break  # Only apply first matching override
        
        return pattern
    
    def audit(self, student_state: dict, entry_year: int, entry_term: str, 
              target_system: str = "csu") -> dict:
        """
        Perform full GE audit against IGETC or Cal-GETC.
        
        Args:
            student_state: Parsed transcript data from TranscriptParser
            entry_year: Year student started at community college
            entry_term: Semester (Fall, Spring, Summer, Winter)
            target_system: "csu" or "uc" (affects Area 1 requirements)
        
        Returns:
            {
                "pattern_name": "IGETC for UC and CSU",
                "pattern_key": "IGETC",
                "areas": [AreaAuditResult, ...],
                "overall_satisfied": bool,
                "total_units_completed": float,
            }
        """
        pattern_key = self.determine_ge_pattern(entry_year, entry_term)
        
        # NEW SCHEMA: Access via systems key
        systems = self.loader.ge_rules.get("systems", {})
        pattern = systems.get(pattern_key, {})
        
        # Apply year-specific overrides
        year_code = self._get_year_code(entry_year)
        pattern = self._apply_year_overrides(pattern, year_code)
        
        completed = student_state["completed"]
        in_progress = student_state["in_progress"]
        
        # Select the correct Course attribute key based on pattern
        ge_attr_key = "igetc" if pattern_key == "IGETC" else "cal_getc"
        
        # Convert target_system to uppercase for matching per_target keys
        target_key = target_system.upper()  # "csu" -> "CSU"
        
        # Audit each GE area
        area_results = []
        areas_dict = pattern.get("areas", {})
        
        for area_code, area_data in areas_dict.items():
            # Skip disabled areas
            if area_data.get("disabled"):
                continue
            
            result = self._audit_area_v2(
                area_code, area_data, completed, in_progress, 
                ge_attr_key, target_key, year_code
            )
            area_results.append(result)
        
        # Sort areas by code for consistent display
        area_results.sort(key=lambda x: x.code)
        
        # Check overall satisfaction
        overall_satisfied = all(r.is_satisfied for r in area_results)
        
        # Calculate total units from completed GE courses
        ge_courses = set()
        for r in area_results:
            for c in r.completed_courses:
                ge_courses.add(c.code)
        total_units = sum(c.units for c in completed if c.code in ge_courses)
        
        return {
            "pattern_name": pattern.get("pattern_name", pattern_key),
            "pattern_key": pattern_key,
            "areas": area_results,
            "overall_satisfied": overall_satisfied,
            "total_units_completed": total_units,
        }
    
    def _course_matches_area(self, course: Course, area_code: str, ge_attr_key: str) -> bool:
        """
        Check if a course satisfies a GE area code.
        
        MATCHING LOGIC:
        - Exact match: "2A" == "2A" ✓
        - Prefix match for single-digit areas: "4H" starts with "4" ✓
        """
        course_codes = getattr(course, ge_attr_key, [])
        for cc in course_codes:
            # Exact match (handles subareas like "1A", "5C")
            if cc == area_code:
                return True
            # Prefix match for single-digit area codes
            if cc.startswith(area_code) and len(area_code) == 1:
                return True
        return False
    
    def _audit_area_v2(self, area_code: str, area_data: dict, completed: list, 
                       in_progress: list, ge_attr_key: str, target_key: str,
                       year_code: int) -> AreaAuditResult:
        """
        Audit a single GE area using the NEW schema structure (v2.0).
        """
        name = area_data.get("name", "")
        description = area_data.get("description", "")
        
        # Get target-specific requirements
        per_target = area_data.get("per_target", {})
        target_reqs = per_target.get(target_key, {})
        
        # Check if this area is required for this target
        if target_reqs.get("required") == False:
            return AreaAuditResult(
                code=area_code,
                name=name,
                required_courses=0,
                required_units=0,
                completed_courses=[],
                pending_courses=[],
                is_satisfied=True,
                notes=f"Not required for {target_key}",
            )
        
        min_courses = target_reqs.get("min_courses", 1)
        min_units = target_reqs.get("min_units_semester", 3)
        required_subareas = target_reqs.get("required_subareas", [])
        constraints = target_reqs.get("constraints", {})
        
        # Get subareas (dict in new schema)
        subareas_dict = area_data.get("subareas", {})
        
        # If area has required subareas, audit each one
        if required_subareas or subareas_dict:
            return self._audit_area_with_subareas_v2(
                area_code, name, description, subareas_dict, 
                min_courses, min_units, required_subareas, constraints,
                completed, in_progress, ge_attr_key
            )
        
        # Simple area - find courses that match
        matching_completed = [c for c in completed if self._course_matches_area(c, area_code, ge_attr_key)]
        matching_pending = [c for c in in_progress if self._course_matches_area(c, area_code, ge_attr_key)]
        
        is_satisfied = len(matching_completed) >= min_courses
        
        return AreaAuditResult(
            code=area_code,
            name=name,
            required_courses=min_courses,
            required_units=min_units,
            completed_courses=matching_completed,
            pending_courses=matching_pending,
            is_satisfied=is_satisfied,
            notes=description,
        )
    
    def _audit_area_with_subareas_v2(self, area_code: str, area_name: str, 
                                      description: str, subareas_dict: dict,
                                      min_courses: int, min_units: float,
                                      required_subareas: list, constraints: dict,
                                      completed: list, in_progress: list,
                                      ge_attr_key: str) -> AreaAuditResult:
        """
        Audit an area with subareas using the NEW schema (v2.0).
        """
        subarea_results = []
        all_completed = []
        all_pending = []
        
        # Determine which subareas need to be checked
        subareas_to_check = required_subareas if required_subareas else list(subareas_dict.keys())
        
        # Check constraints
        require_one_each = constraints.get("require_one_each_from", [])
        if require_one_each:
            subareas_to_check = require_one_each
        
        require_subareas = constraints.get("require_subareas", [])
        if require_subareas:
            subareas_to_check = require_subareas
        
        for sub_code in subareas_to_check:
            sub_info = subareas_dict.get(sub_code, {})
            sub_name = sub_info.get("name", sub_code)
            sub_min = sub_info.get("min_courses", 1)
            
            matching_completed = [c for c in completed if self._course_matches_area(c, sub_code, ge_attr_key)]
            matching_pending = [c for c in in_progress if self._course_matches_area(c, sub_code, ge_attr_key)]
            
            sub_satisfied = len(matching_completed) >= sub_min
            
            subarea_results.append({
                "code": sub_code,
                "name": sub_name,
                "required": sub_min,
                "completed": matching_completed,
                "pending": matching_pending,
                "satisfied": sub_satisfied,
            })
            
            all_completed.extend(matching_completed)
            all_pending.extend(matching_pending)
        
        # Check lab requirement if specified
        lab_satisfied = True
        if constraints.get("require_at_least_one_lab"):
            lab_code = "5C"  # Standard lab subarea code
            lab_courses = [c for c in completed if self._course_matches_area(c, lab_code, ge_attr_key)]
            lab_satisfied = len(lab_courses) >= 1
            
            if not lab_satisfied:
                subarea_results.append({
                    "code": lab_code,
                    "name": "Laboratory",
                    "required": 1,
                    "completed": lab_courses,
                    "pending": [],
                    "satisfied": False,
                })
        
        # De-duplicate courses
        seen_codes = set()
        unique_completed = []
        for c in all_completed:
            if c.code not in seen_codes:
                unique_completed.append(c)
                seen_codes.add(c.code)
        
        seen_codes = set()
        unique_pending = []
        for c in all_pending:
            if c.code not in seen_codes:
                unique_pending.append(c)
                seen_codes.add(c.code)
        
        # Check satisfaction
        all_subs_satisfied = all(s["satisfied"] for s in subarea_results)
        total_courses = len(unique_completed)
        total_units = sum(c.units for c in unique_completed)
        
        is_satisfied = (all_subs_satisfied and 
                       total_courses >= min_courses and 
                       total_units >= min_units and
                       lab_satisfied)
        
        # Build subarea status notes
        sub_notes_parts = []
        for s in subarea_results:
            status = "✓" if s["satisfied"] else "✗"
            sub_notes_parts.append(f"{s['code']} ({s['name']}): {status}")
        sub_notes = " | ".join(sub_notes_parts)
        
        return AreaAuditResult(
            code=area_code,
            name=area_name,
            required_courses=min_courses,
            required_units=min_units,
            completed_courses=unique_completed,
            pending_courses=unique_pending,
            is_satisfied=is_satisfied,
            notes=f"Subareas: {sub_notes}" if sub_notes else description,
        )

