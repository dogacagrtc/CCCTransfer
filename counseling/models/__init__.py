"""
Data models for the counseling system.

This package contains all dataclasses and enums used throughout the system.
These serve as "contracts" between different parts of the system.
"""

from .course import Course, CourseStatus
from .audit import AreaAuditResult, RequirementAuditResult
from .recommendation import (
    CourseOption,
    AreaRecommendation,
    MajorCourseItem,
    MajorRecommendation,
    CrossReferencedCourse,
    EfficiencyGroup,
)
from .multi_target import (
    TargetDefinition,
    TargetAuditResult,
    MultiTargetCourse,
    MultiTargetAnalysis,
)

__all__ = [
    # Course models
    "Course",
    "CourseStatus",
    # Audit results
    "AreaAuditResult",
    "RequirementAuditResult",
    # Recommendation models
    "CourseOption",
    "AreaRecommendation",
    "MajorCourseItem",
    "MajorRecommendation",
    "CrossReferencedCourse",
    "EfficiencyGroup",
    # Multi-target models
    "TargetDefinition",
    "TargetAuditResult",
    "MultiTargetCourse",
    "MultiTargetAnalysis",
]

