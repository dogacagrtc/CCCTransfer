"""
Audit result data models.

Contains dataclasses for representing the results of GE and Major audits.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AreaAuditResult:
    """
    Result of auditing a single GE area or subarea.
    
    This captures the complete state of a GE area including what's done,
    what's pending, and whether the requirement is satisfied.
    
    Example for Area 5 (Sciences):
        code: "5"
        name: "Physical and Biological Sciences"
        required_courses: 2
        required_units: 7
        completed_courses: [PHYSCS 21]
        pending_courses: []
        is_satisfied: False (missing biological science)
        notes: "Subareas: 5A ✓ | 5B ✗ | 5C ✓"
    """
    code: str
    name: str
    required_courses: int
    required_units: float
    completed_courses: list  # List of Course objects that satisfy this area
    pending_courses: list    # In-progress courses that could satisfy this area
    is_satisfied: bool       # True only if fully satisfied (not pending)
    notes: str = ""          # Additional context, subarea details


@dataclass
class RequirementAuditResult:
    """
    Result of auditing a single major requirement group.
    
    Major requirements come in different flavors:
    - ALL_OF: Complete all courses in the list (e.g., "Complete CS 20A AND CS 20B")
    - ONE_OF: Complete any one course from the list (e.g., "Take CS 52 OR CS 55")
    - N_OF: Complete at least N courses from the list (e.g., "Choose 2 from...")
    
    This structure captures the logic type and tracks satisfaction status.
    """
    requirement_id: str           # Unique ID from articulation data
    logic: str                    # "ALL_OF", "ONE_OF", "N_OF"
    min_required: Optional[int]   # For N_OF logic, how many needed
    items: list                   # Detailed breakdown: satisfied, pending, missing
    satisfied_by: list            # List of course codes that satisfy this
    pending: list                 # In-progress courses that would satisfy
    is_satisfied: bool            # Fully satisfied right now
    is_pending: bool              # Will be satisfied if pending courses complete

