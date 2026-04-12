"""
YOLO --explain renderer
=======================
After a successful fix, shows:
  - What changed  (before/after diff with line numbers)
  - Why it changed (plain-English from the FixResult summary/plan)
  - Where it came from (interceptor / llm / memory)
"""

import re
import shutil
from pathlib import Path
from core.schema import FixResult

# ── ANSI ──────────────────────────────────────────────────────────────────────
GR   = "\033[92m"
RED  = "\033[91m"
YL   = "\033[93m"
CY   = "\033[96m"
OR   = "\033[38;5;208m"
DIM  = "\033[2m"
BOLD = "\033[1m"
RST  = "\033[0m"

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")
def _vis(s): return len(_ANSI_RE.sub("", s))
def _pad(s, w): return s + " " * max(0, w - _vis(s))

_SOURCE_LABEL = {
    "interceptor": f"{CY}interceptor{RST}  {DIM}(hardcoded heuristic — no LLM needed){RST}",
    "llm":         f"{YL}LLM{RST}          {DIM}(model generated this fix){RST}",
    "memory":      f"{GR}memory{RST}       {DIM}(recalled from past successful fix){RST}",
    "fallback":    f"{RED}fallback{RST}     {DIM}(AI failed — generic fix applied){RST}",
}


def _parse_yolo_replace(command: str):
    m = re.search(r"python3 yolo_replace\.py\s+(\S+)\s+(\d+)\s+(.*)", command)
    if not m:
        return None
    filepath, line_num, new_text = m.groups()
    if (new_text.startswith("'") and new_text.endswith("'")) or \
       (new_text.startswith('"') and new_text.endswith('"')):
        new_text = new_text[1:-1]
    new_text = new_text.replace("\\n", "\n")
    return filepath, int(line_num), new_text


def _diff_block(filepath: str, line_num: int, new_text: str, context: int = 3) -> str:
    """Render a before/after diff block around the changed line."""
    path = Path(filepath)
    if not path.exists():
        return ""

    try:
        current_lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return ""

    # The file has already been modified — reconstruct original by swapping back
    line_idx = line_num - 1
    if line_idx < 0 or line_idx >= len(current_lines):
        return ""

    new_line     = new_text.rstrip("\n")
    current_line = current_lines[line_idx]   # this is the NEW line (already applied)

    # We need the OLD line — read from snapshot if possible
    from core import snapshot as _snap
    abs_path = str(path.resolve())
    old_content = _snap._snapshots.get(abs_path)
    if old_content is not None:
        old_lines   = old_content.decode(errors="replace").splitlines()
        old_line    = old_lines[line_idx] if line_idx < len(old_lines) else ""
    else:
        old_line = f"{DIM}(original not available){RST}"

    term_w  = shutil.get_terminal_size((120, 40)).columns
    half_w  = max(38, (term_w - 9) // 2)
    gutter  = len(str(line_num + context))
    start   = max(0, line_idx - context)
    end     = min(len(current_lines), line_idx + context + 1)

    sep = f"{DIM}{'─' * min(term_w, 100)}{RST}"
    out = [sep]

    # Column headers
    lh = _pad(f"{DIM}  BEFORE{RST}", half_w)
    rh = f"{DIM}  AFTER{RST}"
    out.append(f"  {' ' * gutter}  {lh}  {DIM}│{RST}  {rh}")
    out.append(sep)

    for i in range(start, end):
        ln = i + 1
        g  = f"{DIM}{ln:>{gutter}}{RST}"
        if i == line_idx:
            lc = _pad(f"{RED}- {_trunc(old_line, half_w-2)}{RST}", half_w + len(RED)+len(RST))
            rc = f"{GR}+ {_trunc(current_line, half_w-2)}{RST}"
            out.append(f"  {g}  {lc}  {DIM}│{RST}  {rc}")
        else:
            ctx = _trunc(current_lines[i], half_w - 2)
            lc  = _pad(f"{DIM}  {ctx}{RST}", half_w + 2*len(DIM)+len(RST))
            out.append(f"  {g}  {lc}  {DIM}│{RST}  {DIM}  {ctx}{RST}")

    out.append(sep)
    return "\n".join(out)


def _trunc(s: str, w: int) -> str:
    return s[:w-1] + "…" if len(s) > w else s


def render_explain(result: FixResult, original_stderr: str) -> str:
    """Build the full --explain output block."""
    out = []
    out.append(f"\n{OR}{'─'*58}{RST}")
    out.append(f"{OR}  ⚡  {BOLD}EXPLAIN{RST}")
    out.append(f"{OR}{'─'*58}{RST}\n")

    # Source
    src_label = _SOURCE_LABEL.get(result.source, result.source)
    out.append(f"  {DIM}Source  :{RST}  {src_label}")

    # What happened
    out.append(f"  {DIM}Error   :{RST}  {YL}{result.summary}{RST}")

    # Plan
    out.append(f"  {DIM}Plan    :{RST}  {result.plan}\n")

    # Diff (only for yolo_replace commands)
    parsed = _parse_yolo_replace(result.command)
    if parsed:
        filepath, line_num, new_text = parsed
        out.append(f"  {DIM}File    :{RST}  {filepath}  {DIM}line {line_num}{RST}\n")
        diff = _diff_block(filepath, line_num, new_text)
        if diff:
            out.append(diff)
    else:
        out.append(f"  {DIM}Command :{RST}  {CY}{result.command}{RST}")

    out.append(f"\n{OR}{'─'*58}{RST}\n")
    return "\n".join(out)
