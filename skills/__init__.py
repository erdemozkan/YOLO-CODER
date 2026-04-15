# skills/__init__.py
from .security import scan_for_keys
from .code_fixer import apply_code_fix
from .replacer import replace_line

SKILL_REGISTRY = {
    "security_audit": scan_for_keys,
    "apply_code_fix": apply_code_fix,
    "line_replacer": replace_line,
}
