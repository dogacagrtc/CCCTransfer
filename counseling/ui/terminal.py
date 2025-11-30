"""
Terminal Display Implementation.

This module handles all console/terminal output formatting.
It's the ONLY place where printing happens in the counseling package.

To create a different UI (web, PDF, etc.), create a new class with
the same method signatures but different output handling.
"""

from ..models import (
    AreaAuditResult,
    RequirementAuditResult,
    CourseOption,
    EfficiencyGroup,
    CrossReferencedCourse,
    TargetAuditResult,
    MultiTargetCourse,
    MultiTargetAnalysis,
)


class TerminalDisplay:
    """
    Pretty terminal output for audit results.
    
    ═══════════════════════════════════════════════════════════════════════════
    HOW TO REPLACE THIS UI
    ═══════════════════════════════════════════════════════════════════════════
    
    1. FOR WEB UI:
       Create a WebDisplay class with the same method signatures.
       Instead of print(), return HTML or render templates.
       
    2. FOR API RESPONSE:
       Create an APIFormatter class that converts dataclasses to JSON.
       
    3. FOR PDF EXPORT:
       Create a PDFExporter class using reportlab or similar.
    
    ═══════════════════════════════════════════════════════════════════════════
    """
    
    # ANSI color codes for terminal styling
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    WHITE = "\033[97m"
    
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_RED = "\033[41m"
    
    @classmethod
    def print_header(cls, title: str):
        """Print a major section header with decorative borders."""
        width = 70
        print()
        print(f"{cls.BOLD}{cls.CYAN}{'═' * width}{cls.RESET}")
        print(f"{cls.BOLD}{cls.CYAN}  {title}{cls.RESET}")
        print(f"{cls.BOLD}{cls.CYAN}{'═' * width}{cls.RESET}")
    
    @classmethod
    def print_subheader(cls, title: str):
        """Print a subsection header."""
        print()
        print(f"{cls.BOLD}{cls.WHITE}  ── {title} ──{cls.RESET}")
    
    @classmethod
    def status_badge(cls, satisfied: bool, pending: bool = False) -> str:
        """Return a colored status badge."""
        if satisfied:
            return f"{cls.BG_GREEN}{cls.WHITE} ✓ COMPLETE {cls.RESET}"
        elif pending:
            return f"{cls.BG_YELLOW}{cls.WHITE} ⏳ PENDING {cls.RESET}"
        else:
            return f"{cls.BG_RED}{cls.WHITE} ✗ MISSING {cls.RESET}"
    
    @classmethod
    def print_student_info(cls, student: dict):
        """Print student identification information."""
        cls.print_header("STUDENT INFORMATION")
        print(f"  {cls.BOLD}Name:{cls.RESET} {student.get('name', 'Unknown')}")
        print(f"  {cls.BOLD}Institution:{cls.RESET} {student.get('institution', 'Unknown')}")
        print(f"  {cls.BOLD}Generated:{cls.RESET} {student.get('generated_date', 'Unknown')}")
    
    @classmethod
    def print_ge_audit(cls, audit_result: dict):
        """Print GE (IGETC/Cal-GETC) audit results in tabular format."""
        cls.print_header(f"GE AUDIT: {audit_result['pattern_name'].upper()}")
        
        overall = audit_result["overall_satisfied"]
        status = cls.status_badge(overall)
        print(f"\n  {cls.BOLD}Overall Status:{cls.RESET} {status}")
        print(f"  {cls.BOLD}Total GE Units:{cls.RESET} {audit_result['total_units_completed']:.1f}")
        
        print(f"\n  {cls.BOLD}{'AREA':<8} {'NAME':<40} {'STATUS':<15} {'COURSES'}{cls.RESET}")
        print(f"  {cls.DIM}{'-' * 66}{cls.RESET}")
        
        for area in audit_result["areas"]:
            status_str = cls._area_status_str(area)
            courses_str = cls._courses_summary(area)
            
            if area.is_satisfied:
                code_color = cls.GREEN
            elif len(area.pending_courses) > 0:
                code_color = cls.YELLOW
            else:
                code_color = cls.RED
            
            print(f"  {code_color}{area.code:<8}{cls.RESET} {area.name:<40} {status_str:<15} {courses_str}")
            
            if "Subareas:" in area.notes and not area.is_satisfied:
                subarea_info = area.notes.split("Subareas:")[1].strip() if "Subareas:" in area.notes else ""
                if subarea_info:
                    print(f"  {cls.DIM}         └─ {subarea_info}{cls.RESET}")
    
    @classmethod
    def _area_status_str(cls, area: AreaAuditResult) -> str:
        """Get a short status string for an area."""
        if area.is_satisfied:
            return f"{cls.GREEN}✓ Done{cls.RESET}"
        elif len(area.pending_courses) > 0:
            return f"{cls.YELLOW}⏳ Pending{cls.RESET}"
        else:
            return f"{cls.RED}✗ Need {area.required_courses}{cls.RESET}"
    
    @classmethod
    def _courses_summary(cls, area: AreaAuditResult) -> str:
        """Get a summary of courses for an area."""
        completed = [c.code for c in area.completed_courses[:2]]
        pending = [c.code for c in area.pending_courses[:2]]
        
        parts = []
        if completed:
            parts.append(f"{cls.GREEN}{', '.join(completed)}{cls.RESET}")
        if pending:
            parts.append(f"{cls.YELLOW}[{', '.join(pending)}]{cls.RESET}")
        
        return " ".join(parts) if parts else f"{cls.DIM}(none){cls.RESET}"
    
    @classmethod
    def print_major_audit(cls, audit_result: dict):
        """Print major requirements audit results."""
        if "error" in audit_result:
            cls.print_header("MAJOR AUDIT: ERROR")
            print(f"\n  {cls.RED}Error: {audit_result['error']}{cls.RESET}")
            if audit_result.get("available_majors"):
                print(f"\n  {cls.BOLD}Available majors (first 10):{cls.RESET}")
                for m in audit_result["available_majors"]:
                    print(f"    • {m}")
            return
        
        major = audit_result["major"]
        university = audit_result["university"]
        
        cls.print_header(f"MAJOR AUDIT: {major.upper()}")
        print(f"  {cls.BOLD}University:{cls.RESET} {university}")
        
        overall = audit_result["overall_satisfied"]
        status = cls.status_badge(overall)
        pct = audit_result["completion_percentage"]
        
        print(f"\n  {cls.BOLD}Overall Status:{cls.RESET} {status}")
        print(f"  {cls.BOLD}Completion:{cls.RESET} {pct:.0f}% ({audit_result['satisfied_count']}/{audit_result['total_count']} requirements)")
        if audit_result["pending_count"] > 0:
            print(f"  {cls.BOLD}Pending:{cls.RESET} {audit_result['pending_count']} requirement(s)")
        
        cls.print_subheader("Requirements Detail")
        
        for i, req in enumerate(audit_result["requirements"], 1):
            cls._print_requirement(i, req)
    
    @classmethod
    def _print_requirement(cls, num: int, req: RequirementAuditResult):
        """
        Print a single requirement with its courses.
        
        INCOMPLETE DATA DETECTION:
        --------------------------
        If a requirement has no items (satisfied, pending, or missing), it likely
        means the articulation data from Assist.org is incomplete. We show a warning
        to let the student know to check Assist.org directly for this requirement.
        """
        items = req.items
        total_items = (len(items.get("satisfied", [])) + 
                       len(items.get("pending", [])) + 
                       len(items.get("missing", [])))
        
        # Determine status icon
        if req.is_satisfied:
            status = f"{cls.GREEN}✓{cls.RESET}"
        elif req.is_pending:
            status = f"{cls.YELLOW}⏳{cls.RESET}"
        else:
            status = f"{cls.RED}✗{cls.RESET}"
        
        logic_display = {
            "ALL_OF": "Complete all",
            "ONE_OF": "Choose one",
            "N_OF": f"Choose {req.min_required}",
            "CHOOSE_N": f"Choose {req.min_required or 1}",
            "AT_LEAST_N": f"Choose {req.min_required or 1}+",
        }.get(req.logic, req.logic)
        
        print(f"\n  {status} {cls.BOLD}Requirement {num}{cls.RESET} {cls.DIM}({logic_display}){cls.RESET}")
        
        # Check for incomplete data: no items but requirement expects courses
        if total_items == 0:
            if req.logic in ("CHOOSE_N", "AT_LEAST_N", "N_OF", "ONE_OF") and not req.is_satisfied:
                # This requirement expects courses but has none listed
                print(f"     {cls.YELLOW}⚠ INCOMPLETE DATA{cls.RESET} — This requirement may have courses not listed in our data.")
                print(f"       {cls.DIM}Please check Assist.org directly for the complete requirement.{cls.RESET}")
            elif req.logic == "ALL_OF" and req.is_satisfied:
                # ALL_OF with no items = nothing required (trivially satisfied)
                print(f"     {cls.DIM}(No specific courses listed){cls.RESET}")
            return
        
        for item in items.get("satisfied", []):
            uni_course = item["university_course"]
            smc_courses = item["satisfied_by"]
            print(f"     {cls.GREEN}✓{cls.RESET} {uni_course.get('code', '')} → {cls.GREEN}{', '.join(smc_courses)}{cls.RESET}")
        
        for item in items.get("pending", []):
            uni_course = item["university_course"]
            smc_courses = item["pending_courses"]
            print(f"     {cls.YELLOW}⏳{cls.RESET} {uni_course.get('code', '')} → {cls.YELLOW}[{', '.join(smc_courses)}]{cls.RESET}")
        
        if not req.is_satisfied:
            for item in items.get("missing", []):
                uni_course = item["university_course"]
                options = item["smc_options"]
                artic_type = item["articulation_type"]
                
                if artic_type == "No Articulation":
                    print(f"     {cls.RED}✗{cls.RESET} {uni_course.get('code', '')} {cls.DIM}(No SMC equivalent){cls.RESET}")
                elif options:
                    option_strs = []
                    for opt_group in options[:3]:
                        codes = [c.get("code", "") for c in opt_group]
                        option_strs.append(" + ".join(codes))
                    options_display = " OR ".join(option_strs)
                    if len(options) > 3:
                        options_display += f" {cls.DIM}(+{len(options)-3} more){cls.RESET}"
                    print(f"     {cls.RED}✗{cls.RESET} {uni_course.get('code', '')} → Need: {options_display}")
                else:
                    print(f"     {cls.RED}✗{cls.RESET} {uni_course.get('code', '')} {cls.DIM}(check articulation){cls.RESET}")
    
    @classmethod
    def print_summary(cls, ge_result: dict, major_result: dict):
        """Print a final summary with overall transfer readiness."""
        cls.print_header("SUMMARY")
        
        ge_done = ge_result["overall_satisfied"]
        major_done = major_result.get("overall_satisfied", False)
        
        print(f"\n  {cls.BOLD}General Education:{cls.RESET} {cls.status_badge(ge_done)}")
        print(f"  {cls.BOLD}Major Preparation:{cls.RESET} {cls.status_badge(major_done, major_result.get('pending_count', 0) > 0)}")
        
        if ge_done and major_done:
            print(f"\n  {cls.GREEN}{cls.BOLD}🎉 Congratulations! You are ready to transfer!{cls.RESET}")
        else:
            print(f"\n  {cls.YELLOW}Keep going! Review the available courses below.{cls.RESET}")
        
        print()
    
    @classmethod
    def print_major_recommendations(cls, recommendations: list):
        """Print course recommendations for missing major requirements."""
        if not recommendations:
            return
        
        cls.print_header("MAJOR: AVAILABLE COURSES TO TAKE")
        print(f"\n  {cls.DIM}Courses you can take to complete missing major requirements.{cls.RESET}")
        
        for rec in recommendations:
            print(f"\n  {cls.BOLD}{'─' * 66}{cls.RESET}")
            
            if rec.logic == "ONE_OF":
                print(f"  {cls.BOLD}{cls.CYAN}Requirement {rec.requirement_num}{cls.RESET} — {cls.GREEN}{cls.BOLD}Choose ONE:{cls.RESET}")
            elif rec.logic == "ALL_OF":
                print(f"  {cls.BOLD}{cls.CYAN}Requirement {rec.requirement_num}{cls.RESET} — {cls.YELLOW}{cls.BOLD}Complete ALL:{cls.RESET}")
            elif rec.logic == "N_OF":
                print(f"  {cls.BOLD}{cls.CYAN}Requirement {rec.requirement_num}{cls.RESET} — {cls.YELLOW}{cls.BOLD}Complete at least {rec.min_required}:{cls.RESET}")
            else:
                print(f"  {cls.BOLD}{cls.CYAN}Requirement {rec.requirement_num}{cls.RESET}")
            
            for i, item in enumerate(rec.items):
                uni_code = item.university_course.get("code", "Unknown")
                uni_title = item.university_course.get("title", "")
                
                if rec.logic == "ONE_OF":
                    option_label = f"{cls.CYAN}Option {chr(65+i)}:{cls.RESET}"
                else:
                    option_label = f"{cls.DIM}•{cls.RESET}"
                
                print(f"\n    {option_label} {cls.BOLD}{cls.MAGENTA}{uni_code}{cls.RESET}", end="")
                if uni_title:
                    title_display = uni_title[:35] + "..." if len(uni_title) > 35 else uni_title
                    print(f" {cls.DIM}({title_display}){cls.RESET}")
                else:
                    print()
                
                if not item.has_articulation:
                    print(f"      {cls.RED}No SMC equivalent available{cls.RESET}")
                    continue
                
                for smc_course in item.smc_options:
                    cls._print_major_course_option(smc_course)
    
    @classmethod
    def _print_major_course_option(cls, course: CourseOption):
        """Print a single SMC course option for major requirements."""
        if course.prereqs_met:
            code_color = cls.GREEN
            status = f"{cls.GREEN}✓ CAN TAKE NOW{cls.RESET}"
        elif course.prereqs_in_progress and not course.prereqs_missing:
            code_color = cls.YELLOW
            status = f"{cls.YELLOW}⏳ NEXT SEMESTER{cls.RESET}"
        else:
            code_color = cls.RED
            status = f"{cls.RED}⚠ PREREQS NEEDED{cls.RESET}"
        
        title_display = course.title[:30] + "..." if len(course.title) > 30 else course.title
        print(f"      {code_color}→ {course.code}{cls.RESET} - {title_display} ({course.units} units)")
        print(f"        {status}")
        
        if course.prereqs_missing:
            for prereq in course.prereqs_missing:
                print(f"        {cls.DIM}  Needs: {cls.RED}{prereq}{cls.RESET}")
    
    @classmethod
    def print_ge_recommendations(cls, recommendations: list, pattern_name: str):
        """Print course recommendations for missing GE areas."""
        if not recommendations:
            return
        
        cls.print_header(f"GE: AVAILABLE COURSES FOR {pattern_name.upper()}")
        print(f"\n  {cls.DIM}Courses you can take to complete missing GE areas.{cls.RESET}")
        print(f"  {cls.BOLD}{cls.YELLOW}⚠ DOUBLE-COUNTING RULE:{cls.RESET} {cls.DIM}A course can only count for ONE area")
        print(f"    (Exception: Language courses can count for both 3B and 6A){cls.RESET}")
        
        for rec in recommendations:
            if rec.subarea_code:
                print(f"\n  {cls.BOLD}{cls.CYAN}▸ Area {rec.subarea_code}{cls.RESET} - {rec.area_name}")
            else:
                print(f"\n  {cls.BOLD}{cls.CYAN}▸ Area {rec.area_code}{cls.RESET} - {rec.area_name}")
            
            print(f"    {cls.DIM}Need {rec.courses_needed} course(s){cls.RESET}")
            
            if not rec.available_courses:
                print(f"    {cls.YELLOW}No additional courses available{cls.RESET}")
                continue
            
            can_take_now = sum(1 for c in rec.available_courses if c.prereqs_met)
            need_prereqs = len(rec.available_courses) - can_take_now
            
            print(f"    {cls.DIM}Total: {len(rec.available_courses)} ({cls.GREEN}{can_take_now} available{cls.RESET}{cls.DIM}, {cls.YELLOW}{need_prereqs} need prereqs{cls.RESET}{cls.DIM}){cls.RESET}")
            
            for course in rec.available_courses:
                cls._print_ge_course_option(course)
    
    @classmethod
    def _print_ge_course_option(cls, course: CourseOption):
        """Print a GE course option."""
        if course.prereqs_met:
            status = f"{cls.GREEN}✓{cls.RESET}"
            code_color = cls.GREEN
        elif course.prereqs_in_progress and not course.prereqs_missing:
            status = f"{cls.YELLOW}⏳{cls.RESET}"
            code_color = cls.YELLOW
        else:
            status = f"{cls.RED}✗{cls.RESET}"
            code_color = cls.RED
        
        print(f"      {status} {code_color}{course.code}{cls.RESET} - {course.title[:30]}{'...' if len(course.title) > 30 else ''}", end="")
        
        if course.ge_areas and len(course.ge_areas) > 1:
            areas_str = ", ".join(course.ge_areas[:4])
            print(f" {cls.DIM}[also: {areas_str}]{cls.RESET}", end="")
        
        print()
        
        if course.prereqs_missing:
            missing_str = ", ".join(course.prereqs_missing[:2])
            print(f"        {cls.DIM}↳ Need: {cls.RED}{missing_str}{cls.RESET}")
        elif course.prereqs_in_progress:
            pending_str = ", ".join(course.prereqs_in_progress)
            print(f"        {cls.DIM}↳ In progress: {cls.YELLOW}{pending_str}{cls.RESET}")
    
    @classmethod
    def print_cross_reference(cls, efficiency_groups: list, pattern_name: str):
        """Print cross-referenced courses that satisfy BOTH GE and Major."""
        if not efficiency_groups:
            print(f"\n  {cls.DIM}No courses found that satisfy both GE and Major requirements.{cls.RESET}")
            return
        
        cls.print_header("⭐ MOST EFFICIENT COURSES (GE + MAJOR)")
        print(f"\n  {cls.BOLD}These courses satisfy BOTH {pattern_name} AND major requirements!{cls.RESET}")
        print(f"  {cls.DIM}Taking these saves time and units.{cls.RESET}")
        
        for rank, group in enumerate(efficiency_groups, 1):
            print(f"\n  {cls.BOLD}╔{'═' * 64}╗{cls.RESET}")
            
            if group.efficiency_score >= 3:
                eff_color = cls.GREEN
                eff_label = "EXCELLENT"
            elif group.efficiency_score >= 2:
                eff_color = cls.YELLOW
                eff_label = "GOOD"
            else:
                eff_color = cls.WHITE
                eff_label = "FAIR"
            
            print(f"  {cls.BOLD}║{cls.RESET}  {eff_color}{cls.BOLD}#{rank} [{eff_label}] Satisfies {group.efficiency_score} requirements{cls.RESET}")
            print(f"  {cls.BOLD}╠{'═' * 64}╣{cls.RESET}")
            
            ge_display = ", ".join(group.ge_areas) if group.ge_areas else "None"
            print(f"  {cls.BOLD}║{cls.RESET}  {cls.CYAN}📚 GE Area(s):{cls.RESET} {ge_display}")
            
            if group.is_or_group and group.requirement_info:
                one_of_reqs = [ri for ri in group.requirement_info if ri.get("logic") == "ONE_OF"]
                if one_of_reqs:
                    req_num = one_of_reqs[0].get("req_num", "?")
                    print(f"  {cls.BOLD}║{cls.RESET}  {cls.MAGENTA}🎯 Major:{cls.RESET} Requirement {req_num} {cls.GREEN}(Choose ONE){cls.RESET}")
            else:
                for i, major_req in enumerate(group.major_requirements):
                    prefix = "🎯 Major:" if i == 0 else "        "
                    req_display = major_req[:50] + "..." if len(major_req) > 50 else major_req
                    print(f"  {cls.BOLD}║{cls.RESET}  {cls.MAGENTA}{prefix}{cls.RESET} {req_display}")
            
            print(f"  {cls.BOLD}╠{'═' * 64}╣{cls.RESET}")
            
            if len(group.courses) == 1:
                print(f"  {cls.BOLD}║{cls.RESET}  {cls.BOLD}Recommended Course:{cls.RESET}")
            elif group.is_or_group:
                print(f"  {cls.BOLD}║{cls.RESET}  {cls.GREEN}{cls.BOLD}★ Pick ANY ONE:{cls.RESET}")
            else:
                print(f"  {cls.BOLD}║{cls.RESET}  {cls.BOLD}Available Options:{cls.RESET}")
            
            print(f"  {cls.BOLD}║{cls.RESET}")
            
            for i, course in enumerate(group.courses):
                is_last = (i == len(group.courses) - 1)
                cls._print_cross_ref_course_boxed(course, is_last)
            
            print(f"  {cls.BOLD}╚{'═' * 64}╝{cls.RESET}")
    
    @classmethod
    def _print_cross_ref_course_boxed(cls, course: CrossReferencedCourse, is_last: bool):
        """Print a cross-referenced course within the box layout."""
        if course.prereqs_met:
            status_icon = "✓"
            status_text = "Ready to take"
            code_color = cls.GREEN
            prereq_note = ""
        elif course.prereqs_in_progress and not course.prereqs_missing:
            status_icon = "⏳"
            status_text = "Next semester"
            code_color = cls.YELLOW
            prereq_note = f" (waiting for: {', '.join(course.prereqs_in_progress)})"
        else:
            status_icon = "⚠"
            status_text = "Prereqs needed"
            code_color = cls.RED
            prereq_note = ""
        
        title_display = course.title[:35] + "..." if len(course.title) > 35 else course.title
        print(f"  {cls.BOLD}║{cls.RESET}    {code_color}{status_icon} {course.code}{cls.RESET} — {title_display}")
        print(f"  {cls.BOLD}║{cls.RESET}      {cls.DIM}Units: {course.units} │ {code_color}{status_text}{cls.RESET}{prereq_note}")
        
        if course.prereqs_missing:
            for prereq in course.prereqs_missing:
                prereq_display = prereq[:45] + "..." if len(prereq) > 45 else prereq
                print(f"  {cls.BOLD}║{cls.RESET}      {cls.DIM}└─ Needs: {cls.RED}{prereq_display}{cls.RESET}")
        
        if not is_last:
            print(f"  {cls.BOLD}║{cls.RESET}")
    
    # =========================================================================
    # MULTI-TARGET DISPLAY METHODS
    # =========================================================================
    
    @classmethod
    def print_multi_target_analysis(cls, analysis: MultiTargetAnalysis):
        """Print complete multi-target analysis results."""
        cls.print_header("🎯 MULTI-TARGET ANALYSIS")
        
        print(f"\n  {cls.BOLD}Analyzing {len(analysis.targets)} university/major target(s):{cls.RESET}")
        for i, target in enumerate(analysis.targets, 1):
            system_label = "CSU" if target.target_system == "csu" else "UC"
            print(f"    {i}. {target.university} - {target.major} ({system_label})")
        
        print(f"\n  {cls.BOLD}Summary:{cls.RESET}")
        print(f"    • Missing GE areas (total): {analysis.total_missing_ge_areas}")
        print(f"    • Missing major requirements: {analysis.total_missing_major_reqs}")
        print(f"    • GE patterns needed: {', '.join(analysis.unique_ge_patterns)}")
        print(f"    • Total courses analyzed: {len(analysis.all_courses)}")
        
        if analysis.super_efficient:
            cls._print_super_efficient_courses(analysis.super_efficient, analysis.targets)
        
        if analysis.single_target_efficient:
            cls._print_single_target_courses(analysis.single_target_efficient, analysis.targets)
        
        if analysis.ge_only:
            cls._print_ge_only_courses(analysis.ge_only)
    
    @classmethod
    def _print_super_efficient_courses(cls, courses: list, targets: list):
        """
        Print super-efficient courses that help multiple targets.
        
        These are the MOST VALUABLE courses - they satisfy requirements
        at 2+ universities with a single course.
        """
        cls.print_header("🌟 SUPER EFFICIENT: COURSES HELPING MULTIPLE TARGETS")
        print(f"\n  {cls.GREEN}{cls.BOLD}These courses satisfy requirements at 2+ universities!{cls.RESET}")
        print(f"  {cls.DIM}Taking these first maximizes your transfer options.{cls.RESET}")
        print(f"\n  {cls.BOLD}Total: {len(courses)} super-efficient courses found{cls.RESET}")
        
        # Group by efficiency score to show priority
        by_efficiency = {}
        for course in courses:
            eff = course.efficiency_score
            if eff not in by_efficiency:
                by_efficiency[eff] = []
            by_efficiency[eff].append(course)
        
        # Sort by efficiency (highest first)
        priority = 1
        for eff_score in sorted(by_efficiency.keys(), reverse=True):
            eff_courses = by_efficiency[eff_score]
            eff_courses.sort(key=lambda c: c.code)  # Alphabetical within group
            
            if len(eff_courses) == 1:
                print(f"\n  {cls.BOLD}{cls.GREEN}★ Priority {priority}:{cls.RESET}")
                cls._print_multi_target_course(eff_courses[0], is_super=True)
            else:
                # Multiple courses with same efficiency - may be alternatives
                print(f"\n  {cls.BOLD}{cls.GREEN}★ Priority {priority}:{cls.RESET} {len(eff_courses)} courses with same efficiency")
                print(f"  {cls.DIM}(If they satisfy the same requirements, choose ONE){cls.RESET}")
                for course in eff_courses:
                    cls._print_multi_target_course(course, is_super=True)
            
            priority += 1
    
    @classmethod
    def _print_single_target_courses(cls, courses: list, targets: list):
        """
        Print courses that help exactly one target, GROUPED by requirement.
        
        GROUPING LOGIC:
        ---------------
        Courses that satisfy the same GE area + same university are likely
        OR alternatives for the same requirement. We group them together
        and show "Choose ONE" to make it clear the student doesn't need all.
        
        Example:
        - BIOL 3 (satisfies IGETC 5B + CSULB BIOL 200)
        - PHYS 3 (satisfies IGETC 5B + CSULB BIOL 207)
        These are alternatives → grouped as "Priority 1: Choose ONE"
        """
        cls.print_header("📘 SINGLE-TARGET COURSES (Grouped by Requirement)")
        print(f"\n  {cls.DIM}Courses grouped by what requirement they satisfy.{cls.RESET}")
        print(f"  {cls.DIM}If multiple courses are in the same group, you only need ONE.{cls.RESET}")
        
        # First, organize by target
        by_target = {}
        for course in courses:
            target_ids = list(course.major_satisfaction.keys())
            if target_ids:
                target_id = target_ids[0]
                if target_id not in by_target:
                    by_target[target_id] = []
                by_target[target_id].append(course)
        
        for target_id, target_courses in by_target.items():
            target_name = target_id
            for target in targets:
                if target.target_id == target_id:
                    uni_name = target.university.replace("California State University ", "CSU ")
                    uni_name = uni_name.replace("University of California ", "UC ")
                    target_name = f"{uni_name} - {target.major}"
                    break
            
            print(f"\n  {cls.BOLD}{cls.CYAN}══ For: {target_name} ══{cls.RESET}")
            
            # Group courses by what they satisfy to find OR alternatives
            # 
            # GROUPING LOGIC:
            # - Courses with SAME GE area = likely alternatives for same GE requirement
            #   (e.g., BIOL 3 and PHYS 3 both satisfy IGETC 5B for biology requirement)
            # - Courses with NO GE but SAME major requirement = alternatives
            #   (e.g., ENGL 1D and ENGL C1000 both satisfy UCLA's ENGCOMP 3)
            # - Courses with NO GE and DIFFERENT major requirements = separate
            #   (e.g., CS 56 for CECS 277 vs MATH 10 for CECS 228)
            #
            groups = {}
            for course in target_courses:
                if course.ge_satisfaction:
                    # Courses with GE: group by GE areas (likely alternatives)
                    ge_key = tuple(sorted(
                        f"{p}:{','.join(sorted(a))}" 
                        for p, a in course.ge_satisfaction.items()
                    ))
                    group_key = ("ge", ge_key)
                else:
                    # Courses with only major: group by what major requirement they satisfy
                    # This groups alternatives like ENGL 1D and ENGL C1000 for ENGCOMP 3
                    major_reqs = course.major_satisfaction.get(target_id, [])
                    if major_reqs:
                        # Group by the first major requirement (most have only one)
                        req_key = tuple(sorted(major_reqs))
                        group_key = ("major_only", req_key)
                    else:
                        group_key = ("major_only", course.code)
                
                if group_key not in groups:
                    groups[group_key] = []
                groups[group_key].append(course)
            
            # Sort groups by efficiency (highest first)
            # GE+Major courses come before Major-only courses
            def group_sort_key(item):
                group_key, courses = item
                best_course = courses[0]
                # Primary: efficiency score (higher is better)
                # Secondary: has GE (True comes before False)
                return (-best_course.efficiency_score, group_key[0] != "ge")
            
            sorted_groups = sorted(groups.items(), key=group_sort_key)
            
            priority = 1
            for group_key, group_courses in sorted_groups:
                # Sort courses within group alphabetically
                group_courses.sort(key=lambda c: c.code)
                
                if len(group_courses) == 1:
                    # Single course for this requirement
                    print(f"\n  {cls.BOLD}{cls.GREEN}Priority {priority}:{cls.RESET} Take this course")
                    cls._print_multi_target_course_compact(group_courses[0])
                else:
                    # Multiple alternatives - only need ONE
                    print(f"\n  {cls.BOLD}{cls.GREEN}Priority {priority}:{cls.RESET} Choose ONE of these {len(group_courses)} options")
                    print(f"  {cls.DIM}(All satisfy the same requirement - pick based on your preference){cls.RESET}")
                    
                    for i, course in enumerate(group_courses):
                        option_letter = chr(65 + i)  # A, B, C...
                        cls._print_multi_target_course_compact(course, option_label=option_letter)
                
                priority += 1
                
                # Limit to first 10 priority groups per target
                if priority > 10:
                    remaining = len(sorted_groups) - 10
                    if remaining > 0:
                        print(f"\n  {cls.DIM}... and {remaining} more requirement groups{cls.RESET}")
                    break
    
    @classmethod
    def _print_ge_only_courses(cls, courses: list):
        """Print courses that only satisfy GE requirements."""
        cls.print_header("📚 GE-ONLY COURSES (No Major Requirement)")
        print(f"\n  {cls.DIM}These satisfy GE requirements but no major requirements at your targets.{cls.RESET}")
        print(f"\n  {cls.BOLD}Total: {len(courses)} GE-only courses{cls.RESET}")
        
        by_area = {}
        for course in courses:
            for pattern, areas in course.ge_satisfaction.items():
                for area in areas:
                    key = f"{pattern} Area {area}"
                    if key not in by_area:
                        by_area[key] = []
                    if course not in by_area[key]:
                        by_area[key].append(course)
        
        for area_key in sorted(by_area.keys()):
            area_courses = by_area[area_key]
            print(f"\n  {cls.CYAN}{cls.BOLD}{area_key}:{cls.RESET} {len(area_courses)} courses")
            for course in area_courses[:5]:
                prereq_status = cls.GREEN + "✓" if course.prereqs_met else cls.RED + "⚠"
                print(f"    {prereq_status} {course.code}{cls.RESET} — {course.title[:40]}")
            
            if len(area_courses) > 5:
                print(f"    {cls.DIM}... and {len(area_courses) - 5} more{cls.RESET}")
    
    @classmethod
    def _print_multi_target_course(cls, course: MultiTargetCourse, is_super: bool):
        """Print a single course with its multi-target efficiency breakdown."""
        if course.prereqs_met:
            prereq_icon = "✓"
            prereq_status = "Ready to take"
            code_color = cls.GREEN
        elif course.prereqs_in_progress and not course.prereqs_missing:
            prereq_icon = "⏳"
            prereq_status = "Next semester"
            code_color = cls.YELLOW
        else:
            prereq_icon = "⚠"
            prereq_status = "Prereqs needed"
            code_color = cls.RED
        
        # Build a clear efficiency badge showing GE areas and Major targets separately
        ge_count = course.total_ge_areas
        major_count = course.total_major_reqs
        targets_count = course.total_targets_helped
        
        if is_super:
            eff_color = cls.GREEN
            # For super efficient courses (help 2+ universities)
            parts = []
            if ge_count > 0:
                parts.append(f"{ge_count} GE area{'s' if ge_count > 1 else ''}")
            if major_count > 0:
                parts.append(f"{major_count} major req{'s' if major_count > 1 else ''} across {targets_count} universities")
            eff_badge = f"★ Satisfies {' + '.join(parts)}"
        else:
            eff_color = cls.YELLOW
            # For single target courses
            parts = []
            if ge_count > 0:
                parts.append(f"{ge_count} GE")
            if major_count > 0:
                parts.append(f"{major_count} major req{'s' if major_count > 1 else ''}")
            eff_badge = f"Satisfies {' + '.join(parts)}"
        
        print(f"\n    {cls.BOLD}╭{'─' * 70}╮{cls.RESET}")
        print(f"    {cls.BOLD}│{cls.RESET} {code_color}{prereq_icon} {course.code}{cls.RESET} — {course.title[:45]}")
        print(f"    {cls.BOLD}│{cls.RESET} {cls.DIM}Units: {course.units} │ {prereq_status}{cls.RESET}")
        print(f"    {cls.BOLD}│{cls.RESET} {eff_color}{eff_badge}{cls.RESET}")
        
        if course.ge_satisfaction:
            ge_parts = []
            for pattern, areas in course.ge_satisfaction.items():
                ge_parts.append(f"{pattern}: {', '.join(areas)}")
            ge_display = " │ ".join(ge_parts)
            print(f"    {cls.BOLD}│{cls.RESET} {cls.CYAN}📚 GE:{cls.RESET} {ge_display}")
        
        if course.major_satisfaction:
            print(f"    {cls.BOLD}│{cls.RESET} {cls.MAGENTA}🎯 Major Requirements:{cls.RESET}")
            for target_name, reqs in course.efficiency_breakdown.get("major", {}).items():
                # Show full university name - just shorten "California State University" to "CSU"
                display_name = target_name.replace("California State University ", "CSU ")
                display_name = display_name.replace("University of California ", "UC ")
                
                reqs_display = ", ".join(r.split(":")[0] for r in reqs[:3])
                if len(reqs) > 3:
                    reqs_display += f" +{len(reqs) - 3} more"
                print(f"    {cls.BOLD}│{cls.RESET}   • {cls.BOLD}{display_name}{cls.RESET}")
                print(f"    {cls.BOLD}│{cls.RESET}     {cls.DIM}→ {reqs_display}{cls.RESET}")
        
        if course.prereqs_missing:
            prereqs_display = ", ".join(course.prereqs_missing[:3])
            if len(course.prereqs_missing) > 3:
                prereqs_display += f" +{len(course.prereqs_missing) - 3} more"
            print(f"    {cls.BOLD}│{cls.RESET}   {cls.RED}⚠ Needs: {prereqs_display}{cls.RESET}")
        elif course.prereqs_in_progress:
            in_progress = ", ".join(course.prereqs_in_progress[:2])
            print(f"    {cls.BOLD}│{cls.RESET}   {cls.YELLOW}⏳ Waiting for: {in_progress}{cls.RESET}")
        
        print(f"    {cls.BOLD}╰{'─' * 70}╯{cls.RESET}")
    
    @classmethod
    def _print_multi_target_course_compact(cls, course: MultiTargetCourse, option_label: str = None):
        """
        Print a course in a compact format for grouped display.
        
        Used when showing OR alternatives to keep the output readable.
        Shows option label (A, B, C) when multiple courses are alternatives.
        """
        if course.prereqs_met:
            prereq_icon = "✓"
            prereq_text = "Ready"
            code_color = cls.GREEN
        elif course.prereqs_in_progress and not course.prereqs_missing:
            prereq_icon = "⏳"
            prereq_text = "Next sem"
            code_color = cls.YELLOW
        else:
            prereq_icon = "⚠"
            prereq_text = "Prereqs needed"
            code_color = cls.RED
        
        # Option label for alternatives
        if option_label:
            label = f"{cls.CYAN}[{option_label}]{cls.RESET} "
        else:
            label = "    "
        
        # Build requirement summary
        ge_parts = []
        if course.ge_satisfaction:
            for pattern, areas in course.ge_satisfaction.items():
                ge_parts.append(f"{pattern}: {', '.join(areas)}")
        ge_str = " + ".join(ge_parts) if ge_parts else ""
        
        major_parts = []
        for target_name, reqs in course.efficiency_breakdown.get("major", {}).items():
            req_codes = [r.split(":")[0] for r in reqs]
            major_parts.extend(req_codes)
        major_str = ", ".join(major_parts) if major_parts else ""
        
        # Print compact format
        print(f"\n    {label}{code_color}{prereq_icon} {course.code}{cls.RESET} — {course.title[:40]}")
        print(f"        {cls.DIM}Units: {course.units} │ {prereq_text}{cls.RESET}")
        
        if ge_str:
            print(f"        {cls.CYAN}GE:{cls.RESET} {ge_str}")
        if major_str:
            print(f"        {cls.MAGENTA}Major:{cls.RESET} {major_str}")
        
        # Show prerequisites if needed
        if course.prereqs_missing:
            prereqs = ", ".join(course.prereqs_missing[:2])
            if len(course.prereqs_missing) > 2:
                prereqs += f" +{len(course.prereqs_missing) - 2} more"
            print(f"        {cls.RED}⚠ Needs: {prereqs}{cls.RESET}")
    
    @classmethod
    def print_target_audit_result(cls, audit_result: TargetAuditResult, target_num: int):
        """Print complete audit result for a single target."""
        target = audit_result.target
        
        print(f"\n{'═' * 70}")
        print(f"  {cls.BOLD}{cls.CYAN}TARGET {target_num}: {target.university.upper()}{cls.RESET}")
        print(f"  {cls.BOLD}Major:{cls.RESET} {target.major}")
        print(f"  {cls.BOLD}System:{cls.RESET} {'CSU' if target.target_system == 'csu' else 'UC'} (uses {audit_result.ge_pattern})")
        print(f"{'═' * 70}\n")
        
        cls.print_ge_audit(audit_result.ge_audit)
        cls.print_major_audit(audit_result.major_audit)
        
        if audit_result.cross_reference:
            cls.print_cross_reference(audit_result.cross_reference, audit_result.ge_pattern)
    
    # =========================================================================
    #  MAJOR DISCOVERY DISPLAY
    # =========================================================================
    
    @classmethod
    def print_major_discovery_header(cls):
        """Print the header for major discovery mode."""
        print(f"\n{cls.BOLD}{cls.CYAN}{'═' * 70}{cls.RESET}")
        print(f"  {cls.BOLD}{cls.GREEN}🔍 MAJOR DISCOVERY MODE{cls.RESET}")
        print(f"{cls.BOLD}{cls.CYAN}{'═' * 70}{cls.RESET}")
        print(f"\n  {cls.DIM}Finding majors that best match your completed courses...{cls.RESET}")
        print(f"  {cls.DIM}Scanning all universities and majors...{cls.RESET}\n")
    
    @classmethod
    def print_major_discovery_results(cls, matches: dict, total_scanned: int = 0):
        """
        Print the major discovery results.
        
        DISPLAY FORMAT:
        ---------------
        Shows two sections:
        1. Substantial majors (≥3 requirements) - main ranking
        2. Small majors (1-2 requirements) - shown separately at the end
        
        Each entry shows:
        - Rank number and progress bar
        - University and major name
        - Requirement progress (X/Y satisfied)
        - What's still needed
        
        Args:
            matches: Dict with "substantial" and "small" lists of MajorMatch objects
            total_scanned: Optional count of total majors scanned
        """
        # Handle both old list format and new dict format
        if isinstance(matches, list):
            substantial = matches
            small = []
        else:
            substantial = matches.get("substantial", [])
            small = matches.get("small", [])
        
        cls.print_header("🏆 TOP MATCHING MAJORS")
        
        if not substantial and not small:
            print(f"\n  {cls.YELLOW}No matching majors found.{cls.RESET}")
            print(f"  {cls.DIM}This could mean your courses don't satisfy any major requirements yet.{cls.RESET}")
            return
        
        print(f"\n  {cls.DIM}Based on your completed and in-progress courses:{cls.RESET}")
        if total_scanned:
            print(f"  {cls.DIM}(Scanned {total_scanned} majors across all universities){cls.RESET}")
        print()
        
        # Print substantial majors (main list)
        for i, match in enumerate(substantial, 1):
            cls._print_major_match(i, match)
        
        # Print small majors in a separate section
        if small:
            print(f"\n  {cls.DIM}{'─' * 66}{cls.RESET}")
            print(f"\n  {cls.BOLD}{cls.YELLOW}📌 SMALL MAJORS (1-2 requirements){cls.RESET}")
            print(f"  {cls.DIM}These may be minors or have limited articulation data:{cls.RESET}\n")
            
            for i, match in enumerate(small, 1):
                cls._print_major_match(i, match)
        
        print(f"\n  {cls.DIM}{'─' * 66}{cls.RESET}")
        print(f"  {cls.DIM}Tip: These are majors where you've already satisfied requirements.{cls.RESET}")
        print(f"  {cls.DIM}Select one to see a full audit of what's still needed.{cls.RESET}")
    
    @classmethod
    def _print_major_match(cls, rank: int, match):
        """
        Print a single major match result.
        
        VISUAL FORMAT:
        --------------
        Shows both absolute progress and percentage for clarity.
        Absolute progress is what really matters (5/6 > 1/1 even though 83% < 100%)
        
        #1  ████████░░ 5/6 reqs done (83%)
            UCLA - Computer Science/B.S.
            ✓ 5 satisfied, ⏳ 1 in progress
            → Need: MATH 15, PHYSCS 22
        """
        # Create progress bar (10 chars)
        filled = int(match.percentage / 10)
        empty = 10 - filled
        progress_bar = "█" * filled + "░" * empty
        
        # Color based on percentage
        if match.percentage >= 75:
            bar_color = cls.GREEN
        elif match.percentage >= 50:
            bar_color = cls.YELLOW
        else:
            bar_color = cls.CYAN
        
        # Shorten university name for display
        uni_short = match.university.replace("California State University ", "CSU ")
        uni_short = uni_short.replace("University of California ", "UC ")
        
        # Calculate effective progress (for display)
        effective = match.satisfied_count
        if match.in_progress_count > 0:
            effective_str = f"{match.satisfied_count}+{match.in_progress_count}"
        else:
            effective_str = str(match.satisfied_count)
        
        # Print the match - emphasize absolute count over percentage
        print(f"  {cls.BOLD}#{rank:2}{cls.RESET}  {bar_color}{progress_bar}{cls.RESET} "
              f"{cls.BOLD}{effective_str}/{match.total_requirements} reqs{cls.RESET} "
              f"{cls.DIM}({match.percentage:.0f}%){cls.RESET}")
        
        print(f"      {cls.CYAN}{uni_short}{cls.RESET} - {cls.BOLD}{match.major}{cls.RESET}")
        
        # Status line
        status_parts = []
        if match.satisfied_count > 0:
            status_parts.append(f"{cls.GREEN}✓ {match.satisfied_count} done{cls.RESET}")
        if match.in_progress_count > 0:
            status_parts.append(f"{cls.YELLOW}⏳ {match.in_progress_count} in progress{cls.RESET}")
        if match.missing_count > 0:
            status_parts.append(f"{cls.DIM}{match.missing_count} needed{cls.RESET}")
        
        print(f"      {', '.join(status_parts)}")
        
        # Show what's needed (if missing)
        if match.missing_courses:
            missing_str = ", ".join(match.missing_courses)
            print(f"      {cls.DIM}→ Need: {missing_str}{cls.RESET}")
        
        print()  # Blank line between entries

