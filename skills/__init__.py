# skills/__init__.py
import subprocess
from .security import scan_for_keys
from .code_fixer import apply_code_fix
from .replacer import replace_line


def _run_in_sandbox(cmd: str):
    """Execute a shell command and return (exit_code, stdout, stderr)."""
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True
    )
    return result.returncode, result.stdout, result.stderr


SKILL_REGISTRY = {
    "run_in_sandbox": _run_in_sandbox,
    "security_audit": scan_for_keys,
    "apply_code_fix": apply_code_fix,
    "line_replacer": replace_line,
}
