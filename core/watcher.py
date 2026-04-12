"""
YOLO Watch Mode — Sub-Agent
============================
Standalone file watcher that re-invokes `yolo <cmd>` whenever a source
file changes.  Launched by yolo.py when --watch is detected; runs as an
independent process so the fix logic stays fully decoupled.

Usage (internal):
    python3 -m core.watcher <command tokens...>
"""

import os
import sys
import subprocess
import time
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
WATCH_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".sh", ".toml", ".yaml", ".yml", ".env"}
POLL_INTERVAL    = 0.5   # seconds between scans
IGNORE_DIRS      = {"__pycache__", ".git", "node_modules", ".venv", "venv", ".mypy_cache", ".pytest_cache"}

# ── ANSI ──────────────────────────────────────────────────────────────────────
OR   = "\033[38;5;208m"
YL   = "\033[93m"
GR   = "\033[92m"
CY   = "\033[96m"
DIM  = "\033[2m"
BOLD = "\033[1m"
RST  = "\033[0m"


def _scan(root: Path) -> dict[str, float]:
    """Return {filepath: mtime} for all watched files under root."""
    snapshot = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for fname in filenames:
            if Path(fname).suffix in WATCH_EXTENSIONS:
                fpath = os.path.join(dirpath, fname)
                try:
                    snapshot[fpath] = os.stat(fpath).st_mtime
                except OSError:
                    pass
    return snapshot


def _changed(old: dict, new: dict) -> list[str]:
    """Return list of files that were added or modified."""
    changed = []
    for path, mtime in new.items():
        if path not in old or old[path] != mtime:
            changed.append(path)
    return changed


def _run_yolo(cmd_tokens: list[str], root: Path) -> int:
    """Run `python3 yolo.py <cmd>` and stream output. Returns exit code."""
    full_cmd = [sys.executable, str(root / "yolo.py")] + cmd_tokens
    proc = subprocess.Popen(full_cmd, cwd=str(root))
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        proc.wait()
    return proc.returncode


def _confirm(cmd: str, root: Path) -> bool:
    """Explain watch mode and ask for Y/N confirmation."""
    exts = ", ".join(sorted(WATCH_EXTENSIONS))
    print(f"\n{OR}{'─'*58}{RST}")
    print(f"{OR}  ⚡  {BOLD}WATCH MODE{RST}")
    print(f"{OR}{'─'*58}{RST}")
    print(f"  {DIM}Project  :{RST}  {root}")
    print(f"  {DIM}Command  :{RST}  {YL}{cmd}{RST}")
    print(f"  {DIM}Watching :{RST}  {DIM}{exts}{RST}")
    print(f"  {DIM}Interval :{RST}  {POLL_INTERVAL}s")
    print(f"\n  On any file change → re-runs the command.")
    print(f"  On failure → YOLO auto-fixes and retries.")
    print(f"  Press {BOLD}Ctrl+C{RST} at any time to stop.\n")
    print(f"{OR}{'─'*58}{RST}")
    try:
        ans = input(f"\n  Continue? {BOLD}[y/N]{RST} ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print()
        return False
    return ans in ("y", "yes")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 -m core.watcher <command tokens...>")
        sys.exit(1)

    cmd_tokens = sys.argv[1:]
    cmd_str    = " ".join(cmd_tokens)
    root       = Path(__file__).parent.parent.resolve()

    if not _confirm(cmd_str, root):
        print(f"\n  {DIM}Watch mode cancelled.{RST}\n")
        sys.exit(0)

    print(f"\n{GR}  ✔  Watch mode started.{RST}  {DIM}(Ctrl+C to stop){RST}\n")

    # Initial run
    print(f"{OR}  ⚡  {DIM}Running initial check…{RST}\n")
    _run_yolo(cmd_tokens, root)

    # Seed the file snapshot after the initial run
    snapshot = _scan(root)

    print(f"\n{CY}  👁  Watching for changes…{RST}  {DIM}{cmd_str}{RST}\n")

    try:
        while True:
            time.sleep(POLL_INTERVAL)
            current = _scan(root)
            changed = _changed(snapshot, current)

            if changed:
                snapshot = current
                rel = [os.path.relpath(f, root) for f in changed]
                print(f"\n{YL}  ✦  Change detected:{RST}  {DIM}{', '.join(rel)}{RST}")
                print(f"{OR}  ⚡  Re-running…{RST}\n")
                _run_yolo(cmd_tokens, root)
                print(f"\n{CY}  👁  Watching for changes…{RST}  {DIM}{cmd_str}{RST}\n")
                # Re-seed after YOLO may have modified files
                snapshot = _scan(root)

    except KeyboardInterrupt:
        print(f"\n\n{OR}  ⚡  {BOLD}Watch mode stopped.{RST}  {DIM}Goodbye!{RST}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
