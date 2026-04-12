"""
YOLO history — append-only run log at ~/.yolo/history.jsonl
Each line is one JSON record written at the end of every YOLO run.
"""

import json
import os
import shutil
import re
from datetime import datetime

HISTORY_FILE = os.path.expanduser("~/.yolo/history.jsonl")
MAX_ENTRIES  = 200   # trim file to this many lines on write

# ── ANSI ──────────────────────────────────────────────────────────────────────
OR   = "\033[38;5;208m"
GR   = "\033[92m"
RED  = "\033[91m"
YL   = "\033[93m"
CY   = "\033[96m"
DIM  = "\033[2m"
BOLD = "\033[1m"
RST  = "\033[0m"

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")
def _vis(s): return len(_ANSI_RE.sub("", s))
def _pad(s, w): return s + " " * max(0, w - _vis(s))


# ── Writer ─────────────────────────────────────────────────────────────────────

def record(
    command: str,
    outcome: str,           # "fixed" | "failed" | "dry_run"
    error: str,
    fix_command: str,
    source: str,            # "llm" | "interceptor" | "memory" | "fallback" | ""
    attempts: int,
    files_modified: list[str],
) -> None:
    """Append one run record to the history file."""
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)

    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "command": command,
        "outcome": outcome,
        "error": error.strip().splitlines()[0][:200] if error.strip() else "",
        "fix_command": fix_command,
        "source": source,
        "attempts": attempts,
        "files_modified": files_modified,
    }

    with open(HISTORY_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

    _trim()


def _trim() -> None:
    """Keep history file from growing beyond MAX_ENTRIES lines."""
    try:
        with open(HISTORY_FILE) as f:
            lines = f.readlines()
        if len(lines) > MAX_ENTRIES:
            with open(HISTORY_FILE, "w") as f:
                f.writelines(lines[-MAX_ENTRIES:])
    except OSError:
        pass


def clear() -> None:
    """Wipe the history file."""
    try:
        os.remove(HISTORY_FILE)
    except FileNotFoundError:
        pass


# ── Reader ─────────────────────────────────────────────────────────────────────

def load(n: int = 10) -> list[dict]:
    """Return the last n entries (most recent last → reversed for display)."""
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE) as f:
            lines = [l.strip() for l in f if l.strip()]
        entries = []
        for line in lines[-n:]:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return list(reversed(entries))   # newest first
    except OSError:
        return []


# ── Renderer ───────────────────────────────────────────────────────────────────

_OUTCOME_ICON = {
    "fixed":   f"{GR}✅ fixed  {RST}",
    "failed":  f"{RED}💀 failed {RST}",
    "dry_run": f"{YL}🔍 dry-run{RST}",
}

_SOURCE_COLOR = {
    "interceptor": CY,
    "llm":         YL,
    "memory":      GR,
    "fallback":    RED,
}


def _fmt_ts(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%b %d %H:%M")
    except ValueError:
        return ts[:16]


def render_list(entries: list[dict]) -> str:
    """Render a compact numbered table for the picker."""
    if not entries:
        return f"{YL}  No history yet.{RST}"

    term_w = shutil.get_terminal_size((120, 40)).columns
    sep = f"{DIM}{'─' * min(term_w, 100)}{RST}"

    col_date = 12
    col_out  = 10
    col_src  = 13
    col_cmd  = max(20, (term_w - 6 - col_date - col_out - col_src - 6))

    header = (
        f"  {DIM}{'#':>2}  "
        f"{'Date':<{col_date}}  "
        f"{'Outcome':<10}  "
        f"{'Source':<11}  "
        f"Command{RST}"
    )

    rows = [f"\n{sep}", header, sep]
    for i, e in enumerate(entries, 1):
        icon   = _OUTCOME_ICON.get(e.get("outcome", ""), e.get("outcome", ""))
        sc     = _SOURCE_COLOR.get(e.get("source", ""), DIM)
        src    = f"{sc}{e.get('source', ''):<11}{RST}"
        cmd    = e.get("command", "")
        if len(cmd) > col_cmd:
            cmd = cmd[:col_cmd - 1] + "…"
        date   = _fmt_ts(e.get("timestamp", ""))
        rows.append(f"  {CY}{i:>2}{RST}  {DIM}{date:<{col_date}}{RST}  {icon}  {src}  {cmd}")
    rows.append(sep)
    return "\n".join(rows)


def render_detail(entry: dict) -> str:
    """Render a full detail view for one history entry."""
    sep = f"{OR}{'─' * 58}{RST}"
    lines = [
        f"\n{sep}",
        f"{OR}  ⚡  {BOLD}HISTORY DETAIL{RST}",
        sep,
        f"  {DIM}Date     :{RST}  {_fmt_ts(entry.get('timestamp', ''))}",
        f"  {DIM}Outcome  :{RST}  {_OUTCOME_ICON.get(entry.get('outcome',''), entry.get('outcome',''))}",
        f"  {DIM}Source   :{RST}  {entry.get('source', '')}",
        f"  {DIM}Attempts :{RST}  {entry.get('attempts', '')}",
        f"  {DIM}Command  :{RST}  {entry.get('command', '')}",
        f"  {DIM}Error    :{RST}  {YL}{entry.get('error', '(none)')}{RST}",
        f"  {DIM}Fix      :{RST}  {GR}{entry.get('fix_command', '(none)')}{RST}",
    ]
    files = entry.get("files_modified", [])
    if files:
        lines.append(f"  {DIM}Files    :{RST}")
        for f in files:
            lines.append(f"             {DIM}{f}{RST}")
    lines.append(sep + "\n")
    return "\n".join(lines)
