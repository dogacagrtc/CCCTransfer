"""
Multi-target analysis data models.

These dataclasses support auditing against MULTIPLE university/major targets
simultaneously, enabling cross-referencing across all targets.
"""

from dataclasses import dataclass


@dataclass
class TargetDefinition:
    """
    Defines a single university/major target for the student.
    
    A student might have multiple targets:
    - CSULB Computer Science
    - CSUN Computer Science  
    - UCLA Computer Science
    
    Each target has its own GE pattern (IGETC for CSU, potentially different for UC)
    and its own major requirements.
    """
    university: str                        # Full university name
    major: str                             # Major name
    target_system: str                     # "csu" or "uc" - determines GE pattern
    target_id: str = ""                    # Unique ID for this target (auto-generated if empty)
    
    def __post_init__(self):
        if not self.target_id:
            # Generate a short ID from university and major
            uni_short = "".join(word[0] for word in self.university.split()[-2:])
            major_short = self.major[:3].upper()
            self.target_id = f"{uni_short}_{major_short}"


@dataclass
class TargetAuditResult:
    """
    Complete audit result for a single university/major target.
    
    Contains:
    - GE audit (IGETC or Cal-GETC)
    - Major audit
    - Cross-reference (courses satisfying both GE and major for THIS target)
    """
    target: TargetDefinition               # The target being audited
    ge_pattern: str                        # "IGETC" or "CalGETC"
    ge_audit: dict                         # Result from GEAuditEngine.audit()
    major_audit: dict                      # Result from MajorAuditEngine.audit()
    cross_reference: list                  # List of EfficiencyGroup for this target
    missing_ge_areas: list                 # List of missing GE area codes
    missing_major_reqs: list               # List of missing major requirement descriptions


@dataclass 
class MultiTargetCourse:
    """
    A course analyzed across ALL student targets.
    
    ═══════════════════════════════════════════════════════════════════════════
    PURPOSE
    ═══════════════════════════════════════════════════════════════════════════
    
    This is the KEY data structure for multi-major efficiency analysis.
    
    For each SMC course, we track:
    1. Which GE areas it satisfies (IGETC/Cal-GETC)
    2. Which major requirements it satisfies at EACH university
    3. Total efficiency score across ALL targets
    
    Example:
        BIOL 3 at SMC:
        - Satisfies IGETC 5B (counts for both CSU targets)
        - Satisfies CSULB CS requirement: BIOL 200
        - Satisfies CSUN CS requirement: BIOL 101
        - Efficiency: 3 (1 GE area + 2 major requirements)
    
    ═══════════════════════════════════════════════════════════════════════════
    """
    code: str                              # Course code (e.g., "BIOL 3")
    title: str                             # Course title
    units: float                           # Course units
    prereqs_met: bool                      # True if all prereqs are satisfied
    prereqs_missing: list                  # List of unmet prerequisite codes
    prereqs_in_progress: list              # Prerequisites currently in progress
    
    # GE SATISFACTION - which GE areas does this course satisfy?
    ge_satisfaction: dict                  # {pattern_key: [area_codes]}
    
    # MAJOR SATISFACTION - which major requirements at each university?
    major_satisfaction: dict               # {target_id: ["BIOL 200: General Biology", ...]}
    
    # EFFICIENCY BREAKDOWN
    total_ge_areas: int                    # Count of unique GE areas satisfied
    total_major_reqs: int                  # Count of major requirements across ALL targets
    total_targets_helped: int              # How many targets does this course help?
    efficiency_score: int                  # Total: ge_areas + major_reqs across all targets
    
    # DETAILED BREAKDOWN for UI
    efficiency_breakdown: dict             # Detailed breakdown for display
    
    def __lt__(self, other):
        """Sort by efficiency (highest first), then by targets helped, then alphabetically."""
        if self.efficiency_score != other.efficiency_score:
            return self.efficiency_score > other.efficiency_score
        if self.total_targets_helped != other.total_targets_helped:
            return self.total_targets_helped > other.total_targets_helped
        return self.code < other.code


@dataclass
class MultiTargetAnalysis:
    """
    Complete analysis across ALL student targets.
    
    ═══════════════════════════════════════════════════════════════════════════
    STRUCTURE
    ═══════════════════════════════════════════════════════════════════════════
    
    This is the top-level result containing:
    
    1. INDIVIDUAL TARGET AUDITS
       For each target (e.g., CSULB CS, CSUN CS, UCLA CS):
       - GE audit for that target's system
       - Major audit
       - Cross-reference for that target alone
    
    2. UNIFIED COURSE LIST
       ALL courses that help with ANY target, ranked by:
       - How many total requirements they satisfy
       - How many targets they help
       - Whether prerequisites are met
    
    3. SUPER EFFICIENT COURSES
       Courses that help with MULTIPLE targets simultaneously
       (e.g., satisfies both CSULB major AND CSUN major AND GE)
    
    ═══════════════════════════════════════════════════════════════════════════
    """
    targets: list                          # List of TargetDefinition
    target_audits: list                    # List of TargetAuditResult (one per target)
    
    # Unified course analysis
    all_courses: list                      # List of MultiTargetCourse, sorted by efficiency
    
    # Categorized by efficiency level
    super_efficient: list                  # Courses helping 2+ targets (multi-target winners)
    single_target_efficient: list          # Courses helping exactly 1 target
    ge_only: list                          # Courses that only satisfy GE (no major)
    
    # Summary statistics
    total_missing_ge_areas: int            # Union of all missing GE areas
    total_missing_major_reqs: int          # Sum of all missing major requirements
    unique_ge_patterns: list               # List of unique GE patterns needed

