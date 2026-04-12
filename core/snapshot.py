import os
import json
import base64
from datetime import datetime

# Maps absolute file path → original content (bytes).
# Only the FIRST snapshot per file is kept — preserves the true pre-YOLO state
# even if the same file is modified multiple times across attempts.
_snapshots: dict[str, bytes | None] = {}

SESSION_FILE = os.path.expanduser("~/.yolo/last_session.json")


def _persist(command: str) -> None:
    """Write current in-memory snapshots to disk so --rollback works after exit."""
    os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
    payload = {
        "timestamp": datetime.now().isoformat(),
        "command": command,
        "files": {
            path: base64.b64encode(content).decode() if content is not None else None
            for path, content in _snapshots.items()
        },
    }
    with open(SESSION_FILE, "w") as f:
        json.dump(payload, f, indent=2)


# Stored once per run so _persist() can include it without being passed each time.
_current_command: str = ""


def set_command(command: str) -> None:
    """Called once at the start of a YOLO run to tag the session."""
    global _current_command
    _current_command = command


def take_snapshot(filepath: str) -> None:
    """
    Capture the current content of a file before YOLO modifies it.
    Safe to call multiple times for the same file — only the first call is stored.
    If the file does not exist yet, stores None so rollback knows to delete it.
    Persists to disk after every new capture.
    """
    abs_path = os.path.abspath(filepath)
    if abs_path in _snapshots:
        return  # Already captured — don't overwrite the original

    if os.path.exists(abs_path):
        with open(abs_path, "rb") as f:
            _snapshots[abs_path] = f.read()
    else:
        # File will be created by the fix — mark it for deletion on rollback
        _snapshots[abs_path] = None

    _persist(_current_command)


def _apply_snapshots(snapshots: dict[str, bytes | None]) -> list[str]:
    """Shared restore logic for both in-memory and disk rollback."""
    restored = []
    for abs_path, original_content in snapshots.items():
        try:
            if original_content is None:
                if os.path.exists(abs_path):
                    os.remove(abs_path)
                    restored.append(f"deleted  {abs_path}")
            else:
                os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                with open(abs_path, "wb") as f:
                    f.write(original_content)
                restored.append(f"restored {abs_path}")
        except Exception as e:
            restored.append(f"FAILED   {abs_path} ({e})")
    return restored


def rollback_all() -> list[str]:
    """
    Restore every snapshotted file to its pre-YOLO state (in-memory path).
    Used automatically at the end of a failed run.
    Does NOT delete the session file — keeps it available for manual --rollback.
    """
    restored = _apply_snapshots(_snapshots)
    _snapshots.clear()
    return restored


def rollback_from_disk() -> tuple[list[str], str]:
    """
    Read ~/.yolo/last_session.json and restore all files to their pre-YOLO state.
    Used by the --rollback flag in a new process after a previous run.
    Returns (list of result strings, original command string).
    """
    if not os.path.exists(SESSION_FILE):
        return [], ""

    with open(SESSION_FILE) as f:
        payload = json.load(f)

    command = payload.get("command", "")
    snapshots: dict[str, bytes | None] = {}
    for path, encoded in payload.get("files", {}).items():
        snapshots[path] = base64.b64decode(encoded) if encoded is not None else None

    restored = _apply_snapshots(snapshots)

    # Clear the session file so the same rollback can't be run twice
    os.remove(SESSION_FILE)

    return restored, command


def rollback_file(filepath: str) -> tuple[str, str]:
    """
    Restore a single file from the last session on disk.
    Returns (status, command) where status is a result string.
    Does NOT remove the session file — other files are still restorable.
    """
    if not os.path.exists(SESSION_FILE):
        return "no_session", ""

    with open(SESSION_FILE) as f:
        payload = json.load(f)

    command = payload.get("command", "")
    abs_path = os.path.abspath(filepath)

    # Try to match by absolute path or by basename
    files = payload.get("files", {})
    matched_key = None
    for key in files:
        if key == abs_path or os.path.basename(key) == os.path.basename(filepath):
            matched_key = key
            break

    if matched_key is None:
        return "not_found", command

    encoded = files[matched_key]
    original_content = base64.b64decode(encoded) if encoded is not None else None

    try:
        if original_content is None:
            if os.path.exists(matched_key):
                os.remove(matched_key)
            result = f"deleted  {matched_key}"
        else:
            os.makedirs(os.path.dirname(matched_key), exist_ok=True)
            with open(matched_key, "wb") as f:
                f.write(original_content)
            result = f"restored {matched_key}"
    except Exception as e:
        result = f"FAILED   {matched_key} ({e})"

    # Remove this file from the session so it can't be rolled back twice
    del payload["files"][matched_key]
    if payload["files"]:
        with open(SESSION_FILE, "w") as f:
            json.dump(payload, f, indent=2)
    else:
        os.remove(SESSION_FILE)

    return result, command


def list_session_files() -> tuple[list[str], str]:
    """
    Return (list of file paths in last session, original command).
    Used by --rollback to show what's restorable.
    """
    if not os.path.exists(SESSION_FILE):
        return [], ""
    with open(SESSION_FILE) as f:
        payload = json.load(f)
    return list(payload.get("files", {}).keys()), payload.get("command", "")


def clear_snapshots() -> None:
    """
    Discard in-memory snapshots without restoring (called on success).
    Keeps the disk session file so the user can still run --rollback manually.
    """
    _snapshots.clear()


def modified_files() -> list[str]:
    """Return the list of absolute paths that were snapshotted this run."""
    return list(_snapshots.keys())
