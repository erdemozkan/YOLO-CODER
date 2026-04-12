"""
YOLO Fix Memory
===============
Remembers fix commands that successfully resolved past errors.
Checked before the LLM — if a match is found, the LLM call is skipped entirely.

Storage: ~/.yolo/fix_memory.jsonl  (one JSON record per line)

Record format:
  {
    "fingerprint": "<error type>|<normalised call site>",
    "command":     "python3 yolo_replace.py ...",
    "hits":        3,        # times this fix was applied successfully
    "last_seen":   "2026-04-12T10:00:00"
  }
"""

import json
import os
import re
from datetime import datetime

MEMORY_FILE = os.path.expanduser("~/.yolo/fix_memory.jsonl")

# Minimum hits before a remembered fix is trusted
_MIN_CONFIDENCE = 1


# ── Fingerprinting ─────────────────────────────────────────────────────────────

def _fingerprint(error_msg: str) -> str | None:
    """
    Derive a stable key from stderr that generalises across projects.

    Strategy:
      1. Extract the error type  (e.g. "ZeroDivisionError: division by zero")
      2. Extract the function name where it crashed (last frame)
      3. Strip file paths, line numbers, and memory addresses — those change
         per project and per run.

    Returns None if the error is too ambiguous to fingerprint.
    """
    # Extract the error type line (last line of traceback or first Error: line)
    error_type = None
    for line in reversed(error_msg.strip().splitlines()):
        line = line.strip()
        if re.match(r"[A-Za-z][\w\.]*Error[:\s]", line) or \
           re.match(r"[A-Za-z][\w\.]*Exception[:\s]", line) or \
           re.match(r"[A-Za-z][\w\.]*Warning[:\s]", line):
            error_type = line[:120]
            break

    if not error_type:
        return None

    # Normalise: strip memory addresses, numbers in brackets, quoted file paths
    error_type = re.sub(r"0x[0-9a-fA-F]+", "0xADDR", error_type)
    error_type = re.sub(r"\bat 0x\w+", "", error_type)
    error_type = re.sub(r"'[^']*\.py'", "'FILE'", error_type)

    # Extract the innermost function name from the traceback
    frames = re.findall(r'in (\w+)\s*$', error_msg, re.MULTILINE)
    call_site = frames[-1] if frames else "unknown"

    return f"{error_type}|{call_site}"


# ── Read / write ───────────────────────────────────────────────────────────────

def _load() -> list[dict]:
    if not os.path.exists(MEMORY_FILE):
        return []
    records = []
    try:
        with open(MEMORY_FILE) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except OSError:
        pass
    return records


def _save(records: list[dict]) -> None:
    try:
        os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
        with open(MEMORY_FILE, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
    except OSError:
        pass


# ── Public API ─────────────────────────────────────────────────────────────────

def recall(error_msg: str) -> dict | None:
    """
    Look up a remembered fix for this error.
    Returns the memory record if found and confident, else None.
    """
    fp = _fingerprint(error_msg)
    if not fp:
        return None

    for record in _load():
        if record.get("fingerprint") == fp and record.get("hits", 0) >= _MIN_CONFIDENCE:
            return record

    return None


def remember(error_msg: str, command: str) -> None:
    """
    Record that `command` successfully fixed this error.
    Increments hit count if already known, otherwise creates a new record.
    """
    fp = _fingerprint(error_msg)
    if not fp:
        return

    records = _load()
    for record in records:
        if record.get("fingerprint") == fp and record.get("command") == command:
            record["hits"] = record.get("hits", 1) + 1
            record["last_seen"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            _save(records)
            return

    # New entry
    records.append({
        "fingerprint": fp,
        "command":     command,
        "hits":        1,
        "last_seen":   datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    })
    _save(records)


def forget(error_msg: str) -> bool:
    """
    Remove memory entries for this error fingerprint.
    Called when a remembered fix fails — so we don't keep applying a broken fix.
    Returns True if anything was removed.
    """
    fp = _fingerprint(error_msg)
    if not fp:
        return False

    records = _load()
    before = len(records)
    records = [r for r in records if r.get("fingerprint") != fp]
    if len(records) < before:
        _save(records)
        return True
    return False
