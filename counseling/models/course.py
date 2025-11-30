"""
Course data models.

Contains the Course dataclass and CourseStatus enum that represent
a student's academic record.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CourseStatus(Enum):
    """
    Possible states for a course on a student's record.
    
    COMPLETED: Student passed the course with a qualifying grade
    IN_PROGRESS: Student is currently enrolled (no grade yet)
    FAILED: Student did not pass (F, NP, W, etc.)
    NOT_TAKEN: Course has never been attempted (used for gap analysis)
    """
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    FAILED = "failed"
    NOT_TAKEN = "not_taken"


@dataclass
class Course:
    """
    Represents a single course from the student's transcript.
    
    This is the core data unit that flows through the system. We enrich
    the raw transcript data with GE attributes from raw_GE files
    because the transcript's pre-computed GE codes were found to be incomplete.
    
    Attributes:
        code: Course code as it appears in SMC catalog (e.g., "PHYSCS 21")
        title: Human-readable course title
        units: Credit units earned or enrolled
        grade: Letter grade or None if in-progress
        term: Academic term (e.g., "Fall 2023")
        status: CourseStatus enum value
        igetc: List of IGETC area codes this course satisfies (from catalog)
        cal_getc: List of Cal-GETC area codes this course satisfies (from catalog)
        csu_ge: List of CSU GE-Breadth codes this course satisfies (from catalog)
    """
    code: str
    title: str
    units: float
    grade: Optional[str]
    term: str
    status: CourseStatus
    # GE attributes from raw_GE files (source of truth)
    # We store all three patterns because student might need different audits
    igetc: list = field(default_factory=list)
    cal_getc: list = field(default_factory=list)
    csu_ge: list = field(default_factory=list)

