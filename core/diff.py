"""
YOLO diff renderer — side-by-side diff for --dry-run preview.
"""

import re
import shutil
from pathlib import Path

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


def _parse_yolo_replace(command: str):
    """
    Extract (filepath, line_number, new_text) from a yolo_replace command.
    Returns None if not a yolo_replace command.
    """
    m = re.search(r"python3 yolo_replace\.py\s+(\S+)\s+(\d+)\s+(.*)", command)
    if not m:
        return None
    filepath, line_num, new_text = m.groups()
    # Strip surrounding quotes
    if (new_text.startswith("'") and new_text.endswith("'")) or \
       (new_text.startswith('"') and new_text.endswith('"')):
        new_text = new_text[1:-1]
    new_text = new_text.replace("\\n", "\n")
    return filepath, int(line_num), new_text


def render_diff(command: str, context_lines: int = 3) -> str:
    """
    Given a fix command, return a formatted diff string.
    For yolo_replace commands: shows a side-by-side before/after diff.
    For other commands: shows a plain command preview.
    """
    parsed = _parse_yolo_replace(command)
    if not parsed:
        return _plain_preview(command)

    filepath, line_num, new_text = parsed
    path = Path(filepath)

    if not path.exists():
        return _plain_preview(command)

    try:
        original_lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return _plain_preview(command)

    line_idx = line_num - 1
    if line_idx < 0 or line_idx >= len(original_lines):
        return _plain_preview(command)

    old_line = original_lines[line_idx]
    new_line = new_text.rstrip("\n")

    # Context window
    start = max(0, line_idx - context_lines)
    end   = min(len(original_lines), line_idx + context_lines + 1)

    term_w   = shutil.get_terminal_size((120, 40)).columns
    half_w   = max(40, (term_w - 7) // 2)   # 7 = " │ " + line number gutter
    gutter_w = len(str(end))

    lines_out = []
    sep = f"{DIM}{'─' * term_w}{RST}"

    lines_out.append(f"\n{OR}  ⚡  {BOLD}DRY-RUN DIFF{RST}  {DIM}{filepath}  line {line_num}{RST}")
    lines_out.append(sep)

    # Header
    left_hdr  = _pad(f"{DIM}  BEFORE{RST}", half_w)
    right_hdr = _pad(f"{DIM}  AFTER{RST}",  half_w)
    lines_out.append(f"{' ' * (gutter_w + 2)}{left_hdr}  {DIM}│{RST}  {right_hdr}")
    lines_out.append(sep)

    for i in range(start, end):
        lineno = i + 1
        gutter = f"{DIM}{lineno:>{gutter_w}}{RST}"

        if i == line_idx:
            # Changed line — highlight in red (left) and green (right)
            left_txt  = f"{RED}- {_truncate(old_line, half_w - 2)}{RST}"
            right_txt = f"{GR}+ {_truncate(new_line, half_w - 2)}{RST}"
            left_pad  = _pad(left_txt,  half_w + len(RED) + len(RST))
            lines_out.append(f" {gutter}  {left_pad}  {DIM}│{RST}  {right_txt}")
        else:
            # Context line — same on both sides
            ctx = _truncate(original_lines[i], half_w - 2)
            ctx_col = f"{DIM}  {ctx}{RST}"
            left_pad = _pad(ctx_col, half_w + 2 * len(DIM) + len(RST))
            lines_out.append(f" {gutter}  {left_pad}  {DIM}│{RST}  {DIM}  {ctx}{RST}")

    lines_out.append(sep)
    lines_out.append(f"  {DIM}Command :{RST}  {CY}{command}{RST}")
    lines_out.append(f"  {DIM}Source  :{RST}  ")  # filled in by caller
    lines_out.append("")

    return "\n".join(lines_out)


def _truncate(s: str, max_w: int) -> str:
    if len(s) > max_w:
        return s[:max_w - 1] + "…"
    return s


def _plain_preview(command: str) -> str:
    """Fallback for non-yolo_replace commands."""
    OR_ = "\033[38;5;208m"
    return (
        f"\n{OR_}  ⚡  {BOLD}DRY-RUN PREVIEW{RST}\n"
        f"  {DIM}Command :{RST}  {CY}{command}{RST}\n"
        f"  {DIM}Note    :{RST}  {DIM}No file diff available for this command type.{RST}\n"
    )
