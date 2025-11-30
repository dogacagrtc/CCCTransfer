"""
Transcript parsing.

This module handles parsing student transcripts and enriching them
with catalog data.
"""

from ..config import PASSING_GRADES, FAILING_GRADES
from ..models import Course, CourseStatus
from .loader import DataLoader


class TranscriptParser:
    """
    Parses student transcript and enriches with catalog data.
    
    KEY RESPONSIBILITY: Convert raw transcript JSON into structured Course
    objects with accurate GE attributes from the raw_GE files.
    
    WHY ENRICHMENT IS NEEDED:
    The transcript's ge_normalized field is pre-computed but was found to
    be incomplete in testing. For example, PHYSCS 21 transcript showed only
    ["5A"] but the raw_GE files correctly show ["5A", "5C"]. The "5C" is crucial
    for the lab requirement. We must use raw_GE data for accuracy.
    
    DUPLICATE HANDLING:
    Students sometimes retake courses. We keep the "best" outcome:
    - If completed, keep completed (ignore later failed attempts)
    - If in-progress, keep in-progress over failed
    - This prevents a failed retake from hiding a passing grade
    """
    
    def __init__(self, data_loader: DataLoader, year_code: int = 76):
        self.loader = data_loader
        self.year_code = year_code  # Default to 2025-2026
    
    def parse(self, transcript_data: dict) -> dict:
        """
        Parse transcript and return structured student state.
        
        This is the main entry point for transcript processing. It takes
        the raw JSON and produces a clean, categorized set of courses.
        
        Args:
            transcript_data: Raw parsed transcript JSON
        
        Returns:
            {
                "student": {name, institution, ...},
                "completed": [Course, ...],    # Passed courses
                "in_progress": [Course, ...],  # Currently enrolled
                "failed": [Course, ...],       # Failed/withdrawn
                "all_courses": {code: Course}  # Quick lookup by code
            }
        """
        student_info = transcript_data.get("student", {})
        courses_raw = transcript_data.get("courses", [])
        
        completed = []
        in_progress = []
        failed = []
        all_courses = {}
        
        for c in courses_raw:
            course = self._parse_course(c)
            
            # DUPLICATE HANDLING: If we've seen this course before,
            # keep the better outcome (completed > in_progress > failed)
            if course.code in all_courses:
                existing = all_courses[course.code]
                # If already completed, skip any later attempts
                if existing.status == CourseStatus.COMPLETED:
                    continue
                # If new one is completed, replace the old one
                if course.status == CourseStatus.COMPLETED:
                    # Remove from previous category list
                    if existing.status == CourseStatus.IN_PROGRESS:
                        in_progress = [x for x in in_progress if x.code != course.code]
                    elif existing.status == CourseStatus.FAILED:
                        failed = [x for x in failed if x.code != course.code]
                # If existing is in_progress and new is failed, keep in_progress
                elif existing.status == CourseStatus.IN_PROGRESS and course.status == CourseStatus.FAILED:
                    continue
            
            # Store/update the course
            all_courses[course.code] = course
            
            # Categorize by status
            if course.status == CourseStatus.COMPLETED:
                completed.append(course)
            elif course.status == CourseStatus.IN_PROGRESS:
                in_progress.append(course)
            elif course.status == CourseStatus.FAILED:
                failed.append(course)
        
        return {
            "student": student_info,
            "completed": completed,
            "in_progress": in_progress,
            "failed": failed,
            "all_courses": all_courses,
        }
    
    def _parse_course(self, course_data: dict) -> Course:
        """
        Parse a single course entry from transcript.
        
        Determines course status based on grade and enriches with
        GE attributes from the raw_GE files.
        """
        code = course_data.get("code", "")
        grade = course_data.get("grade")
        status_str = course_data.get("status", "")
        
        # STATUS DETERMINATION LOGIC:
        # 1. Explicit "in_progress" status OR no grade = currently enrolled
        # 2. Grade in PASSING_GRADES = completed successfully
        # 3. Grade in FAILING_GRADES = not completed
        # 4. Unknown grade = treat as failed (safe default, don't assume passing)
        if status_str == "in_progress" or grade is None:
            status = CourseStatus.IN_PROGRESS
        elif grade in PASSING_GRADES:
            status = CourseStatus.COMPLETED
        elif grade in FAILING_GRADES:
            status = CourseStatus.FAILED
        else:
            # Unknown grade - treat as failed to be safe
            status = CourseStatus.FAILED
        
        # CRITICAL: Get GE attributes from raw_GE files (source of truth)
        ge_attrs = self.loader.get_course_ge_attributes(code, self.year_code)
        
        return Course(
            code=code,
            title=course_data.get("title", ""),
            units=course_data.get("units_completed", 0.0) or course_data.get("units_enrolled", 0.0),
            grade=grade,
            term=course_data.get("term", ""),
            status=status,
            igetc=ge_attrs["IGETC"],
            cal_getc=ge_attrs["CALGETC"],
            csu_ge=ge_attrs["CSUGE"],
        )

