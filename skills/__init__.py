# skills/__init__.py
from .security import scan_for_keys
from .code_fixer import apply_code_fix
from .lab import run_in_sandbox
from .replacer import replace_line

SKILL_REGISTRY = {
    "security_audit": scan_for_keys,
    "apply_code_fix": apply_code_fix,
    "run_in_sandbox": run_in_sandbox,
    "line_replacer": replace_line,
}
