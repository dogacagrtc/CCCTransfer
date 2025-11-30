import requests
import json
import os
import time
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- CONFIGURATION ---
SMC_ID = 137             # Santa Monica College
SMC_NAME = "Santa Monica College"

START_YEAR = 76          # 76 = 2025-2026 Academic Year
LOOKBACK_YEARS = 10      # Scrape last 10 years

# Calculate paths relative to this script file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "raw_ge")

# The exact codes accepted by the 'listType' parameter
REPORT_TYPES = [
    "CSUGE",    # CSU GE-Breadth
    "IGETC",    # IGETC
    "CALGETC",  # Cal-GETC (New!)
    "CSUTC",    # CSU Transferable Courses
    "CSUAI",    # CSU American Ideals
    "UCTCA",    # UC Transferable Courses
    "UCTEL"     # UC Eligibility
]
# ---------------------

# --- SESSION SETUP (Anti-Ban) ---
def create_retry_session():
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=2,  # Wait 2s, 4s, 8s, 16s... on 429 errors
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    return session

def run():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    session = create_retry_session()
    
    # Create SMC folder
    safe_name = SMC_NAME.replace(" ", "_")
    college_dir = os.path.join(OUTPUT_DIR, safe_name)
    if not os.path.exists(college_dir):
        os.makedirs(college_dir)

    print(f"🏫 Processing: {SMC_NAME} (ID: {SMC_ID})")
    print(f"🔗 Base URL: https://assist.org/api/transferability/courses")
    print(f"📂 Saving to: {college_dir}")

    # LOOP: Years (Newest -> Oldest)
    for year in range(START_YEAR, START_YEAR - LOOKBACK_YEARS, -1):
        year_disp = f"20{int(year) + 1949}-20{int(year) + 1950}"
        print(f"   📅 Year {year} ({year_disp})...", end=" ")

        for rtype in REPORT_TYPES:
            # 1. Safety Check: Skip Cal-GETC for years before 2025
            if rtype == "CALGETC" and year < 76:
                continue

            filename = os.path.join(college_dir, f"{rtype}_{year}.json")
            
            # 2. Skip if already exists
            if os.path.exists(filename):
                continue

            # 3. Construct the EXACT URL you found
            url = "https://assist.org/api/transferability/courses"
            params = {
                "institutionId": SMC_ID,
                "academicYearId": year,
                "listType": rtype
            }

            try:
                resp = session.get(url, params=params, timeout=15)
                
                if resp.status_code == 200:
                    data = resp.json()
                    # Verify content is valid
                    course_list = data.get('courseInformationList', [])
                    
                    if course_list:
                        # Save Data
                        with open(filename, 'w', encoding='utf-8') as f:
                            json.dump(data, f, indent=4)
                        print(f"[{rtype} ✔️]", end=" ", flush=True)
                        
                        # 4. Human Jitter (Sleep 2-4 seconds)
                        time.sleep(random.uniform(2.0, 4.0))
                    else:
                        # Empty list returned (valid but empty)
                        print(f"[{rtype} ∅]", end=" ", flush=True)
                
                elif resp.status_code == 400:
                    print(f"[{rtype} ❌ 400]", end=" ", flush=True)
                else:
                    print(f"[{rtype} ⚠️ {resp.status_code}]", end=" ", flush=True)

            except Exception as e:
                print(f"[Err: {e}]", end=" ")

        print("") # New line after year

if __name__ == "__main__":
    print(f"🚀 Starting Final SMC Transferability Scrape")
    print("-" * 60)
    run()
    print("-" * 60)
    print(f"✨ Done. Data saved to '{OUTPUT_DIR}'")
