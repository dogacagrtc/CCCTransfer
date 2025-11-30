"""
Command-Line Interface for the Counseling System.

This module provides the interactive CLI for the counseling algorithm.
It handles user input and orchestrates the display of results.

NOTE: Don't run this file directly. Run from parent directory:
    cd CollegeTransfer
    python3 -m counseling
"""

from .config import DATA_DIR
from .models import TargetDefinition
from .ui import TerminalDisplay
from .counselor import TransferCounselor


def _select_university_and_major(counselor: TransferCounselor, target_num: int = 1) -> tuple:
    """
    Helper to select a university and major interactively.
    
    Returns:
        Tuple of (university, major, target_system) or (None, None, None) if cancelled
    """
    print(f"\n{TerminalDisplay.BOLD}Select target university #{target_num}:{TerminalDisplay.RESET}")
    universities = counselor.list_universities()
    
    # Separate CSU and UC options
    csu_unis = [u for u in universities if "California State" in u or "CSU" in u.upper()]
    uc_unis = [u for u in universities if "University of California" in u or u.startswith("UC ")]
    
    print(f"\n  {TerminalDisplay.CYAN}CSU Campuses:{TerminalDisplay.RESET}")
    for i, u in enumerate(csu_unis, 1):
        print(f"    {i}. {u.replace('_', ' ')}")
    
    if uc_unis:
        print(f"\n  {TerminalDisplay.MAGENTA}UC Campuses:{TerminalDisplay.RESET}")
        for i, u in enumerate(uc_unis, len(csu_unis) + 1):
            print(f"    {i}. {u.replace('_', ' ')}")
    
    all_unis = csu_unis + uc_unis
    
    try:
        choice = input(f"\n  Enter number (1-{len(all_unis)}) or 'skip' to finish: ").strip()
        if choice.lower() == 'skip':
            return None, None, None
        university = all_unis[int(choice) - 1]
    except (ValueError, IndexError, EOFError):
        university = "California State University Long Beach"
        print(f"  → Using default: {university.replace('_', ' ')}")
    
    # Determine target system (CSU or UC)
    target_system = "uc" if "University of California" in university else "csu"
    
    # Select major
    print(f"\n{TerminalDisplay.BOLD}Select major at {university.replace('_', ' ')}:{TerminalDisplay.RESET}")
    majors = counselor.list_majors(university)
    
    search = input("  Search (or press Enter to list all): ").strip().lower()
    
    if search:
        matching = [m for m in majors if search in m.lower()]
    else:
        matching = majors
    
    # Show first 20
    for i, m in enumerate(matching[:20], 1):
        print(f"    {i}. {m}")
    
    if len(matching) > 20:
        print(f"    ... and {len(matching) - 20} more")
    
    try:
        choice = input(f"\n  Enter number or major name: ").strip()
        if choice.isdigit():
            major = matching[int(choice) - 1]
        else:
            major = choice
    except (ValueError, IndexError, EOFError):
        major = "Computer Science"
        print(f"  → Using default: {major}")
    
    return university, major, target_system


def main():
    """
    Command-line interface for the counseling algorithm.
    
    ═══════════════════════════════════════════════════════════════════════════
    MULTI-TARGET SUPPORT
    ═══════════════════════════════════════════════════════════════════════════
    
    This CLI supports auditing against MULTIPLE university/major targets:
    
    1. Enter student's start date (determines IGETC vs Cal-GETC)
    2. Select first university and major
    3. Optionally add more targets
    4. Run audit showing:
       - Individual results for each target
       - Unified efficiency analysis across all targets
    
    ═══════════════════════════════════════════════════════════════════════════
    """
    counselor = TransferCounselor()
    
    # Welcome banner
    print(f"\n{TerminalDisplay.BOLD}{TerminalDisplay.CYAN}")
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║         STUDENT TRANSFER COUNSELING SYSTEM                       ║")
    print("║         Santa Monica College → California Universities           ║")
    print("║                                                                  ║")
    print("║  ★ NEW: Compare multiple universities at once!                  ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print(f"{TerminalDisplay.RESET}")
    
    # Get student entry information
    print(f"\n{TerminalDisplay.BOLD}When did you start at SMC?{TerminalDisplay.RESET}")
    try:
        entry_year = int(input("  Entry Year (e.g., 2023): ").strip())
        entry_term = input("  Entry Term (Fall/Spring/Summer/Winter): ").strip().capitalize()
    except (ValueError, EOFError):
        print("Invalid input. Using defaults: 2023 Fall")
        entry_year = 2023
        entry_term = "Fall"
    
    # Show which GE pattern applies
    ge_pattern = counselor.ge_engine.determine_ge_pattern(entry_year, entry_term)
    pattern_name = "Cal-GETC" if ge_pattern == "CalGETC" else "IGETC"
    print(f"\n  → Based on your entry date, you'll be audited against: {TerminalDisplay.CYAN}{pattern_name}{TerminalDisplay.RESET}")
    
    # Ask how many targets
    print(f"\n{TerminalDisplay.BOLD}How many universities are you considering?{TerminalDisplay.RESET}")
    print(f"  {TerminalDisplay.DIM}(Enter a number, or 0 to select interactively){TerminalDisplay.RESET}")
    
    try:
        num_targets = int(input("  Number of targets: ").strip())
    except (ValueError, EOFError):
        num_targets = 0
    
    # Collect targets
    targets = []
    
    if num_targets > 0:
        for i in range(1, num_targets + 1):
            university, major, target_system = _select_university_and_major(counselor, i)
            if university and major:
                targets.append(TargetDefinition(
                    university=university,
                    major=major,
                    target_system=target_system
                ))
    else:
        print(f"\n  {TerminalDisplay.DIM}You can add as many targets as you want.{TerminalDisplay.RESET}")
        print(f"  {TerminalDisplay.DIM}Type 'skip' when you're done adding targets.{TerminalDisplay.RESET}")
        
        target_num = 1
        while True:
            university, major, target_system = _select_university_and_major(counselor, target_num)
            if university and major:
                targets.append(TargetDefinition(
                    university=university,
                    major=major,
                    target_system=target_system
                ))
                target_num += 1
                print(f"\n  {TerminalDisplay.GREEN}✓ Added: {university.replace('_', ' ')} - {major}{TerminalDisplay.RESET}")
            else:
                break
    
    # Ensure at least one target
    if not targets:
        print(f"\n  {TerminalDisplay.YELLOW}No targets selected. Using defaults.{TerminalDisplay.RESET}")
        targets = [TargetDefinition(
            university="California State University Long Beach",
            major="Computer Science",
            target_system="csu"
        )]
    
    # Confirm targets
    print(f"\n{TerminalDisplay.BOLD}Your targets:{TerminalDisplay.RESET}")
    for i, target in enumerate(targets, 1):
        system_label = "CSU" if target.target_system == "csu" else "UC"
        print(f"  {i}. {target.university.replace('_', ' ')} - {target.major} ({system_label})")
    
    # Run the audit
    transcript_path = DATA_DIR / "example_parsed_transcript.json"
    
    print(f"\n{TerminalDisplay.DIM}Running audit...{TerminalDisplay.RESET}")
    
    if len(targets) == 1:
        counselor.run_audit(
            transcript_path=str(transcript_path),
            university=targets[0].university,
            major=targets[0].major,
            entry_year=entry_year,
            entry_term=entry_term,
            target_system=targets[0].target_system
        )
    else:
        counselor.run_multi_target_audit(
            transcript_path=str(transcript_path),
            targets=targets,
            entry_year=entry_year,
            entry_term=entry_term
        )


if __name__ == "__main__":
    main()

