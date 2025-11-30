"""
Data loading and caching.

This module handles loading all required data files with caching to prevent
repeated file I/O during audits.
"""

import json
from pathlib import Path

from ..config import DATA_DIR, CLEAN_MAJORS_DIR, RAW_GE_DIR


class DataLoader:
    """
    Loads and caches all required data files.
    
    WHY CACHING: The raw_GE files are large (17K+ lines each). Loading them once
    and caching prevents repeated file I/O during audits.
    
    WHY LAZY LOADING: Properties only load files when first accessed.
    This means if you only need GE rules, the major files aren't loaded.
    
    DATA SOURCES:
    - raw_GE/: Official GE course lists from Assist.org (SOURCE OF TRUTH for GE)
      - IGETC_76.json: IGETC courses for year 2025-2026
      - CALGETC_76.json: Cal-GETC courses for year 2025-2026
      - CSUGE_76.json: CSU GE-Breadth courses for year 2025-2026
    - ge_rules_master.json: GE area requirements (how many courses/units per area)
    - master_catalog.json: Course catalog (units, titles - NOT used for GE areas)
    
    Usage:
        loader = DataLoader()
        igetc_data = loader.load_raw_ge("IGETC", 76)  # Load IGETC for 2025-2026
        ge_attrs = loader.get_course_ge_attributes("PHYSCS 21", 76)
    """
    
    def __init__(self):
        # Private cache variables - None means "not loaded yet"
        self._master_catalog = None
        self._ge_rules = None
        self._dependencies = None
        self._majors_cache = {}  # Keyed by university name for multi-major lookups
        self._raw_ge_cache = {}  # Keyed by (ge_type, year_code) for raw GE files
        self._ge_course_lookup = {}  # Keyed by year_code
    
    @property
    def master_catalog(self) -> dict:
        """
        SMC course catalog with course metadata.
        
        NOTE: This is NOT used for GE area lookups anymore. We now use
        raw_GE/ files for GE attributes because they are the official
        Assist.org data with proper date ranges.
        
        This file is still useful for:
        - Course titles
        - Unit counts
        - CSU/UC transferability flags
        """
        if self._master_catalog is None:
            with open(DATA_DIR / "master_catalog.json", "r") as f:
                self._master_catalog = json.load(f)
        return self._master_catalog
    
    @property
    def ge_rules(self) -> dict:
        """
        GE pattern definitions (Schema v2.0).
        
        Defines the "shape" of GE requirements - which areas exist, how many
        courses/units each requires, and subarea constraints.
        """
        if self._ge_rules is None:
            with open(DATA_DIR / "ge_rules_master.json", "r") as f:
                self._ge_rules = json.load(f)
        return self._ge_rules
    
    @property
    def dependencies(self) -> dict:
        """
        Course prerequisites and corequisites.
        
        This data enables future features like:
        - "How many semesters until I can take PHYS 3?"
        - "What's the optimal course sequence?"
        """
        if self._dependencies is None:
            with open(DATA_DIR / "smc_dependencies.json", "r") as f:
                self._dependencies = json.load(f)
        return self._dependencies
    
    def load_major_articulation(self, university_name: str) -> dict:
        """
        Load articulation agreement for a specific university.
        
        Args:
            university_name: University name with underscores (matches filename)
        
        Returns:
            Dict containing major requirements and articulation data
        """
        if university_name not in self._majors_cache:
            filename = f"SMC_to_{university_name}_clean.json"
            filepath = CLEAN_MAJORS_DIR / filename
            if not filepath.exists():
                raise FileNotFoundError(f"No articulation file found for: {university_name}")
            with open(filepath, "r") as f:
                self._majors_cache[university_name] = json.load(f)
        return self._majors_cache[university_name]
    
    def list_available_universities(self) -> list:
        """
        List all universities with articulation agreements.
        
        Scans the clean_majors directory for available articulation files.
        Returns university names extracted from filenames.
        """
        universities = []
        for f in CLEAN_MAJORS_DIR.glob("SMC_to_*_clean.json"):
            # Extract university name from filename pattern
            name = f.stem.replace("SMC_to_", "").replace("_clean", "")
            universities.append(name)
        return sorted(universities)
    
    def load_raw_ge(self, ge_type: str, year_code: int) -> dict:
        """
        Load a raw GE file from the raw_GE folder.
        
        Args:
            ge_type: Type of GE pattern - "IGETC", "CALGETC", "CSUGE", "CSUAI"
            year_code: Year code (76 = 2025-2026, 75 = 2024-2025, etc.)
        
        Returns:
            Parsed JSON data from the GE file
        """
        cache_key = (ge_type, year_code)
        if cache_key not in self._raw_ge_cache:
            filename = f"{ge_type}_{year_code}.json"
            filepath = RAW_GE_DIR / filename
            if not filepath.exists():
                raise FileNotFoundError(f"GE file not found: {filepath}")
            with open(filepath, "r") as f:
                self._raw_ge_cache[cache_key] = json.load(f)
        return self._raw_ge_cache[cache_key]
    
    def _build_ge_course_lookup(self, year_code: int) -> dict:
        """
        Build a lookup table of course_code -> GE areas for a specific year.
        
        This processes the raw_GE files and creates an efficient lookup:
        {
            "PHYSCS 21": {
                "IGETC": ["5A", "5C"],
                "CALGETC": ["5A", "5C"],
                "CSUGE": ["B1", "B3"],
                "CSUAI": []
            },
            ...
        }
        
        Only includes CURRENT courses (where endDate is in the future).
        """
        if year_code in self._ge_course_lookup:
            return self._ge_course_lookup[year_code]
        
        lookup = {}
        current_date = "2025-01-01T00:00:00"  # Approximate current date
        
        # Map of GE file types to attribute keys
        ge_types = {
            "IGETC": "IGETC",
            "CALGETC": "CALGETC",
            "CSUGE": "CSUGE",
            "CSUAI": "CSUAI",
        }
        
        for ge_file, attr_key in ge_types.items():
            try:
                data = self.load_raw_ge(ge_file, year_code)
                courses = data.get("courseInformationList", [])
                
                for course in courses:
                    # Get course identifier (e.g., "PHYSCS 21")
                    code = course.get("identifier", "")
                    if not code:
                        continue
                    
                    # Check if course is currently valid
                    end_date = course.get("endDate", "2070-01-01T00:00:00")
                    if end_date < current_date:
                        continue  # Course has expired
                    
                    # Initialize if not exists
                    if code not in lookup:
                        lookup[code] = {"IGETC": [], "CALGETC": [], "CSUGE": [], "CSUAI": []}
                    
                    # Extract transfer areas for this GE type
                    transfer_areas = course.get("transferAreas", [])
                    for area in transfer_areas:
                        area_code = area.get("code", "")
                        area_end = area.get("endDate", "2070-01-01T00:00:00")
                        
                        # Only include if the area assignment is current
                        if area_end >= current_date and area_code:
                            if area_code not in lookup[code][attr_key]:
                                lookup[code][attr_key].append(area_code)
                                
            except FileNotFoundError:
                # Some GE types might not have files for all years
                pass
        
        self._ge_course_lookup[year_code] = lookup
        return lookup
    
    def get_course_ge_attributes(self, course_code: str, year_code: int = 76) -> dict:
        """
        Get GE attributes for a course from raw_GE files.
        
        This is the critical lookup that determines which GE areas a course
        satisfies. We use the raw_GE files as the source of truth because
        they come directly from Assist.org and are year-specific.
        
        Args:
            course_code: Exact course code (e.g., "PHYSCS 21")
            year_code: Year code (default 76 = 2025-2026)
        
        Returns:
            Dict with IGETC, CALGETC, CSUGE, CSUAI lists
            Returns empty lists if course not found (safe default)
        """
        lookup = self._build_ge_course_lookup(year_code)
        course_attrs = lookup.get(course_code, {})
        return {
            "IGETC": course_attrs.get("IGETC", []),
            "CALGETC": course_attrs.get("CALGETC", []),
            "CSUGE": course_attrs.get("CSUGE", []),
            "CSUAI": course_attrs.get("CSUAI", []),
        }
    
    def get_available_year_codes(self) -> list:
        """
        Get list of available year codes from raw_GE folder.
        
        Returns:
            List of year codes (e.g., [67, 68, 69, ..., 76])
        """
        year_codes = set()
        for f in RAW_GE_DIR.glob("IGETC_*.json"):
            try:
                code = int(f.stem.split("_")[1])
                year_codes.add(code)
            except (ValueError, IndexError):
                pass
        return sorted(year_codes)

