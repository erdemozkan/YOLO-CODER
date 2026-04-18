"""
YOLO full-pipeline provider for YOLO-Bench.

Runs the same three-layer fix pipeline that yoco.py uses at runtime:
  1. Interceptors  — 23 deterministic regex rules, zero LLM calls
  2. Fix Memory    — cached successful fixes from past runs
  3. LLM fallback  — calls the local Ollama model (default: yolo-7b)

This lets the benchmark measure the complete system, not just the LLM layer.
"""

import os
import sys
from pathlib import Path
from collections import namedtuple

# Add the YOLO repo root to sys.path so core.* imports resolve
YOLO_ROOT = Path(__file__).resolve().parents[3]
if str(YOLO_ROOT) not in sys.path:
    sys.path.insert(0, str(YOLO_ROOT))

# Patch os.uname to always report Linux so OS-branching interceptors
# (e.g. Docker daemon: open -a Docker vs systemctl start docker) take
# the Linux path — matching benchmark expected answers.
_UnameTuple = namedtuple("uname_result", ["sysname", "nodename", "release", "version", "machine"])
os.uname = lambda: _UnameTuple("Linux", "bench", "5.15.0", "#1 SMP", "x86_64")

from core.interceptors import run_auto_intercept
from core.memory import recall
from models.ollama import predict as ollama_predict


def predict(error: str, model: str = "yolo-7b") -> str:
    """
    Run the full YOLO fix pipeline against an error string.

    Returns the predicted fix command as a bare string.
    source is embedded in the string prefix for reporting if needed,
    but callers (run_eval.py) just use the raw command.
    """

    # ── Layer 1: Interceptors ─────────────────────────────────────────────────
    # dry_run=True: skip any actual file writes — we only want the command.
    fix = run_auto_intercept(error, dry_run=True)
    if fix is not None:
        cmd = fix.command.strip()
        # File-patch interceptors return echo '...' — not a real fix command
        # for command-based eval. Skip them and fall through.
        if not cmd.startswith("echo '"):
            return cmd

    # ── Layer 2: Fix Memory ───────────────────────────────────────────────────
    record = recall(error)
    if record and record.get("command"):
        return record["command"].strip()

    # ── Layer 3: LLM (Ollama) ─────────────────────────────────────────────────
    return ollama_predict(error, model=model)
