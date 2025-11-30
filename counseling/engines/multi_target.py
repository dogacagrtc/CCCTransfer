"""
Multi-Target Analysis Engine.

This module handles analyzing course efficiency across MULTIPLE university/major
targets simultaneously.
"""

from ..models import (
    TargetDefinition,
    TargetAuditResult,
    MultiTargetCourse,
    MultiTargetAnalysis,
)
from ..data import DataLoader
from .ge_audit import GEAuditEngine
from .major_audit import MajorAuditEngine
from .recommendation import CourseRecommendationEngine


class MultiTargetEngine:
    """
    Analyzes course efficiency across MULTIPLE university/major targets.
    
    ═══════════════════════════════════════════════════════════════════════════
    PURPOSE
    ═══════════════════════════════════════════════════════════════════════════
    
    When a student is applying to multiple universities (e.g., CSULB, CSUN, UCLA),
    this engine finds the MOST EFFICIENT courses by cross-referencing:
    
    1. GE requirements (which may differ between CSU and UC)
    2. Major requirements at EACH university
    
    The result is a ranked list showing which courses help with the most targets.
    
    ═══════════════════════════════════════════════════════════════════════════
    EXAMPLE SCENARIO
    ═══════════════════════════════════════════════════════════════════════════
    
    Student targets:
    - CSULB Computer Science (CSU - uses IGETC)
    - CSUN Computer Science (CSU - uses IGETC)
    - UCLA Computer Science (UC - uses IGETC but with UC-specific requirements)
    
    Analysis finds:
    - BIOL 3 satisfies IGETC 5B + CSULB BIOL 200 + CSUN BIOL 101 = efficiency 3
    - MATH 13 satisfies CSULB CECS 229 + CSUN COMP 310 = efficiency 2
    
    ═══════════════════════════════════════════════════════════════════════════
    """
    
    def __init__(self, data_loader: DataLoader, ge_engine: GEAuditEngine, 
                 major_engine: MajorAuditEngine, rec_engine: CourseRecommendationEngine):
        self.loader = data_loader
        self.ge_engine = ge_engine
        self.major_engine = major_engine
        self.rec_engine = rec_engine
    
    def analyze_targets(self, targets: list, student_state: dict, 
                        entry_year: int, entry_term: str, year_code: int) -> MultiTargetAnalysis:
        """
        Perform complete analysis across all student targets.
        
        Args:
            targets: List of TargetDefinition objects
            student_state: Parsed transcript with completed/in-progress courses
            entry_year: Year student started at community college
            entry_term: Term of first enrollment
            year_code: Academic year code for GE lookups
        
        Returns:
            MultiTargetAnalysis with complete cross-referenced results
        """
        # STEP 1: Run individual audits for each target
        target_audits = []
        
        for target in targets:
            audit_result = self._audit_single_target(
                target, student_state, entry_year, entry_term, year_code
            )
            target_audits.append(audit_result)
        
        # STEP 2: Build unified course analysis across all targets
        all_courses = self._build_unified_course_list(
            target_audits, student_state, year_code
        )
        
        # STEP 3: Categorize courses by efficiency level
        super_efficient = []
        single_target = []
        ge_only = []
        
        for course in all_courses:
            if course.total_targets_helped >= 2:
                super_efficient.append(course)
            elif course.total_targets_helped == 1:
                single_target.append(course)
            elif course.total_ge_areas > 0:
                ge_only.append(course)
        
        # STEP 4: Calculate summary statistics
        all_missing_ge = set()
        total_missing_major = 0
        unique_patterns = set()
        
        for audit in target_audits:
            all_missing_ge.update(audit.missing_ge_areas)
            total_missing_major += len(audit.missing_major_reqs)
            unique_patterns.add(audit.ge_pattern)
        
        return MultiTargetAnalysis(
            targets=targets,
            target_audits=target_audits,
            all_courses=all_courses,
            super_efficient=super_efficient,
            single_target_efficient=single_target,
            ge_only=ge_only,
            total_missing_ge_areas=len(all_missing_ge),
            total_missing_major_reqs=total_missing_major,
            unique_ge_patterns=list(unique_patterns),
        )
    
    def _audit_single_target(self, target: TargetDefinition, student_state: dict,
                             entry_year: int, entry_term: str, year_code: int) -> TargetAuditResult:
        """Run complete audit for a single university/major target."""
        # Run GE audit
        ge_audit = self.ge_engine.audit(
            student_state, entry_year, entry_term, target.target_system
        )
        ge_pattern = ge_audit.get("pattern_key", "IGETC")
        
        # Run major audit
        major_audit = self.major_engine.audit(
            student_state, target.university, target.major
        )
        
        # Run cross-reference for this single target
        cross_ref = self.rec_engine.cross_reference_ge_and_major(
            ge_audit, major_audit, student_state, year_code
        )
        
        # Extract missing areas/requirements
        missing_ge = self._extract_missing_ge_areas(ge_audit)
        missing_major = self._extract_missing_major_reqs(major_audit)
        
        return TargetAuditResult(
            target=target,
            ge_pattern=ge_pattern,
            ge_audit=ge_audit,
            major_audit=major_audit,
            cross_reference=cross_ref,
            missing_ge_areas=missing_ge,
            missing_major_reqs=missing_major,
        )
    
    def _extract_missing_ge_areas(self, ge_audit: dict) -> list:
        """Extract list of missing GE area codes from audit result."""
        missing = []
        for area in ge_audit.get("areas", []):
            if not area.is_satisfied:
                if "Subareas:" in area.notes:
                    subarea_info = area.notes.split("Subareas:")[1].strip()
                    for part in subarea_info.split(" | "):
                        if "✗" in part:
                            code = part.split(" ")[0].strip()
                            missing.append(code)
                else:
                    missing.append(area.code)
        return missing
    
    def _extract_missing_major_reqs(self, major_audit: dict) -> list:
        """Extract list of missing major requirement descriptions."""
        if "error" in major_audit:
            return []
        
        missing = []
        for req in major_audit.get("requirements", []):
            if not req.is_satisfied:
                for item in req.items.get("missing", []):
                    uni_course = item.get("university_course", {})
                    code = uni_course.get("code", "")
                    title = uni_course.get("title", "")
                    missing.append(f"{code}: {title}" if title else code)
        return missing
    
    def _build_unified_course_list(self, target_audits: list, 
                                    student_state: dict, year_code: int) -> list:
        """Build a unified list of ALL courses that help with ANY target."""
        completed_codes = {c.code for c in student_state["completed"]}
        pending_codes = {c.code for c in student_state["in_progress"]}
        all_student_codes = completed_codes | pending_codes
        
        # Collect all missing GE areas (by pattern)
        missing_ge_by_pattern = {}
        
        for audit in target_audits:
            pattern = audit.ge_pattern
            if pattern not in missing_ge_by_pattern:
                missing_ge_by_pattern[pattern] = set()
            missing_ge_by_pattern[pattern].update(audit.missing_ge_areas)
        
        # Collect all SMC course options from major requirements
        major_course_map = {}
        
        for audit in target_audits:
            target_id = audit.target.target_id
            major_audit = audit.major_audit
            
            if "error" in major_audit:
                continue
            
            for req in major_audit.get("requirements", []):
                if req.is_satisfied:
                    continue
                
                for item in req.items.get("missing", []):
                    uni_course = item.get("university_course", {})
                    smc_options = item.get("smc_options", [])
                    articulation_type = item.get("articulation_type", "")
                    
                    if not smc_options or articulation_type == "NO_ARTICULATION":
                        continue
                    
                    uni_code = uni_course.get("code", "")
                    uni_title = uni_course.get("title", "")
                    major_desc = f"{uni_code}: {uni_title}" if uni_title else uni_code
                    
                    for option_group in smc_options:
                        for course in option_group:
                            code = course.get("code", "")
                            
                            if code in all_student_codes:
                                continue
                            
                            if code not in major_course_map:
                                major_course_map[code] = {}
                            
                            if target_id not in major_course_map[code]:
                                major_course_map[code][target_id] = []
                            
                            if major_desc not in major_course_map[code][target_id]:
                                major_course_map[code][target_id].append(major_desc)
        
        # Get courses that satisfy missing GE areas
        ge_course_map = {}
        
        for pattern, missing_areas in missing_ge_by_pattern.items():
            for area in missing_areas:
                courses = self.rec_engine.get_courses_for_ge_area(
                    area, year_code, pattern
                )
                for course_info in courses:
                    code = course_info["code"]
                    if code in all_student_codes:
                        continue
                    
                    if code not in ge_course_map:
                        ge_course_map[code] = {}
                    
                    if pattern not in ge_course_map[code]:
                        ge_course_map[code][pattern] = []
                    
                    if area not in ge_course_map[code][pattern]:
                        ge_course_map[code][pattern].append(area)
        
        # Combine and build MultiTargetCourse objects
        all_course_codes = set(major_course_map.keys()) | set(ge_course_map.keys())
        
        multi_target_courses = []
        
        for code in all_course_codes:
            catalog_entry = self.loader.master_catalog.get(code, {})
            title = catalog_entry.get("title", "")
            units = catalog_entry.get("units", 3.0)
            
            prereq_status = self.rec_engine.check_prerequisites(
                code, completed_codes, pending_codes
            )
            
            ge_satisfaction = ge_course_map.get(code, {})
            major_satisfaction = major_course_map.get(code, {})
            
            total_ge = sum(len(areas) for areas in ge_satisfaction.values())
            total_major = sum(len(reqs) for reqs in major_satisfaction.values())
            targets_helped = len(major_satisfaction)
            
            if total_ge > 0 and targets_helped == 0:
                targets_helped = 0
            
            efficiency = total_ge + total_major
            
            if efficiency == 0:
                continue
            
            # Build efficiency breakdown
            breakdown = {"ge": {}, "major": {}}
            
            for pattern, areas in ge_satisfaction.items():
                breakdown["ge"][pattern] = areas
            
            for target_id, reqs in major_satisfaction.items():
                target_name = target_id
                for audit in target_audits:
                    if audit.target.target_id == target_id:
                        target_name = f"{audit.target.university} - {audit.target.major}"
                        break
                breakdown["major"][target_name] = reqs
            
            multi_target_courses.append(MultiTargetCourse(
                code=code,
                title=title,
                units=units,
                prereqs_met=prereq_status["prereqs_met"],
                prereqs_missing=prereq_status["prereqs_missing"],
                prereqs_in_progress=prereq_status["prereqs_in_progress"],
                ge_satisfaction=ge_satisfaction,
                major_satisfaction=major_satisfaction,
                total_ge_areas=total_ge,
                total_major_reqs=total_major,
                total_targets_helped=targets_helped,
                efficiency_score=efficiency,
                efficiency_breakdown=breakdown,
            ))
        
        multi_target_courses.sort()
        
        return multi_target_courses

