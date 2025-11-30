"""
Student Transfer Counseling Algorithm - LEGACY WRAPPER
=======================================================

This file is maintained for backwards compatibility.
The code has been reorganized into the 'counseling' package.

NEW STRUCTURE:
--------------
counseling/
├── __init__.py          # Main exports
├── config.py            # Configuration constants
├── counselor.py         # TransferCounselor orchestrator
├── cli.py               # Command-line interface
├── models/              # Data classes and enums
├── data/                # Data loading and parsing
├── engines/             # Audit and recommendation engines
└── ui/                  # User interface implementations

USAGE:
------

Option 1 - Run as module:
    python -m counseling

Option 2 - Run this file (legacy):
    python counseling_algorithm.py

Option 3 - Import in code:
    from counseling import TransferCounselor, TargetDefinition
    
    counselor = TransferCounselor()
    counselor.run_audit(...)

For more information, see counseling/__init__.py
"""

# Import everything from the new package for backwards compatibility
from counseling import *
from counseling.cli import main

if __name__ == "__main__":
    main()
