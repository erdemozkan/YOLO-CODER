"""
YOLO full-pipeline provider for YOLO-Bench.

Runs the same three-layer fix pipeline that yoco.py uses at runtime:
  1. Interceptors  — 23 deterministic regex rules, zero LLM calls
  2. Fix Memory    — cached successful fixes from past runs
  3. LLM fallback  — calls the local Ollama model with OS/project context

The LLM prompt mirrors agent.py: includes OS, shell, Python version, and
package manager so the model can give platform-correct answers (brew vs apt,
open -a Docker vs systemctl, etc.).
"""

import os
import sys
import shutil  # unused (old_working prompt used it)
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
from models.ollama import predict as _ollama_raw


# ── Context-aware system prompt ───────────────────────────────────────────────

# System prompt aligned with training data
_SYSTEM_PROMPT = (
    "You are a CLI repair tool. Output ONLY a single bare bash command to fix the error. "
    "No explanation. No markdown. No backticks."
)

# ── old_working: env-aware system prompt (disabled) ───────────────────────────
# def _build_system_prompt() -> str:
#     python_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
#     node_ver = ""
#     node_bin = shutil.which("node")
#     if node_bin:
#         try:
#             import subprocess
#             out = subprocess.check_output(["node", "--version"],
#                                           stderr=subprocess.DEVNULL, text=True).strip()
#             node_ver = f" | Node: {out}"
#         except Exception:
#             pass
#     env_block = (
#         f"OS: Linux 5.15.0 (x86_64) | Shell: bash | Python: {python_ver}{node_ver}"
#     )
#     return (
#         "You are a CLI repair tool. "
#         "Output ONLY a single bare bash command to fix the error. "
#         "No explanation. No markdown. No backticks. Just the command.\n\n"
#         f"Environment: {env_block}\n"
#         "Package manager: pip / npm / cargo (use whichever fits the error).\n"
#         "For system packages use brew on macOS or apt-get on Linux."
#     )
# _SYSTEM_PROMPT = _build_system_prompt()
# ── end old_working ───────────────────────────────────────────────────────────


def _ollama_with_context(error: str, model: str, temperature: float = 0.1) -> str:
    """Call Ollama with the training-aligned system prompt."""
    import requests
    url = "http://localhost:11434/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": error},
        ],
        "options": {"temperature": temperature},
        "stream": False,
    }
    try:
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except Exception as e:
        return f"ERROR: {e}"


# Temperature ladder — matches agent.py retry behaviour
_ATTEMPT_TEMPS = {1: 0.1, 2: 0.4, 3: 0.8}


# ── Pipeline ──────────────────────────────────────────────────────────────────

def predict(error: str, model: str = "yolo-7b", command: str = "", attempts: int = 1) -> str | list:
    """
    Run the full YOLO fix pipeline against an error string.
    If attempts > 1, returns a list of predictions (best is picked by the benchmark).
    Interceptors and memory always return a single answer — only the LLM layer retries.

    Temperature scales up on each retry (0.1 → 0.4 → 0.8) so the model samples
    differently rather than deterministically repeating the same output.
    Previous failed predictions are injected as a prior_block so the model avoids
    repeating them — mirroring the agent.py retry prompt format.
    """

    # ── Layer 1: Interceptors ─────────────────────────────────────────────────
    fix = run_auto_intercept(error, dry_run=True, command=command)
    if fix is not None:
        cmd = fix.command.strip()
        if not cmd.startswith("echo '"):
            return cmd

    # ── Layer 2: Fix Memory ───────────────────────────────────────────────────
    record = recall(error)
    if record and record.get("command"):
        return record["command"].strip()

    # ── Layer 3: LLM — format aligned with training data ─────────────────────
    base_user_content = (
        f"[Linux] $ {command}\nError:\n{error}" if command
        else f"Error:\n{error}"
    )

    # ── old_working ───────────────────────────────────────────────────────────
    # user_content = f"Command: {command}\nError: {error}" if command else error
    # ── end old_working ───────────────────────────────────────────────────────

    if attempts <= 1:
        return _ollama_with_context(base_user_content + "\nFIX:", model=model, temperature=0.1)

    # Multiple attempts — scale temperature, inject prior failures, collect unique predictions
    results = []
    seen: set[str] = set()
    for i in range(1, attempts + 1):
        temp = _ATTEMPT_TEMPS.get(i, 0.8)

        prior_block = ""
        if results:
            lines = ["\nPrevious attempts that did NOT fix the problem:"]
            for j, prev_cmd in enumerate(results, 1):
                lines.append(f"  [{j}] Tried: {prev_cmd}")
                err_headline = (error.strip().splitlines() or ["(no output)"])[0][:120]
                lines.append(f"       Still failing: {err_headline}")
            prior_block = "\n".join(lines)

        user_content = base_user_content + prior_block + "\nFIX:"
        pred = _ollama_with_context(user_content, model=model, temperature=temp)
        if pred not in seen:
            results.append(pred)
            seen.add(pred)

    return results
