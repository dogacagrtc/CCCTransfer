import json
import os
import glob
from datetime import datetime

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# scraper_ge creates a "Santa_Monica_College" folder inside raw_ge
INPUT_DIR = os.path.join(BASE_DIR, "data", "raw_ge", "Santa_Monica_College")
OUTPUT_FILE = os.path.join(BASE_DIR, "data", "master_catalog.json")

CURRENT_ACADEMIC_START = "2025-08-01" # Filter out anything that ended before this

def load_json(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️  Could not read {filepath}: {e}")
        return None

def get_course_key(course):
    """Generates a consistent key like 'COM ST 11'"""
    prefix = course.get('prefixCode', '').strip()
    number = course.get('courseNumber', '').strip()
    return f"{prefix} {number}"

def is_active(area_obj):
    """
    Returns True if the GE Area is active for the 2025-2026 school year.
    Checks if 'endDate' exists and is in the past.
    """
    end_date_str = area_obj.get('endDate')
    
    # If no end date, or empty string, it's still active
    if not end_date_str:
        return True
    
    try:
        # Parse ISO date (e.g., "1985-10-01T00:00:00")
        # We slice [:10] to just get YYYY-MM-DD
        end_date = end_date_str[:10]
        
        # If the end date is BEFORE our current academic year, it's dead.
        if end_date < CURRENT_ACADEMIC_START:
            return False
            
    except:
        pass # If date parse fails, assume safe (keep it)

    return True

def run():
    master_catalog = {}
    
    if not os.path.exists(INPUT_DIR):
        print(f"❌ Input directory not found: {INPUT_DIR}")
        return

    # Map report types to attributes
    file_map = {
        "CSUTC": ("CSU_Transferable", "bool"),
        "UCTCA": ("UC_Transferable", "bool"),
        "CSUGE": ("CSU_GE", "areas"),
        "IGETC": ("IGETC", "areas"),
        "CALGETC": ("Cal_GETC", "areas"),
        "CSUAI": ("CSU_AI", "areas"),
        "UCTEL": ("UC_Eligibility", "areas")
    }

    files = glob.glob(os.path.join(INPUT_DIR, "*.json"))
    print(f"🔄 Merging {len(files)} files with Date Filtering...")

    for filepath in files:
        filename = os.path.basename(filepath)
        
        # Identify report type
        report_type = None
        target_attr = None
        mode = None
        
        for key, (attr, m) in file_map.items():
            if key in filename:
                report_type = key
                target_attr = attr
                mode = m
                break
        
        if not report_type: continue

        data = load_json(filepath)
        if not data: continue

        course_list = data.get('courseInformationList', [])

        for item in course_list:
            course_key = get_course_key(item)
            
            # Initialize
            if course_key not in master_catalog:
                master_catalog[course_key] = {
                    "title": item.get('courseTitle'),
                    "units": item.get('maxUnits', 0.0),
                    "attributes": {
                        "CSU_Transferable": False,
                        "UC_Transferable": False,
                        "CSU_GE": [],
                        "IGETC": [],
                        "Cal_GETC": [],
                        "CSU_AI": [],
                        "UC_Eligibility": []
                    }
                }
            
            course_obj = master_catalog[course_key]
            
            if mode == "bool":
                course_obj["attributes"][target_attr] = True
            
            elif mode == "areas":
                raw_areas = item.get('transferAreas', [])
                
                # --- THE FIX: FILTER BY DATE ---
                active_codes = [
                    area['code'] for area in raw_areas 
                    if is_active(area)
                ]
                # -------------------------------

                # Append unique codes
                current_list = course_obj["attributes"][target_attr]
                for c in active_codes:
                    if c not in current_list:
                        current_list.append(c)
                
                # Implicit Transferability
                if "CSU" in report_type:
                    course_obj["attributes"]["CSU_Transferable"] = True
                if "IGETC" in report_type or "UC" in report_type:
                    course_obj["attributes"]["UC_Transferable"] = True

    print("-" * 50)
    print(f"💾 Saving Cleaned Master Catalog...")
    
    # Ensure output dir exists (it's 'data/')
    out_dir = os.path.dirname(OUTPUT_FILE)
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(master_catalog, f, indent=2, sort_keys=True)
        
    print(f"✅ Done! {OUTPUT_FILE} is now trustworthy.")

if __name__ == "__main__":
    run()
