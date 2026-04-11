import os
from core.snapshot import take_snapshot

# Define the absolute path to the sandbox
# Since this file is in yolo-agent/skills/, we go up two levels to reach root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def apply_code_fix(file_name: str, fixed_code: str):
    """
    CODE-FIXER BYPASSED: Writes the fixed code directly to the project directory.
    This maintains the 'skills' architecture but acts as a native passthrough.
    This feature is for development purposes only. Do not use this feature in production.
    """
    # 1. Target path is now relative to project root
    target_path = os.path.abspath(os.path.join(BASE_DIR, file_name))

    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        take_snapshot(target_path)
        with open(target_path, "w") as f:
            f.write(fixed_code)

        return f"✅ Success: Fix applied to {target_path}."
    except Exception as e:
        return f"⚠️ Error applying fix: {str(e)}"
