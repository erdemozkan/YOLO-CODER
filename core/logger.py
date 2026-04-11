"""
Run history logger.

Appends one JSON record per YOLO run to ~/.yolo/history.jsonl.
All I/O happens only in flush() — the rest of the run is in-memory.
Safe to use even if the log file or directory doesn't exist yet.
"""

import json
import os
from datetime import datetime
from core.config import ModelConfig
from core.schema import FixResult

HISTORY_FILE = os.path.expanduser("~/.yolo/history.jsonl")


class RunLogger:
    def __init__(self, command: str, cfg: ModelConfig, dry_run: bool = False):
        self._record: dict = {
            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "command": command,
            "provider": cfg.provider,
            "model": cfg.model,
            "dry_run": dry_run,
            "outcome": "unknown",
            "attempts": [],
            "files_modified": [],
            "rolled_back": False,
        }
        self._attempt_number = 0

    def record_attempt(
        self,
        result: FixResult,
        fix_exit_code: int,
        retry_exit_code: int | None,
        retry_stderr: str = "",
    ) -> None:
        """
        Call once per loop iteration after the fix has been applied and
        the original command has been retried.

        fix_exit_code   — exit code of the fix command itself
        retry_exit_code — exit code of the original command after the fix
                          (None if the fix command itself failed and we didn't retry)
        """
        self._attempt_number += 1
        headline = ""
        if retry_stderr:
            headline = retry_stderr.strip().splitlines()[0][:200]

        self._record["attempts"].append({
            "number": self._attempt_number,
            "source": result.source,
            "fix_command": result.command,
            "summary": result.summary,
            "plan": result.plan,
            "fix_exit_code": fix_exit_code,
            "retry_exit_code": retry_exit_code,
            "retry_stderr_headline": headline,
        })

    def flush(
        self,
        outcome: str,
        files_modified: list[str] | None = None,
        rolled_back: bool = False,
    ) -> None:
        """
        Finalise the record and append it to history.jsonl.

        outcome      — "success" | "failed" | "rolled_back" | "dry_run"
        files_modified — list of absolute paths touched this run
        rolled_back  — True if rollback_all() was called
        """
        self._record["outcome"] = outcome
        self._record["files_modified"] = files_modified or []
        self._record["rolled_back"] = rolled_back

        try:
            os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
            with open(HISTORY_FILE, "a") as f:
                f.write(json.dumps(self._record) + "\n")
        except Exception:
            pass  # Logging must never crash the main tool
