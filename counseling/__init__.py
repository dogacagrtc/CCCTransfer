"""
Student Transfer Counseling Package
====================================

A precise counseling system for California community college transfer students.

ARCHITECTURE OVERVIEW
---------------------

┌─────────────────────────────────────────────────────────────────────────┐
│                         ALGORITHM LAYER                                  │
│        (Pure logic - returns data structures, NO UI/printing)           │
│                                                                         │
│  ┌─────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │ DataLoader  │  │TranscriptParser │  │ CourseRecommendationEngine  │  │
│  │  (I/O)      │  │ (parsing)       │  │ (cross-reference logic)     │  │
│  └─────────────┘  └─────────────────┘  └─────────────────────────────┘  │
│                                                                         │
│  ┌─────────────────────────┐  ┌─────────────────────────────────────┐  │
│  │     GEAuditEngine       │  │       MajorAuditEngine              │  │
│  │ (IGETC/Cal-GETC logic)  │  │   (articulation logic)             │  │
│  └─────────────────────────┘  └─────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   │ Returns dataclasses
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      PRESENTATION LAYER                                  │
│           (UI only - can be swapped without touching algorithm)         │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    TerminalDisplay                               │   │
│  │  • Formats and prints to console                                 │   │
│  │  • Can be replaced with: WebDisplay, PDFDisplay, APIResponse    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     TransferCounselor                                    │
│          (Orchestrator - connects algorithm to presentation)            │
└─────────────────────────────────────────────────────────────────────────┘

PACKAGE STRUCTURE
-----------------

counseling/
├── __init__.py          # This file - main exports
├── config.py            # Configuration constants
├── counselor.py         # TransferCounselor orchestrator
├── cli.py               # Command-line interface
│
├── models/              # Data classes and enums
│   ├── course.py        # Course, CourseStatus
│   ├── audit.py         # AreaAuditResult, RequirementAuditResult
│   ├── recommendation.py # CourseOption, EfficiencyGroup, etc.
│   └── multi_target.py  # TargetDefinition, MultiTargetCourse, etc.
│
├── data/                # Data loading and parsing
│   ├── loader.py        # DataLoader
│   └── parser.py        # TranscriptParser
│
├── engines/             # Audit and recommendation engines
│   ├── ge_audit.py      # GEAuditEngine
│   ├── major_audit.py   # MajorAuditEngine
│   ├── recommendation.py # CourseRecommendationEngine
│   └── multi_target.py  # MultiTargetEngine
│
└── ui/                  # User interface implementations
    └── terminal.py      # TerminalDisplay

USAGE
-----

Basic usage:

    from counseling import TransferCounselor, TargetDefinition
    
    counselor = TransferCounselor()
    
    # Single target audit
    counselor.run_audit(
        transcript_path="transcript.json",
        university="California State University Long Beach",
        major="Computer Science",
        entry_year=2023,
        entry_term="Fall"
    )
    
    # Multi-target audit
    targets = [
        TargetDefinition("California State University Long Beach", "Computer Science", "csu"),
        TargetDefinition("California State University Northridge", "Computer Science", "csu"),
    ]
    counselor.run_multi_target_audit(
        transcript_path="transcript.json",
        targets=targets,
        entry_year=2023,
        entry_term="Fall"
    )

Running from command line:

    python -m counseling

"""

# Version
__version__ = "2.0.0"

# Main exports
from .counselor import TransferCounselor
from .cli import main

# Model exports (for programmatic use)
from .models import (
    Course,
    CourseStatus,
    AreaAuditResult,
    RequirementAuditResult,
    CourseOption,
    AreaRecommendation,
    MajorCourseItem,
    MajorRecommendation,
    CrossReferencedCourse,
    EfficiencyGroup,
    TargetDefinition,
    TargetAuditResult,
    MultiTargetCourse,
    MultiTargetAnalysis,
)

# Engine exports (for advanced use)
from .engines import (
    GEAuditEngine,
    MajorAuditEngine,
    CourseRecommendationEngine,
    MultiTargetEngine,
)

# Data exports
from .data import DataLoader, TranscriptParser

# UI exports
from .ui import TerminalDisplay

# Configuration exports
from .config import (
    DATA_DIR,
    CLEAN_MAJORS_DIR,
    RAW_GE_DIR,
    PASSING_GRADES,
    FAILING_GRADES,
    CAL_GETC_START_YEAR,
    CAL_GETC_START_TERM,
    academic_year_to_code,
    year_code_to_academic_year,
)

__all__ = [
    # Version
    "__version__",
    # Main entry points
    "TransferCounselor",
    "main",
    # Models
    "Course",
    "CourseStatus",
    "AreaAuditResult",
    "RequirementAuditResult",
    "CourseOption",
    "AreaRecommendation",
    "MajorCourseItem",
    "MajorRecommendation",
    "CrossReferencedCourse",
    "EfficiencyGroup",
    "TargetDefinition",
    "TargetAuditResult",
    "MultiTargetCourse",
    "MultiTargetAnalysis",
    # Engines
    "GEAuditEngine",
    "MajorAuditEngine",
    "CourseRecommendationEngine",
    "MultiTargetEngine",
    # Data
    "DataLoader",
    "TranscriptParser",
    # UI
    "TerminalDisplay",
    # Config
    "DATA_DIR",
    "CLEAN_MAJORS_DIR",
    "RAW_GE_DIR",
    "PASSING_GRADES",
    "FAILING_GRADES",
    "CAL_GETC_START_YEAR",
    "CAL_GETC_START_TERM",
    "academic_year_to_code",
    "year_code_to_academic_year",
]

