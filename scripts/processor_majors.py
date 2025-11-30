#!/usr/bin/env python3
"""
Build a merged, runtime-friendly JSON file directly from raw ASSIST data.

Input:  raw ASSIST JSON, e.g. "SMC_to_California State University East Bay.json"
Output: merged JSON, e.g. "CSUEB_merged.json"

Usage:
    python processor_majors.py <input_raw.json> <output_merged.json>
"""

import json
import sys
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
import re

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_DIR = os.path.join(BASE_DIR, "data", "raw_majors")
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "clean_majors")
# ---------------------

# ------------------------------------------------------------
#  Helpers: articulation index and sending-course options
# ------------------------------------------------------------

def build_articulation_index(raw: Dict[str, Any]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
    """
    Build TWO dictionaries for articulation lookup:
    
    1. cell_id_index: templateCellId -> articulation entry
       Used for direct lookup when we have the cell ID.
       
    2. course_code_index: "PREFIX NUMBER" -> list of articulation entries
       FALLBACK: Used when requirement groups are empty but we know what
       courses they should contain (e.g., "PHYSICS 1A" for engineering physics).
       
    WHY TWO INDEXES?
    ----------------
    Some majors on Assist.org have empty requirement groups that reference
    shared course pools. For example, UCLA Computer Science's physics requirement
    group has 0 courses embedded, but physics courses ARE articulated for
    other engineering majors. The course_code_index lets us find these.
    """
    cell_id_index: Dict[str, Dict[str, Any]] = {}
    course_code_index: Dict[str, List[Dict[str, Any]]] = {}
    
    result = raw.get("result") or {}
    for art in result.get("articulations", []) or []:
        # Index by cell ID
        cell_id = art.get("templateCellId")
        if cell_id:
            cell_id_index[cell_id] = art
        
        # Index by course code for fallback lookup
        art_core = art.get("articulation") or {}
        course = art_core.get("course") or {}
        prefix = course.get("prefix", "")
        number = course.get("courseNumber", "")
        if prefix and number:
            code = f"{prefix} {number}"
            if code not in course_code_index:
                course_code_index[code] = []
            course_code_index[code].append(art)
    
    return cell_id_index, course_code_index


def summarize_sending_options(sending_art: Optional[Dict[str, Any]]) -> Tuple[List[List[Dict[str, Any]]], str]:
    """
    Given a 'sendingArticulation' object from ASSIST, produce:

        smc_options: list of options, where each option is a list of SMC course dicts
        articulation_type: "Articulated" or "No Articulation"

    Examples:
        - [[ {SMC PHYS 8}, {SMC PHYS 9} ]]  → must take both together
        - [[ {SMC ART 31} ], [ {SMC ART 30A} ]] → either course works (two options)
    """
    if not sending_art:
        return [], "No Articulation"

    # If there are no items but a reason, it's explicitly no articulation
    items = sending_art.get("items") or []
    if (not items) and sending_art.get("noArticulationReason"):
        return [], "No Articulation"

    smc_options: List[List[Dict[str, Any]]] = []

    # Each CourseGroup in "items" is treated as one option
    for group in items:
        group_courses: List[Dict[str, Any]] = []
        for c in group.get("items") or []:
            if c.get("type") == "Course":
                group_courses.append({
                    "code": f"{c.get('prefix')} {c.get('courseNumber')}",
                    "prefix": c.get("prefix"),
                    "number": c.get("courseNumber"),
                    "title": c.get("courseTitle"),
                    "units": c.get("minUnits"),
                })
        if group_courses:
            smc_options.append(group_courses)

    articulation_type = "Articulated" if smc_options else "No Articulation"
    return smc_options, articulation_type


# ------------------------------------------------------------
#  Helpers: requirement instruction → simple logic tags
# ------------------------------------------------------------

def normalize_instruction(instr: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert ASSIST's instruction object into a simple rule descriptor:

        {
          "logic": "ALL_OF" | "ONE_OF" | "CHOOSE_N" | "AT_LEAST_N" | "UP_TO_N",
          "n": int or None,
          "min_count": int or None,
          "max_count": int or None,
          "raw_instruction": { ...original... }
        }
    """
    t = instr.get("type")
    conj = instr.get("conjunction")
    amt = instr.get("amount")
    aq = instr.get("amountQuantifier")

    logic = "ALL_OF"
    n: Optional[int] = None
    min_count: Optional[int] = None
    max_count: Optional[int] = None

    # 1) "Following" → complete all listed
    if t == "Following":
        logic = "ALL_OF"

    # 2) "Conjunction" → usually OR or AND
    elif t == "Conjunction":
        if conj == "Or":
            logic = "ONE_OF"
            min_count = 1
            max_count = 1
        else:
            logic = "ALL_OF"

    # 3) NFrom* → numeric variants
    elif t in ("NFromFollowing", "NFromConjunction", "NFromArea"):
        n = int(amt) if amt is not None else 0

        # If quantifier is missing or "None", treat as "CHOOSE_N"
        if aq == "AtLeast":
            logic = "AT_LEAST_N"
            min_count = n
            max_count = None
        elif aq == "UpTo":
            logic = "UP_TO_N"
            min_count = 0
            max_count = n
        else:
            logic = "CHOOSE_N"
            min_count = n
            max_count = n

    # 4) Fallback: unknown → treat as ALL_OF
    else:
        logic = "ALL_OF"

    return {
        "logic": logic,
        "n": n,
        "min_count": min_count,
        "max_count": max_count,
        "raw_instruction": instr,
    }


# ------------------------------------------------------------
#  Transform a single major into merged format
# ------------------------------------------------------------

def extract_course_codes_from_text(text: str) -> List[str]:
    """
    Extract potential course codes from text like:
    "Complete PHYSICS 1A, 1B, and 1C" -> ["PHYSICS 1A", "PHYSICS 1B", "PHYSICS 1C"]
    "CS 52 or CS 55 or JAVA course" -> ["CS 52", "CS 55"]
    
    This helps us find courses mentioned in requirement descriptions
    when the requirement group structure is empty.
    """
    # Common prefixes at UCLA
    prefixes = [
        "PHYSICS", "PHYS", "MATH", "COM SCI", "CS", "CHEM", "ENGR", 
        "EC ENGR", "ENGCOMP", "LIFE SCI", "STATS"
    ]
    
    codes = []
    text_upper = text.upper()
    
    for prefix in prefixes:
        # Match patterns like "PHYSICS 1A" or "PHYSICS 1A, 1B, 1C"
        pattern = rf'\b{re.escape(prefix)}\s+(\d+[A-Z]?)\b'
        matches = re.findall(pattern, text_upper)
        for num in matches:
            codes.append(f"{prefix} {num}")
    
    return codes


# Known requirement patterns for common majors when Assist.org data is incomplete
# Maps keywords in descriptions to course prefixes that should be included
KEYWORD_TO_COURSES = {
    # Physics sequences for engineering
    "physics series": ["PHYSICS 1A", "PHYSICS 1B", "PHYSICS 1C"],
    "calculus based physics": ["PHYSICS 1A", "PHYSICS 1B", "PHYSICS 1C"],
    "calculus-based physics": ["PHYSICS 1A", "PHYSICS 1B", "PHYSICS 1C"],
    "physics for scientists": ["PHYSICS 1A", "PHYSICS 1B", "PHYSICS 1C"],
    
    # Programming languages
    "c++": ["COM SCI 31"],  # UCLA's intro CS is CS 31
    "java": ["COM SCI 31"],
    "programming requirement": ["COM SCI 31"],
}


def extract_courses_from_keywords(text: str) -> List[str]:
    """
    Use keyword matching to find courses when explicit codes aren't mentioned.
    
    Example: "One and a half years of Calculus Based Physics" -> 
             ["PHYSICS 1A", "PHYSICS 1B", "PHYSICS 1C"]
    """
    text_lower = text.lower()
    found_courses = []
    
    for keyword, courses in KEYWORD_TO_COURSES.items():
        if keyword in text_lower:
            for course in courses:
                if course not in found_courses:
                    found_courses.append(course)
    
    return found_courses


def transform_major(
    major_obj: Dict[str, Any],
    cell_id_index: Dict[str, Dict[str, Any]],
    course_code_index: Dict[str, List[Dict[str, Any]]],
    receiving_inst: Dict[str, Any],
    sending_inst: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Transform one major's templateAssets into a merged representation.
    
    ENHANCED: Now uses course_code_index as fallback when requirement
    groups are empty but descriptions mention specific courses.
    
    FALLBACK DEDUPLICATION:
    -----------------------
    When multiple requirement groups are empty, we extract courses from the
    major description text. To avoid adding the SAME courses to multiple
    requirement groups, we track which courses have already been used.
    
    For example, if the description mentions both "physics series" and "C++",
    we add physics courses to the FIRST empty group and C++ to the SECOND.
    """
    template_assets = major_obj.get("templateAssets") or []

    # ---- 1. General titles / texts (program descriptions, notes) ----
    general_titles: List[str] = []
    general_texts: List[str] = []

    for asset in template_assets:
        if asset.get("type") == "GeneralTitle" and asset.get("content"):
            general_titles.append(asset["content"])
        elif asset.get("type") == "GeneralText" and asset.get("content"):
            general_texts.append(asset["content"])
    
    # Track which courses have been added via fallback to avoid duplicates
    # across multiple empty requirement groups
    fallback_courses_used: set = set()

    # ---- 2. Requirement titles mapped by groupId ----
    titles_by_gid: Dict[str, List[str]] = {}
    for asset in template_assets:
        if asset.get("type") == "RequirementTitle":
            gid = asset.get("groupId")
            if gid:
                titles_by_gid.setdefault(gid, []).append(asset.get("content"))

    # ---- 3. Requirement groups -> rule groups ----
    requirements: List[Dict[str, Any]] = []

    for asset in template_assets:
        if asset.get("type") != "RequirementGroup":
            continue

        gid = asset.get("groupId")
        rule_info = normalize_instruction(asset.get("instruction") or {})

        # Collect course items from sections/rows/cells
        items: List[Dict[str, Any]] = []

        for section in asset.get("sections") or []:
            for row in section.get("rows") or []:
                for cell in row.get("cells") or []:
                    if cell.get("type") != "Course":
                        continue

                    course_obj = cell.get("course") or {}
                    cell_id = cell.get("id")

                    art_entry = cell_id_index.get(cell_id)
                    sending_art = None
                    receiving_attributes = None

                    if art_entry:
                        art_core = art_entry.get("articulation") or {}
                        sending_art = art_core.get("sendingArticulation")
                        receiving_attributes = art_core.get("receivingAttributes") or art_entry.get("receivingAttributes")

                    smc_options, articulation_type = summarize_sending_options(sending_art)

                    items.append({
                        "type": "COURSE",
                        "university_course": {
                            "code": f"{course_obj.get('prefix')} {course_obj.get('courseNumber')}",
                            "prefix": course_obj.get("prefix"),
                            "number": course_obj.get("courseNumber"),
                            "title": course_obj.get("courseTitle"),
                            "units": course_obj.get("minUnits"),
                            "attributes": receiving_attributes,
                        },
                        "smc_options": smc_options,
                        "articulation_type": articulation_type,
                    })

        # ---- FALLBACK: If requirement group is empty, try to extract courses ----
        # from the requirement titles or general texts
        if not items and course_code_index:
            # Look in general_texts for course mentions (they often describe requirements)
            all_text = " ".join(general_texts) + " ".join(titles_by_gid.get(gid, []))
            
            # Try explicit course codes first
            mentioned_codes = extract_course_codes_from_text(all_text)
            
            # Then try keyword-based extraction (e.g., "physics series" -> PHYSICS 1A, 1B, 1C)
            keyword_codes = extract_courses_from_keywords(all_text)
            
            # Combine both (explicit codes take priority)
            all_codes = mentioned_codes + [c for c in keyword_codes if c not in mentioned_codes]
            
            # SMART GROUPING: Group courses by prefix to keep related courses together
            # e.g., all PHYSICS courses go to one requirement, all COM SCI to another
            # 
            # NOTE: Some prefixes have spaces (e.g., "COM SCI", "EC ENGR")
            # We extract everything except the last part (the course number)
            codes_by_prefix: Dict[str, List[str]] = {}
            for code in all_codes:
                # Split and take everything except the last part (number)
                # "COM SCI 31" -> "COM SCI", "PHYSICS 1A" -> "PHYSICS"
                parts = code.rsplit(" ", 1)
                prefix = parts[0] if len(parts) > 1 else code
                if prefix not in codes_by_prefix:
                    codes_by_prefix[prefix] = []
                codes_by_prefix[prefix].append(code)
            
            # Find the first unused prefix group that has valid courses in the index
            selected_codes = []
            for prefix, codes in codes_by_prefix.items():
                # Check if ANY course in this prefix group is already used
                if any(c in fallback_courses_used for c in codes):
                    continue
                    
                # Check if ANY course in this prefix group exists in the index
                valid_codes = [c for c in codes if c in course_code_index]
                if valid_codes:
                    selected_codes = valid_codes
                    break
            
            for code in selected_codes:
                if code not in fallback_courses_used:
                    # Get the first articulation for this course
                    art_entries = course_code_index[code]
                    if art_entries:
                        art_entry = art_entries[0]
                        art_core = art_entry.get("articulation") or {}
                        course_info = art_core.get("course") or {}
                        sending_art = art_core.get("sendingArticulation")
                        receiving_attributes = art_core.get("receivingAttributes") or art_entry.get("receivingAttributes")
                        
                        smc_options, articulation_type = summarize_sending_options(sending_art)
                        
                        items.append({
                            "type": "COURSE",
                            "university_course": {
                                "code": code,
                                "prefix": course_info.get("prefix"),
                                "number": course_info.get("courseNumber"),
                                "title": course_info.get("courseTitle"),
                                "units": course_info.get("minUnits"),
                                "attributes": receiving_attributes,
                            },
                            "smc_options": smc_options,
                            "articulation_type": articulation_type,
                            "_source": "extracted_from_text",  # Mark as fallback
                        })
                        
                        # Mark this course as used
                        fallback_courses_used.add(code)

        requirements.append({
            "id": gid,
            "area": asset.get("area"),
            "position": asset.get("position"),
            "titles": titles_by_gid.get(gid, []),
            "rule": rule_info,
            "items": items,
        })

    return {
        "major": major_obj.get("name"),
        "university": receiving_inst,
        "community_college": sending_inst,
        "general_titles": general_titles,
        "general_texts": general_texts,
        "requirements": requirements,
    }


# ------------------------------------------------------------
#  Top-level transformer
# ------------------------------------------------------------

def transform_raw_to_merged(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Take the raw ASSIST JSON and build a merged structure.
    
    ENHANCED: Now builds two articulation indexes:
    1. cell_id_index - for direct cell ID lookups (primary)
    2. course_code_index - for fallback when requirement groups are empty
    """
    result = raw.get("result") or {}

    # Meta
    meta = {
        "name": result.get("name"),
        "type": result.get("type"),
        "publishDate": result.get("publishDate"),
        "academicYear": result.get("academicYear"),
        "catalogYear": result.get("catalogYear"),
        "receivingInstitution": result.get("receivingInstitution"),
        "sendingInstitution": result.get("sendingInstitution"),
        "document_type": raw.get("document_type"),
        "downloaded_year_id": raw.get("downloaded_year_id"),
        "isSuccessful": raw.get("isSuccessful"),
        "validationFailure": raw.get("validationFailure"),
    }

    # Build articulation indexes (cell ID + course code fallback)
    cell_id_index, course_code_index = build_articulation_index(raw)

    # Transform each major
    majors_out: List[Dict[str, Any]] = []
    for major_obj in result.get("templateAssets") or []:
        majors_out.append(
            transform_major(
                major_obj,
                cell_id_index,
                course_code_index,
                result.get("receivingInstitution") or {},
                result.get("sendingInstitution") or {},
            )
        )

    return {
        "meta": meta,
        "majors": majors_out,
    }

def run():
    input_path = Path(INPUT_DIR)
    output_path = Path(OUTPUT_DIR)
    
    if not input_path.exists():
        print(f"❌ Input directory not found: {input_path}")
        return

    if not output_path.exists():
        output_path.mkdir(parents=True, exist_ok=True)

    files = list(input_path.glob("*.json"))
    print(f"🔄 Found {len(files)} major agreements to process...")

    for fpath in files:
        try:
            with fpath.open("r", encoding="utf-8") as f:
                raw = json.load(f)
            
            merged = transform_raw_to_merged(raw)
            
            # Create a clean filename
            out_name = fpath.stem + "_clean.json"
            out_file = output_path / out_name
            
            with out_file.open("w", encoding="utf-8") as f:
                json.dump(merged, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
             print(f"⚠️ Failed to process {fpath.name}: {e}")

    print("✨ Majors processing complete.")

# ------------------------------------------------------------
#  CLI entry point
# ------------------------------------------------------------

def main(argv: List[str]) -> None:
    if len(argv) != 3:
        print("Usage: python processor_majors.py <input_raw.json> <output_merged.json>")
        sys.exit(1)

    in_path = Path(argv[1])
    out_path = Path(argv[2])

    if not in_path.exists():
        print(f"Input file not found: {in_path}")
        sys.exit(1)

    with in_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    merged = transform_raw_to_merged(raw)

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"Merged file written to {out_path}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv)
    else:
        run()
