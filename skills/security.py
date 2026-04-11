import os
import re

# --- SECURITY CONFIGURATION ---
SECRET_PATTERNS = {
    "OpenAI API Key": r"sk-[a-zA-Z0-9]{30,}",
    "Anthropic Key": r"sk-ant-api03-[a-zA-Z0-9\-_]{90,100}",
    "Google API Key": r"AIza[0-9A-Za-z\\-_]{35}",
    "AWS Access Key": r"AKIA[0-9A-Z]{16}",
    "Generic Secret": r"(?i)secret_key|password|api_key|token",
    "Private Key": r"-----BEGIN [A-Z ]+ PRIVATE KEY-----",
}

IGNORED_DIRS = {".git", "node_modules", "venv", "__pycache__", ".next", "dist", "build"}


def scan_for_keys(start_path="."):
    """
    Scans the directory for exposed API keys and secrets.
    Returns a list of tuples: [(file_path, key_type)]
    """
    leaks_found = []

    for root, dirs, files in os.walk(start_path):
        # Prevent scanning massive/irrelevant directories
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

        for file in files:
            # Skip compiled binaries and the tool itself
            if file.endswith((".pyc", ".png", ".jpg", ".exe", ".lock", ".bin")):
                continue
            if file == "yolo.py":
                continue

            file_path = os.path.join(root, file)
            try:
                with open(file_path, "r", errors="ignore") as f:
                    content = f.read()

                    # Check the file content against our regex patterns
                    for name, pattern in SECRET_PATTERNS.items():
                        if re.search(pattern, content):
                            leaks_found.append((file_path, name))
            except Exception:
                # If a file can't be read (permissions, etc.), just skip it
                continue

    return leaks_found
