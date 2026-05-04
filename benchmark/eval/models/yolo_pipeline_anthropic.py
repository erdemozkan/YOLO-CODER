"""
YOLO pipeline with Anthropic as the LLM fallback.
Interceptors → Fix Memory → Claude (with multi-attempt retry).
Requires ANTHROPIC_API_KEY in environment.
"""

import os
import sys
from pathlib import Path
from collections import namedtuple

_UnameTuple = namedtuple("uname_result", ["sysname", "nodename", "release", "version", "machine"])
os.uname = lambda: _UnameTuple("Linux", "bench", "5.15.0", "#1 SMP", "x86_64")

YOLO_ROOT = Path(__file__).resolve().parents[3]
if str(YOLO_ROOT) not in sys.path:
    sys.path.insert(0, str(YOLO_ROOT))

from core.interceptors import run_auto_intercept
from core.memory import recall
import anthropic

SYSTEM_PROMPT = (
    "You are a CLI repair tool. Output ONLY a single bare bash command to fix the error. "
    "No explanation. No markdown. No backticks. Just the command."
)

_ATTEMPT_TEMPS = {1: 0.1, 2: 0.4, 3: 0.8}


def _call_anthropic(user_content: str, model: str, temperature: float) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    client = anthropic.Anthropic(api_key=api_key)
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=128,
            temperature=temperature,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        return resp.content[0].text.strip()
    except Exception as e:
        return f"ERROR: {e}"


def predict(error: str, model: str = "claude-sonnet-4-6", command: str = "", attempts: int = 1) -> str | list:
    # Layer 1: Interceptors
    fix = run_auto_intercept(error, dry_run=True, command=command)
    if fix is not None:
        cmd = fix.command.strip()
        if not cmd.startswith("echo '"):
            return cmd

    # Layer 2: Fix Memory
    record = recall(error)
    if record and record.get("command"):
        return record["command"].strip()

    # Layer 3: Anthropic LLM
    base_content = (
        f"[Linux] $ {command}\nError:\n{error}" if command
        else f"Error:\n{error}"
    )

    if attempts <= 1:
        return _call_anthropic(base_content + "\nFIX:", model=model, temperature=0.1)

    results = []
    seen: set[str] = set()
    for i in range(1, attempts + 1):
        temp = _ATTEMPT_TEMPS.get(i, 0.8)
        prior_block = ""
        if results:
            lines = ["\nPrevious attempts that did NOT fix the problem:"]
            for j, prev_cmd in enumerate(results, 1):
                err_headline = (error.strip().splitlines() or ["(no output)"])[0][:120]
                lines.append(f"  [{j}] Tried: {prev_cmd}")
                lines.append(f"       Still failing: {err_headline}")
            prior_block = "\n".join(lines)
        pred = _call_anthropic(base_content + prior_block + "\nFIX:", model=model, temperature=temp)
        if pred not in seen:
            results.append(pred)
            seen.add(pred)

    return results
