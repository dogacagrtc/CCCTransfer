"""
Configuration constants for the counseling system.

This module contains all configuration values and constants used throughout
the counseling algorithm. Centralizing these makes it easy to adjust
behavior as policies change.
"""

from pathlib import Path

# =============================================================================
# FILE PATHS
# =============================================================================

# Base data directory (relative to this file's location)
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
CLEAN_MAJORS_DIR = DATA_DIR / "clean_majors"
RAW_GE_DIR = DATA_DIR / "raw_GE" / "Santa_Monica_College"


# =============================================================================
# YEAR CODE UTILITIES
# =============================================================================
# Year codes map to academic years: code = year - 1949
#   - 76 = 2025-2026
#   - 75 = 2024-2025
#   - 74 = 2023-2024 (IGETC Area 4 changed from 3 courses to 2)
#   - 73 = 2022-2023

def academic_year_to_code(year: int) -> int:
    """Convert academic year (e.g., 2025) to year code (e.g., 76)."""
    return year - 1949


def year_code_to_academic_year(code: int) -> int:
    """Convert year code (e.g., 76) to academic year (e.g., 2025)."""
    return code + 1949


# =============================================================================
# GRADE DEFINITIONS
# =============================================================================

# Passing grades that count as "completed"
# These are standard California community college passing grades.
# CR (Credit) is included for pass/fail courses that award credit.
PASSING_GRADES = {"A", "B", "C", "D", "P", "CR"}

# Grades that mean course is NOT completed
# NP = No Pass (failed pass/no-pass), NC = No Credit
# W = Withdrawn, I = Incomplete (should be resolved but treat as not done)
FAILING_GRADES = {"F", "NP", "NC", "W", "I"}


# =============================================================================
# GE PATTERN TRANSITION
# =============================================================================

# Cal-GETC Policy Transition
# --------------------------
# Cal-GETC replaced the separate IGETC and CSU GE-Breadth patterns starting
# Fall 2025. Students who began their coursework before this date continue
# under IGETC, while new students use Cal-GETC.
CAL_GETC_START_YEAR = 2025
CAL_GETC_START_TERM = "Fall"

