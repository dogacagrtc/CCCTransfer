import requests
import json
import urllib.parse
import os
import time

# --- CONFIGURATION ---
SMC_ID = 137      # Source: Santa Monica College
START_YEAR = 76   # 2025-2026
LOOKBACK_YEARS = 6 # How many years back to check (76 -> 70)

# Calculate paths relative to this script file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "raw_majors")
# ---------------------

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def unpack_json_string(s):
    if isinstance(s, str):
        try:
            return json.loads(s)
        except (json.JSONDecodeError, TypeError):
            return s
    return s

def clean_object(obj):
    target_fields = [
        'articulations', 'templateAssets', 'receivingInstitution', 
        'sendingInstitution', 'academicYear', 'catalogYear'
    ]
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in target_fields:
                obj[key] = unpack_json_string(value)
            elif isinstance(value, (dict, list)):
                clean_object(value)
    elif isinstance(obj, list):
        for item in obj:
            clean_object(item)
    return obj

def get_partners(source_id):
    print(f"📡 Fetching ALL partners for SMC ({source_id})...")
    url = f"https://assist.org/api/institutions/{source_id}/agreements"
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        partners = [
            {'id': p['institutionParentId'], 'name': p['institutionName']}
            for p in data 
            if p['institutionParentId'] != source_id
        ]
        
        unique_partners = {p['id']: p for p in partners}.values()
        sorted_partners = sorted(list(unique_partners), key=lambda x: x['name'])
        
        print(f"✅ Found {len(sorted_partners)} unique universities.")
        return sorted_partners
    except Exception as e:
        print(f"❌ Failed to get partner list: {e}")
        return []

def try_download(url):
    """Helper to try a specific URL. Returns data or None."""
    try:
        resp = requests.get(url, headers=headers, timeout=60)
        if resp.status_code == 200:
            raw_data = resp.json()
            if raw_data.get('isSuccessful', False):
                return raw_data
        elif resp.status_code == 429:
            print(f"⏳ Rate Limit. Sleeping 60s...", end=" ", flush=True)
            time.sleep(60)
            return try_download(url) # Retry once recursively
    except:
        pass
    return None

def save_data(raw_data, filename, year, doc_type):
    clean_data = clean_object(raw_data)
    clean_data['downloaded_year_id'] = year
    clean_data['document_type'] = doc_type
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(clean_data, f, indent=4)

def download_school(target):
    target_id = target['id']
    target_name = target['name']
    
    safe_name = "".join([c for c in target_name if c.isalnum() or c in (' ', '-', '_')]).strip()
    filename = f"{OUTPUT_DIR}/SMC_to_{safe_name}.json"
    
    if os.path.exists(filename):
        print(f"⏭️  Skipping {target_name} (Already Exists)")
        return

    print(f"📥 {target_name}...", end=" ", flush=True)

    # LOOP: Check Years (Newest -> Oldest)
    for year in range(START_YEAR, START_YEAR - LOOKBACK_YEARS, -1):
        
        # STRATEGY 1: Try "All Majors"
        raw_key_major = f"{year}/{SMC_ID}/to/{target_id}/AllMajors"
        url_major = f"https://assist.org/api/articulation/Agreements?Key={urllib.parse.quote(raw_key_major)}"
        
        data = try_download(url_major)
        if data:
            print(f"✅ Found Majors (Year {year})")
            save_data(data, filename, year, "AllMajors")
            time.sleep(1) # Polite pause after success
            return

        # STRATEGY 2: Try "All Departments"
        raw_key_dept = f"{year}/{SMC_ID}/to/{target_id}/AllDepartments"
        url_dept = f"https://assist.org/api/articulation/Agreements?Key={urllib.parse.quote(raw_key_dept)}"
        
        data = try_download(url_dept)
        if data:
            print(f"✅ Found Depts (Year {year})")
            save_data(data, filename, year, "AllDepartments")
            time.sleep(1) # Polite pause after success
            return

        # STRATEGY 3: Try "All General Education" (New!)
        # Key format matches the URL you found: 76/137/to/227/AllGeneralEducation
        raw_key_ge = f"{year}/{SMC_ID}/to/{target_id}/AllGeneralEducation"
        url_ge = f"https://assist.org/api/articulation/Agreements?Key={urllib.parse.quote(raw_key_ge)}"
        
        data = try_download(url_ge)
        if data:
            print(f"✅ Found GE (Year {year})")
            save_data(data, filename, year, "AllGeneralEducation")
            time.sleep(0.5) # Polite pause after success
            return
            
        # If all 3 strategies fail, try the next year
        print(".", end="", flush=True)

    print("❌ Failed all attempts.")

def run():
    # Ensure output directory exists
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    partners = get_partners(SMC_ID)

    if partners:
        print(f"🚀 Starting Deep Scrape ({LOOKBACK_YEARS} year history)...")
        print(f"📂 Saving to: {OUTPUT_DIR}")
        print("-" * 50)
        for p in partners:
            download_school(p)
            # We already sleep 1s inside download_school on success, 
            # but a small buffer here ensures we don't hammer immediately on failure loops
            time.sleep(0.5) 
        print("-" * 50)
        print(f"✨ Done. Check '{OUTPUT_DIR}'")

if __name__ == "__main__":
    run()
