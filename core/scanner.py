"""
YOLO Security Scanner — standalone report printer.
Called when the user runs: yolo --scan
"""

import sys
from pathlib import Path
from skills.security import deep_scan

OR   = "\033[38;5;208m"
RED  = "\033[91m"
YL   = "\033[93m"
GR   = "\033[92m"
CY   = "\033[96m"
DIM  = "\033[2m"
BOLD = "\033[1m"
RST  = "\033[0m"


def run_scan(start_path: str = ".") -> int:
    """
    Run the deep scan, print a formatted report, and return exit code:
      0 — no findings
      1 — warnings only
      2 — critical findings
    """
    print(f"\n{OR}{'─'*58}{RST}")
    print(f"{OR}  🛡️   {BOLD}YOLO SECURITY SCAN{RST}")
    print(f"{OR}{'─'*58}{RST}")
    yolignore = Path(start_path) / ".yolignore"
    ignore_note = f"  {DIM}(.yolignore active){RST}" if yolignore.exists() else ""
    print(f"  {DIM}Scanning: {Path(start_path).resolve()}{RST}{ignore_note}\n")

    findings = deep_scan(start_path)

    if not findings:
        print(f"  {GR}{BOLD}✔  All clear — no secrets detected.{RST}\n")
        print(f"{OR}{'─'*58}{RST}\n")
        return 0

    critical = [f for f in findings if f["severity"] == "critical"]
    warnings  = [f for f in findings if f["severity"] == "warning"]

    # Group by file for cleaner output
    by_file: dict[str, list[dict]] = {}
    for f in findings:
        by_file.setdefault(f["file"], []).append(f)

    for fpath, file_findings in by_file.items():
        rel = str(Path(fpath).relative_to(Path(start_path).resolve()) if Path(fpath).is_absolute() else fpath)
        print(f"  {BOLD}{rel}{RST}")
        for f in file_findings:
            sev_color = RED if f["severity"] == "critical" else YL
            sev_icon  = "❌" if f["severity"] == "critical" else "⚠️ "
            line_ref  = f":{f['line']}" if f["line"] else ""
            print(f"    {sev_icon}  {sev_color}{f['label']}{RST}  {DIM}(line{line_ref}){RST}")
            print(f"       {DIM}{f['snippet']}{RST}")
        print()

    print(f"{OR}{'─'*58}{RST}")
    crit_str = f"{RED}{BOLD}{len(critical)} critical{RST}" if critical else f"{DIM}0 critical{RST}"
    warn_str = f"{YL}{len(warnings)} warning{'s' if len(warnings) != 1 else ''}{RST}" if warnings else f"{DIM}0 warnings{RST}"

    # Count unique files
    total_files = len(by_file)
    scanned = _count_files(start_path)
    print(f"  {crit_str}  {warn_str}  {DIM}across {scanned} files scanned ({total_files} with findings){RST}")
    print(f"{OR}{'─'*58}{RST}\n")

    if critical:
        print(f"  {RED}Fix critical findings before committing or deploying.{RST}\n")
        return 2
    return 1


def _count_files(start_path: str) -> int:
    """Count total files scanned (excluding ignored dirs/extensions)."""
    from skills.security import IGNORED_DIRS, IGNORED_FILES
    count = 0
    for _, dirs, files in __import__("os").walk(start_path):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        for f in files:
            if not any(f.endswith(e) for e in IGNORED_FILES):
                count += 1
    return count


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    sys.exit(run_scan(path))
