"""
First-run disclaimer acceptance for YOCO.

On first run, displays the disclaimer and asks for Y/n consent.
On acceptance, writes an acceptance record to ~/.yolo/accepted.json containing:
  - ISO timestamp
  - machine fingerprint (SHA-256 of MAC address)
  - acceptance hash (SHA-256 of fingerprint + timestamp)

The record is local only — it proves the user was shown the disclaimer
and explicitly accepted it.
"""

import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ACCEPTED_FILE = Path.home() / ".yolo" / "accepted.json"

# ── ANSI ──────────────────────────────────────────────────────────────────────
OR   = "\033[38;5;208m"
YL   = "\033[93m"
GR   = "\033[92m"
RD   = "\033[91m"
CY   = "\033[96m"
DIM  = "\033[2m"
BOLD = "\033[1m"
RST  = "\033[0m"

DISCLAIMER = """
YOCO is an experimental AI tool that automatically runs shell commands
and modifies your files. Before you continue, you must understand the risks:

  1. FILE MODIFICATION   YOCO can modify, overwrite, or delete files without
                         explicit confirmation for every change.

  2. SHELL EXECUTION     YOCO runs AI-generated shell commands on your machine.
                         These commands are validated but not guaranteed safe.

  3. AI HALLUCINATION    The underlying LLM is probabilistic. It can generate
                         commands that are technically valid but destructive in
                         your specific context.

  4. NO WARRANTIES       YOCO is provided "as-is" with no guarantees. The
                         authors are not liable for data loss, system damage,
                         or broken environments caused by this tool.

  RECOMMENDATIONS
  ───────────────
  · Run inside Docker / a VM / a disposable environment
  · Always work on a Git branch — never on main with unsaved work
  · Never point YOCO at your only copy of critical data
"""


def _machine_fingerprint() -> str:
    """SHA-256 of the machine's MAC address (locally unique, not reversible)."""
    mac = uuid.getnode()
    return hashlib.sha256(str(mac).encode()).hexdigest()


def _acceptance_hash(fingerprint: str, timestamp: str) -> str:
    return hashlib.sha256(f"{fingerprint}:{timestamp}".encode()).hexdigest()


def _draw_box(text: str) -> None:
    width = 62
    border = f"{OR}{'─' * width}{RST}"
    print(f"\n{border}")
    print(f"{OR}  {BOLD}⚠   YOCO — IMPORTANT DISCLAIMER{RST}")
    print(f"{border}")
    for line in text.splitlines():
        print(f"  {DIM}{line}{RST}")
    print(f"{border}\n")


def check_accepted() -> None:
    """
    If the user has not yet accepted the disclaimer, show it and ask.
    Exits the process if they decline or hit Ctrl+C.
    On acceptance, writes the acceptance record and continues.
    """
    if ACCEPTED_FILE.exists():
        return  # already accepted

    _draw_box(DISCLAIMER)

    print(f"  {CY}Full disclaimer:{RST}  {DIM}https://github.com/erdemozkan/YOLO-CODER/blob/main/DISCLAIMER.md{RST}\n")
    print(f"  By typing {BOLD}y{RST}, you confirm you have read and accept these terms.")
    print(f"  Your acceptance will be recorded locally on this machine.\n")

    try:
        ans = input(f"  {YL}Do you accept? {BOLD}[y/N]{RST} ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print(f"\n\n  {RD}Aborted. YOCO requires acceptance to run.{RST}\n")
        sys.exit(1)

    if ans not in ("y", "yes"):
        print(f"\n  {RD}Declined. YOCO will not run without acceptance.{RST}\n")
        sys.exit(1)

    # Record acceptance
    ACCEPTED_FILE.parent.mkdir(parents=True, exist_ok=True)
    timestamp   = datetime.now(timezone.utc).isoformat()
    fingerprint = _machine_fingerprint()
    record = {
        "accepted_at":        timestamp,
        "machine_fingerprint": fingerprint,
        "acceptance_hash":    _acceptance_hash(fingerprint, timestamp),
    }
    ACCEPTED_FILE.write_text(json.dumps(record, indent=2))

    print(f"\n  {GR}✔  Accepted. Record saved to {ACCEPTED_FILE}{RST}")
    print(f"  {DIM}acceptance_hash: {record['acceptance_hash'][:24]}…{RST}\n")
