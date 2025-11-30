"""
Course recommendation data models.

Contains dataclasses for representing course recommendations,
efficiency analysis, and cross-referencing results.
"""

from dataclasses import dataclass, field


@dataclass
class CourseOption:
    """
    Represents a course option the student can take to satisfy a requirement.
    
    Includes prerequisite information to help students plan their schedule.
    """
    code: str                              # Course code (e.g., "BIOL 3")
    title: str                             # Course title
    units: float                           # Course units
    prereqs_met: bool                      # True if all prereqs are satisfied
    prereqs_missing: list                  # List of unmet prerequisite codes
    prereqs_in_progress: list              # Prerequisites currently in progress
    coreqs: list                           # Corequisite courses
    advisories: list                       # Advisory (recommended) courses
    semesters_away: int                    # How many semesters until eligible (0 = now)
    ge_areas: list = field(default_factory=list)  # GE areas this course satisfies


@dataclass
class AreaRecommendation:
    """
    Recommendation for a single GE area with available course options.
    """
    area_code: str
    area_name: str
    courses_needed: int
    available_courses: list  # List of CourseOption objects
    subarea_code: str = ""   # If this is for a specific subarea


@dataclass
class MajorCourseItem:
    """
    A single university course item within a requirement with its SMC options.
    """
    university_course: dict                # University course info (code, title)
    smc_options: list                      # List of CourseOption objects for this uni course
    has_articulation: bool                 # True if SMC has equivalent courses


@dataclass
class MajorRecommendation:
    """
    Recommendation for a major requirement, preserving the OR/AND logic.
    
    A requirement might be:
    - ONE_OF: Choose any one item (OR logic) - e.g., BIOL 200 OR BIOL 205 OR BIOL 207
    - ALL_OF: Complete all items (AND logic) - e.g., MATH 7 AND MATH 8 AND CS 17
    - N_OF: Complete N items from the list
    """
    requirement_id: str
    requirement_num: int                   # Requirement number (1, 2, 3, ...)
    logic: str                             # "ONE_OF", "ALL_OF", "N_OF"
    logic_display: str                     # Human-readable: "Choose ONE", "Complete ALL"
    min_required: int                      # For N_OF: minimum number required
    items: list                            # List of MajorCourseItem objects


@dataclass
class CrossReferencedCourse:
    """
    A course that satisfies BOTH GE areas AND major requirements.
    
    These are the most efficient courses for students to take because
    they "kill two birds with one stone" - satisfying multiple requirements
    with a single course.
    """
    code: str                              # Course code (e.g., "BIOL 3")
    title: str                             # Course title
    units: float                           # Course units
    prereqs_met: bool                      # True if all prereqs are satisfied
    prereqs_missing: list                  # List of unmet prerequisite codes
    prereqs_in_progress: list              # Prerequisites currently in progress
    ge_areas_satisfied: list               # List of GE area codes this satisfies
    major_requirements_satisfied: list     # List of major requirement descriptions
    requirement_info: list                 # Info about requirement logic
    efficiency_score: int                  # Total number of requirements satisfied
    
    def __lt__(self, other):
        """For sorting: higher efficiency first, then alphabetically by code."""
        if self.efficiency_score != other.efficiency_score:
            return self.efficiency_score > other.efficiency_score  # Higher is better
        return self.code < other.code  # Alphabetical


@dataclass
class EfficiencyGroup:
    """
    A group of courses with the same efficiency score.
    
    All courses in this group satisfy the exact same number of requirements,
    so the student should choose based on personal preference.
    
    IMPORTANT: This now tracks requirement-level OR logic!
    If BIOL 3 and PHYS 3 are both options for the same ONE_OF requirement,
    this is clearly indicated so students know taking either one satisfies it.
    """
    efficiency_score: int                  # Number of requirements satisfied
    ge_areas: list                         # GE areas these courses satisfy
    major_requirements: list               # Major requirements these courses satisfy
    requirement_info: list                 # Info about requirement logic
    courses: list                          # List of CrossReferencedCourse objects
    description: str                       # Human-readable description
    is_or_group: bool = False              # True if courses are OR alternatives

