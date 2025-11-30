"""
Course Recommendation Engine.

This module handles generating course recommendations for missing requirements
with prerequisite analysis and cross-referencing.
"""

from typing import Optional

from ..models import (
    CourseOption,
    AreaRecommendation,
    MajorCourseItem,
    MajorRecommendation,
    CrossReferencedCourse,
    EfficiencyGroup,
)
from ..data import DataLoader


class CourseRecommendationEngine:
    """
    Generates course recommendations for missing requirements with prerequisite analysis.
    
    PURPOSE:
    --------
    For each missing requirement (GE or Major), this engine:
    1. Lists all available SMC courses that can satisfy it
    2. Checks prerequisites for each option against student's completed courses
    3. Shows what prerequisites are missing or in-progress
    4. Calculates how many semesters away each course is
    
    IGETC/CAL-GETC DOUBLE-COUNTING RULES:
    -------------------------------------
    Per UC policy, courses listed in multiple areas shall NOT be certified in 
    more than one area, EXCEPT for Languages Other Than English (LOTE) courses
    which CAN be certified in BOTH areas 3B and 6A.
    """
    
    def __init__(self, data_loader: DataLoader):
        self.loader = data_loader
        self._ge_course_cache = {}  # Cache: {year_code: {area_code: [courses]}}
    
    def check_prerequisites(self, course_code: str, completed_codes: set, 
                           pending_codes: set) -> dict:
        """
        Check prerequisite status for a course.
        
        Returns:
            {
                "prereqs_met": bool,
                "prereqs_missing": ["ANATMY 1", ...],
                "prereqs_in_progress": ["CHEM 10", ...],
                "coreqs": ["BIOL 3L"],
                "advisories": ["CHEM 10"],
                "semesters_away": int,
            }
        """
        deps = self.loader.dependencies
        course_deps = deps.get(course_code, {})
        
        prereqs = course_deps.get("prerequisites", [])
        coreqs = course_deps.get("corequisites", [])
        advisories = course_deps.get("advisories", [])
        
        # Parse prerequisites - handle OR logic
        prereqs_missing = []
        prereqs_in_progress = []
        
        for prereq in prereqs:
            if " or " not in prereq.lower():
                if prereq in completed_codes:
                    continue
                elif prereq in pending_codes:
                    prereqs_in_progress.append(prereq)
                else:
                    prereqs_missing.append(prereq)
            else:
                # Handle OR case: "MATH 20 or MATH 26"
                options = [p.strip() for p in prereq.lower().replace(" or ", "|").split("|")]
                options_upper = [p.upper() for p in options]
                
                if any(opt in completed_codes for opt in options_upper):
                    continue
                elif any(opt in pending_codes for opt in options_upper):
                    prereqs_in_progress.append(prereq)
                else:
                    prereqs_missing.append(prereq)
        
        prereqs_met = len(prereqs_missing) == 0 and len(prereqs_in_progress) == 0
        
        # Calculate semesters away
        if prereqs_met:
            semesters_away = 0
        elif len(prereqs_missing) == 0 and len(prereqs_in_progress) > 0:
            semesters_away = 1
        else:
            max_depth = 1
            for missing in prereqs_missing:
                missing_deps = deps.get(missing, {}).get("prerequisites", [])
                if missing_deps:
                    for md in missing_deps:
                        if md not in completed_codes and md not in pending_codes:
                            max_depth = 2
                            break
            semesters_away = max_depth
        
        return {
            "prereqs_met": prereqs_met,
            "prereqs_missing": prereqs_missing,
            "prereqs_in_progress": prereqs_in_progress,
            "coreqs": coreqs,
            "advisories": advisories,
            "semesters_away": semesters_away,
        }
    
    def get_courses_for_ge_area(self, area_code: str, year_code: int, 
                                 pattern_key: str) -> list:
        """
        Get all SMC courses that satisfy a GE area.
        
        Returns:
            List of course info dicts: [{code, title, ge_areas}, ...]
        """
        cache_key = (year_code, pattern_key)
        
        if cache_key not in self._ge_course_cache:
            ge_data = self.loader.load_raw_ge(pattern_key, year_code)
            if not ge_data:
                return []
            
            area_to_courses = {}
            course_list = ge_data.get("courseInformationList", [])
            
            for course in course_list:
                code = course.get("identifier", "")
                title = course.get("courseTitle", "")
                transfer_areas = course.get("transferAreas", [])
                
                course_areas = [ta.get("code", "") for ta in transfer_areas]
                
                for area in transfer_areas:
                    ac = area.get("code", "")
                    if ac not in area_to_courses:
                        area_to_courses[ac] = []
                    
                    area_to_courses[ac].append({
                        "code": code,
                        "title": title,
                        "ge_areas": course_areas,
                    })
            
            self._ge_course_cache[cache_key] = area_to_courses
        
        return self._ge_course_cache.get(cache_key, {}).get(area_code, [])
    
    def recommend_ge_courses(self, ge_audit_result: dict, student_state: dict,
                             year_code: int) -> list:
        """
        Generate course recommendations for missing GE areas.
        """
        pattern_key = ge_audit_result.get("pattern_key", "IGETC").upper()
        if pattern_key == "IGETC":
            pattern_key = "IGETC"
        elif pattern_key == "cal_getc" or pattern_key == "CALGETC":
            pattern_key = "CALGETC"
        
        completed_codes = {c.code for c in student_state["completed"]}
        pending_codes = {c.code for c in student_state["in_progress"]}
        all_student_codes = completed_codes | pending_codes
        
        # Track courses already used for GE
        used_courses = set()
        for area in ge_audit_result["areas"]:
            for c in area.completed_courses:
                used_courses.add(c.code)
            for c in area.pending_courses:
                used_courses.add(c.code)
        
        recommendations = []
        
        for area in ge_audit_result["areas"]:
            if area.is_satisfied:
                continue
            
            courses_needed = area.required_courses - len(area.completed_courses)
            
            # Check for subareas
            if "Subareas:" in area.notes:
                subarea_info = area.notes.split("Subareas:")[1].strip()
                subarea_parts = subarea_info.split(" | ")
                
                for part in subarea_parts:
                    if "✗" in part:
                        subarea_code = part.split(" ")[0].strip()
                        sub_rec = self._recommend_for_area(
                            subarea_code, area.name, 1, year_code, pattern_key,
                            completed_codes, pending_codes, all_student_codes, 
                            used_courses, is_subarea=True, parent_area=area.code
                        )
                        if sub_rec:
                            recommendations.append(sub_rec)
            else:
                rec = self._recommend_for_area(
                    area.code, area.name, courses_needed, year_code, pattern_key,
                    completed_codes, pending_codes, all_student_codes, used_courses
                )
                if rec:
                    recommendations.append(rec)
        
        return recommendations
    
    def _recommend_for_area(self, area_code: str, area_name: str, courses_needed: int,
                            year_code: int, pattern_key: str,
                            completed_codes: set, pending_codes: set, 
                            all_student_codes: set, used_courses: set,
                            is_subarea: bool = False, parent_area: str = "") -> Optional[AreaRecommendation]:
        """
        Generate recommendations for a single GE area or subarea.
        """
        available = self.get_courses_for_ge_area(area_code, year_code, pattern_key)
        
        course_options = []
        for course_info in available:
            code = course_info["code"]
            
            if code in all_student_codes:
                continue
            
            # Skip if already used (with 3B/6A exception)
            if code in used_courses:
                course_areas = course_info.get("ge_areas", [])
                if area_code in ["3B", "6A"] and ("3B" in course_areas or "6A" in course_areas):
                    pass
                else:
                    continue
            
            prereq_status = self.check_prerequisites(code, completed_codes, pending_codes)
            catalog_entry = self.loader.master_catalog.get(code, {})
            units = catalog_entry.get("units", 3.0)
            title = course_info.get("title", catalog_entry.get("title", ""))
            
            course_options.append(CourseOption(
                code=code,
                title=title,
                units=units,
                prereqs_met=prereq_status["prereqs_met"],
                prereqs_missing=prereq_status["prereqs_missing"],
                prereqs_in_progress=prereq_status["prereqs_in_progress"],
                coreqs=prereq_status["coreqs"],
                advisories=prereq_status["advisories"],
                semesters_away=prereq_status["semesters_away"],
                ge_areas=course_info.get("ge_areas", []),
            ))
        
        # Sort alphabetically
        course_options.sort(key=lambda c: c.code)
        
        if not course_options:
            return None
        
        return AreaRecommendation(
            area_code=area_code,
            area_name=area_name,
            courses_needed=courses_needed,
            available_courses=course_options,
            subarea_code=area_code if is_subarea else "",
        )
    
    def recommend_major_courses(self, major_audit_result: dict, 
                                student_state: dict) -> list:
        """
        Generate course recommendations for missing major requirements.
        """
        if "error" in major_audit_result:
            return []
        
        completed_codes = {c.code for c in student_state["completed"]}
        pending_codes = {c.code for c in student_state["in_progress"]}
        
        recommendations = []
        
        for req_num, req in enumerate(major_audit_result["requirements"], 1):
            if req.is_satisfied:
                continue
            
            missing_items = req.items.get("missing", [])
            
            if not missing_items:
                continue
            
            course_items = []
            
            for item in missing_items:
                uni_course = item.get("university_course", {})
                smc_options_raw = item.get("smc_options", [])
                articulation_type = item.get("articulation_type", "")
                
                smc_options = []
                
                if smc_options_raw and articulation_type != "NO_ARTICULATION":
                    for option_group in smc_options_raw:
                        for course in option_group:
                            code = course.get("code", "")
                            
                            if code in completed_codes or code in pending_codes:
                                continue
                            
                            prereq_status = self.check_prerequisites(code, completed_codes, pending_codes)
                            catalog_entry = self.loader.master_catalog.get(code, {})
                            units = catalog_entry.get("units", 3.0)
                            title = catalog_entry.get("title", course.get("title", ""))
                            
                            smc_options.append(CourseOption(
                                code=code,
                                title=title,
                                units=units,
                                prereqs_met=prereq_status["prereqs_met"],
                                prereqs_missing=prereq_status["prereqs_missing"],
                                prereqs_in_progress=prereq_status["prereqs_in_progress"],
                                coreqs=prereq_status["coreqs"],
                                advisories=prereq_status["advisories"],
                                semesters_away=prereq_status["semesters_away"],
                            ))
                
                course_items.append(MajorCourseItem(
                    university_course=uni_course,
                    smc_options=smc_options,
                    has_articulation=bool(smc_options),
                ))
            
            # Determine logic display
            logic = req.logic
            if logic == "ONE_OF":
                logic_display = f"Choose ONE of these {len(course_items)} options"
            elif logic == "ALL_OF":
                logic_display = "Complete ALL of these courses"
            elif logic == "N_OF":
                logic_display = f"Complete at least {req.min_required} of these"
            else:
                logic_display = logic
            
            recommendations.append(MajorRecommendation(
                requirement_id=req.requirement_id,
                requirement_num=req_num,
                logic=logic,
                logic_display=logic_display,
                min_required=req.min_required or 1,
                items=course_items,
            ))
        
        return recommendations
    
    def cross_reference_ge_and_major(self, ge_audit_result: dict, major_audit_result: dict,
                                      student_state: dict, year_code: int) -> list:
        """
        Find courses that satisfy BOTH GE requirements AND major requirements.
        
        Returns:
            List of EfficiencyGroup objects, sorted by efficiency (highest first)
        """
        if "error" in major_audit_result:
            return []
        
        pattern_key = ge_audit_result.get("pattern_key", "IGETC").upper()
        if pattern_key == "IGETC":
            pattern_key = "IGETC"
        elif pattern_key.lower() == "cal_getc" or pattern_key == "CALGETC":
            pattern_key = "CALGETC"
        
        completed_codes = {c.code for c in student_state["completed"]}
        pending_codes = {c.code for c in student_state["in_progress"]}
        all_student_codes = completed_codes | pending_codes
        
        # STEP 1: Identify missing GE areas
        missing_ge_areas = set()
        for area in ge_audit_result["areas"]:
            if not area.is_satisfied:
                if "Subareas:" in area.notes:
                    subarea_info = area.notes.split("Subareas:")[1].strip()
                    subarea_parts = subarea_info.split(" | ")
                    for part in subarea_parts:
                        if "✗" in part:
                            subarea_code = part.split(" ")[0].strip()
                            missing_ge_areas.add(subarea_code)
                else:
                    missing_ge_areas.add(area.code)
        
        # STEP 2: Collect all SMC courses that can satisfy missing MAJOR requirements
        major_course_map = {}
        requirement_groups = {}
        
        for req_num, req in enumerate(major_audit_result["requirements"], 1):
            if req.is_satisfied:
                continue
            
            req_id = req.requirement_id
            req_logic = req.logic
            requirement_groups[req_id] = {
                "logic": req_logic,
                "num": req_num,
                "courses": [],
                "items": [],
            }
            
            missing_items = req.items.get("missing", [])
            
            for item in missing_items:
                uni_course = item.get("university_course", {})
                smc_options = item.get("smc_options", [])
                articulation_type = item.get("articulation_type", "")
                
                if not smc_options or articulation_type == "NO_ARTICULATION":
                    continue
                
                uni_code = uni_course.get("code", "")
                uni_title = uni_course.get("title", "")
                major_desc = f"{uni_code}: {uni_title}" if uni_title else uni_code
                
                requirement_groups[req_id]["items"].append(major_desc)
                
                for option_group in smc_options:
                    for course in option_group:
                        code = course.get("code", "")
                        
                        if code in all_student_codes:
                            continue
                        
                        requirement_groups[req_id]["courses"].append(code)
                        
                        if code not in major_course_map:
                            major_course_map[code] = {
                                "major_requirements": [],
                                "requirement_info": [],
                                "ge_areas": [],
                            }
                        
                        if major_desc not in major_course_map[code]["major_requirements"]:
                            major_course_map[code]["major_requirements"].append(major_desc)
                        
                        req_info = {
                            "req_id": req_id,
                            "req_num": req_num,
                            "logic": req_logic,
                            "all_items": requirement_groups[req_id]["items"],
                        }
                        if req_info not in major_course_map[code]["requirement_info"]:
                            major_course_map[code]["requirement_info"].append(req_info)
        
        # STEP 3: Check which GE areas each major course satisfies
        for code in major_course_map:
            ge_attrs = self.loader.get_course_ge_attributes(code, year_code)
            
            if pattern_key == "IGETC":
                course_ge_areas = ge_attrs.get("IGETC", [])
            else:
                course_ge_areas = ge_attrs.get("Cal_GETC", [])
            
            for ge_area in missing_ge_areas:
                for course_ge in course_ge_areas:
                    if course_ge == ge_area or (course_ge.startswith(ge_area) and len(ge_area) == 1):
                        if ge_area not in major_course_map[code]["ge_areas"]:
                            major_course_map[code]["ge_areas"].append(ge_area)
                        break
        
        # STEP 4: Filter to courses that satisfy BOTH
        cross_referenced = []
        
        for code, data in major_course_map.items():
            if not data["ge_areas"]:
                continue
            
            prereq_status = self.check_prerequisites(code, completed_codes, pending_codes)
            catalog_entry = self.loader.master_catalog.get(code, {})
            units = catalog_entry.get("units", 3.0)
            title = catalog_entry.get("title", "")
            
            efficiency = len(data["ge_areas"]) + len(data["major_requirements"])
            
            cross_referenced.append(CrossReferencedCourse(
                code=code,
                title=title,
                units=units,
                prereqs_met=prereq_status["prereqs_met"],
                prereqs_missing=prereq_status["prereqs_missing"],
                prereqs_in_progress=prereq_status["prereqs_in_progress"],
                ge_areas_satisfied=sorted(data["ge_areas"]),
                major_requirements_satisfied=data["major_requirements"],
                requirement_info=data.get("requirement_info", []),
                efficiency_score=efficiency,
            ))
        
        # STEP 5: Group courses
        req_based_groups = {}
        
        for course in cross_referenced:
            one_of_reqs = [ri for ri in course.requirement_info if ri.get("logic") == "ONE_OF"]
            
            if one_of_reqs:
                req = one_of_reqs[0]
                key = (req["req_id"], tuple(sorted(course.ge_areas_satisfied)))
            else:
                key = (f"single_{course.code}", tuple(sorted(course.ge_areas_satisfied)))
            
            if key not in req_based_groups:
                req_based_groups[key] = []
            req_based_groups[key].append(course)
        
        # Convert to EfficiencyGroup objects
        efficiency_groups = []
        
        for key, courses in req_based_groups.items():
            courses.sort(key=lambda c: c.code)
            
            first_course = courses[0]
            one_of_reqs = [ri for ri in first_course.requirement_info if ri.get("logic") == "ONE_OF"]
            is_or_group = len(one_of_reqs) > 0 and len(courses) > 1
            
            req_info = first_course.requirement_info
            efficiency = first_course.efficiency_score
            ge_areas = first_course.ge_areas_satisfied
            major_reqs = first_course.major_requirements_satisfied
            
            if is_or_group and one_of_reqs:
                req_num = one_of_reqs[0].get("req_num", "?")
                desc = f"Requirement {req_num}: Choose ONE (any of these {len(courses)} courses works)"
            elif len(courses) == 1:
                desc = f"This course satisfies {efficiency} requirements"
            else:
                desc = f"Choose ONE of these {len(courses)} courses"
            
            efficiency_groups.append(EfficiencyGroup(
                efficiency_score=efficiency,
                ge_areas=list(ge_areas),
                major_requirements=list(major_reqs),
                requirement_info=req_info,
                courses=courses,
                description=desc,
                is_or_group=is_or_group,
            ))
        
        efficiency_groups.sort(key=lambda g: (-g.efficiency_score, -len(g.courses)))
        
        return efficiency_groups

