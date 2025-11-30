"""
Transfer Counselor - Main Orchestrator.

This module contains the TransferCounselor class that connects the
algorithm layer to the presentation layer.

NOTE: Don't run this file directly. Run from parent directory:
    cd CollegeTransfer
    python3 -m counseling
"""

import json

from .config import DATA_DIR, academic_year_to_code
from .data import DataLoader, TranscriptParser
from .engines import (
    GEAuditEngine,
    MajorAuditEngine,
    CourseRecommendationEngine,
    MultiTargetEngine,
)
from .models import TargetDefinition, MultiTargetAnalysis
from .ui import TerminalDisplay


class TransferCounselor:
    """
    Main interface for the transfer counseling system.
    
    ═══════════════════════════════════════════════════════════════════════════
    ROLE: ORCHESTRATOR
    ═══════════════════════════════════════════════════════════════════════════
    
    This class connects the Algorithm layer to the Presentation layer:
    
    1. Receives user input (transcript, university, major, entry date)
    2. Calls Algorithm layer methods to get audit results (pure data)
    3. Passes that data to Presentation layer for display
    
    TO CHANGE THE UI:
    -----------------
    Replace `self.display = TerminalDisplay()` with your custom display class.
    
    Example for web:
        self.display = WebDisplay()
    
    Example for API:
        # Don't call display methods - just return the data
        return {
            "student": student_state,
            "ge_audit": ge_result,
            "major_audit": major_result,
            "recommendations": cross_ref
        }
    
    ═══════════════════════════════════════════════════════════════════════════
    
    USAGE:
        counselor = TransferCounselor()
        
        # Run a full audit with terminal display
        result = counselor.run_audit(
            transcript_path="path/to/transcript.json",
            university="California State University Long Beach",
            major="Computer Science",
            entry_year=2023,
            entry_term="Fall"
        )
        
        # Or just query available options (no display needed)
        universities = counselor.list_universities()
        majors = counselor.list_majors("California State University Long Beach")
    """
    
    def __init__(self):
        # Initialize all components with shared DataLoader
        self.loader = DataLoader()
        self.ge_engine = GEAuditEngine(self.loader)
        self.major_engine = MajorAuditEngine(self.loader)
        self.recommendation_engine = CourseRecommendationEngine(self.loader)
        
        # Multi-target engine for cross-referencing across universities
        self.multi_target_engine = MultiTargetEngine(
            self.loader, self.ge_engine, self.major_engine, self.recommendation_engine
        )
        
        self.display = TerminalDisplay()
    
    def run_audit(self, transcript_path: str, university: str, major: str,
                  entry_year: int, entry_term: str, target_system: str = "csu"):
        """
        Run a complete transfer audit and display results.
        
        This is the main entry point for the counseling system. It:
        1. Loads and parses the student's transcript
        2. Runs GE audit (IGETC or Cal-GETC based on entry date)
        3. Runs major requirements audit
        4. Displays all results in terminal
        
        Args:
            transcript_path: Path to the student's transcript JSON file
            university: Target university name (must match articulation filename)
            major: Target major name (case-insensitive search)
            entry_year: Year student started at community college
            entry_term: Term of first enrollment (Fall, Spring, Summer, Winter)
            target_system: "csu" or "uc" (affects Area 1 requirements)
        
        Returns:
            Dict with student info, ge_audit, and major_audit results
        """
        # Compute year_code from entry_year
        year_code = academic_year_to_code(entry_year)
        
        # Ensure we have data for this year
        available_years = self.loader.get_available_year_codes()
        if year_code not in available_years and available_years:
            year_code = max(available_years)
        
        # Create TranscriptParser with the appropriate year_code
        transcript_parser = TranscriptParser(self.loader, year_code)
        
        # STEP 1: Load and parse transcript
        with open(transcript_path, "r") as f:
            transcript_data = json.load(f)
        
        student_state = transcript_parser.parse(transcript_data)
        
        # STEP 2: Display student info
        self.display.print_student_info(student_state["student"])
        self._print_course_summary(student_state)
        
        # STEP 3: Run GE audit
        ge_result = self.ge_engine.audit(student_state, entry_year, entry_term, target_system)
        self.display.print_ge_audit(ge_result)
        
        # STEP 4: Run major audit
        major_result = self.major_engine.audit(student_state, university, major)
        self.display.print_major_audit(major_result)
        
        # STEP 5: Print summary
        self.display.print_summary(ge_result, major_result)
        
        # STEP 6: Cross-reference GE + Major
        if not ge_result.get("overall_satisfied", True) or not major_result.get("overall_satisfied", True):
            cross_ref = self.recommendation_engine.cross_reference_ge_and_major(
                ge_result, major_result, student_state, year_code
            )
            if cross_ref:
                self.display.print_cross_reference(cross_ref, ge_result.get("pattern_name", "IGETC"))
        
        # STEP 7: Generate and display recommendations
        if not major_result.get("overall_satisfied", True):
            major_recs = self.recommendation_engine.recommend_major_courses(
                major_result, student_state
            )
            self.display.print_major_recommendations(major_recs)
        
        if not ge_result.get("overall_satisfied", True):
            ge_recs = self.recommendation_engine.recommend_ge_courses(
                ge_result, student_state, year_code
            )
            self.display.print_ge_recommendations(ge_recs, ge_result.get("pattern_name", "IGETC"))
        
        return {
            "student": student_state["student"],
            "ge_audit": ge_result,
            "major_audit": major_result,
        }
    
    def _print_course_summary(self, student_state: dict):
        """Print a quick summary of the student's course status."""
        completed = student_state["completed"]
        in_progress = student_state["in_progress"]
        failed = student_state["failed"]
        
        self.display.print_subheader("Course Summary")
        
        total_units = sum(c.units for c in completed)
        print(f"  {self.display.GREEN}Completed:{self.display.RESET} {len(completed)} courses ({total_units:.1f} units)")
        print(f"  {self.display.YELLOW}In Progress:{self.display.RESET} {len(in_progress)} courses")
        if failed:
            print(f"  {self.display.RED}Failed/Withdrawn:{self.display.RESET} {len(failed)} courses")
    
    def list_universities(self) -> list:
        """List all available universities with articulation agreements."""
        return self.loader.list_available_universities()
    
    def list_majors(self, university: str) -> list:
        """List all majors for a specific university."""
        return self.major_engine.list_majors(university)
    
    def run_multi_target_audit(self, transcript_path: str, targets: list,
                               entry_year: int, entry_term: str) -> MultiTargetAnalysis:
        """
        Run a complete audit against MULTIPLE university/major targets.
        
        Args:
            transcript_path: Path to the student's transcript JSON file
            targets: List of TargetDefinition objects
            entry_year: Year student started at community college
            entry_term: Term of first enrollment
        
        Returns:
            MultiTargetAnalysis with complete results for all targets
        """
        # Compute year_code from entry_year
        year_code = academic_year_to_code(entry_year)
        
        # Ensure we have data for this year
        available_years = self.loader.get_available_year_codes()
        if year_code not in available_years and available_years:
            year_code = max(available_years)
        
        # Create TranscriptParser
        transcript_parser = TranscriptParser(self.loader, year_code)
        
        # Load and parse transcript
        with open(transcript_path, "r") as f:
            transcript_data = json.load(f)
        
        student_state = transcript_parser.parse(transcript_data)
        
        # STEP 1: Display student info
        self.display.print_student_info(student_state["student"])
        self._print_course_summary(student_state)
        
        # STEP 2: Run multi-target analysis
        analysis = self.multi_target_engine.analyze_targets(
            targets, student_state, entry_year, entry_term, year_code
        )
        
        # STEP 3: Display individual target results
        for i, audit_result in enumerate(analysis.target_audits, 1):
            self.display.print_target_audit_result(audit_result, i)
        
        # STEP 4: Display unified multi-target analysis
        if len(targets) > 1:
            self.display.print_multi_target_analysis(analysis)
        
        return analysis

