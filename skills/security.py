import os
import re

# ── Secret patterns ────────────────────────────────────────────────────────────
# Each entry: "Label" → (regex, severity)   severity: "critical" | "warning"
SECRET_PATTERNS = {
    "OpenAI API Key":        (r"sk-[a-zA-Z0-9]{30,}",                               "critical"),
    "Anthropic API Key":     (r"sk-ant-api03-[a-zA-Z0-9\-_]{90,}",                  "critical"),
    "Google API Key":        (r"AIza[0-9A-Za-z\-_]{35}",                            "critical"),
    "AWS Access Key":        (r"AKIA[0-9A-Z]{16}",                                  "critical"),
    "AWS Secret Key":        (r"(?i)aws_secret_access_key\s*=\s*['\"]?[A-Za-z0-9/+=]{40}", "critical"),
    "GitHub Token":          (r"ghp_[a-zA-Z0-9]{36}",                               "critical"),
    "GitHub OAuth":          (r"gho_[a-zA-Z0-9]{36}",                               "critical"),
    "Stripe Secret Key":     (r"sk_live_[0-9a-zA-Z]{24}",                           "critical"),
    "Stripe Publishable Key":(r"pk_live_[0-9a-zA-Z]{24}",                           "warning"),
    "Slack Token":           (r"xox[baprs]-[0-9a-zA-Z\-]{10,}",                     "critical"),
    "Private Key Block":     (r"-----BEGIN [A-Z ]+ PRIVATE KEY-----",               "critical"),
    "Certificate Block":     (r"-----BEGIN CERTIFICATE-----",                       "warning"),
    "Hardcoded Password":    (r"(?i)password\s*=\s*['\"][^'\"]{4,}['\"]",           "critical"),
    "Hardcoded Secret":      (r"(?i)secret\s*=\s*['\"][^'\"]{4,}['\"]",             "critical"),
    "Hardcoded API Key":     (r"(?i)api_key\s*=\s*['\"][^'\"]{4,}['\"]",            "critical"),
    "Hardcoded Token":       (r"(?i)token\s*=\s*['\"][^'\"]{8,}['\"]",              "warning"),
    "Bearer Token":          (r"(?i)bearer\s+[a-zA-Z0-9\-_\.=]{20,}",              "warning"),
    "Database URL":          (r"(?i)(postgres|mysql|mongodb)://[^\s'\"]+",           "critical"),
    "Generic Secret Key":    (r"(?i)secret_key\s*=\s*['\"][^'\"]{4,}['\"]",         "critical"),
}

# Files that are always suspicious regardless of content
SENSITIVE_FILENAMES = {
    ".env", ".env.local", ".env.production", ".env.staging",
    "credentials.json", "secrets.json", "secret.json",
    "id_rsa", "id_ed25519", "id_ecdsa",
}

IGNORED_DIRS  = {".git", "node_modules", "venv", ".venv", "__pycache__", ".next", "dist", "build", ".mypy_cache", "YOLO-MODEL-FILES"}
IGNORED_FILES = {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
                 ".exe", ".lock", ".bin", ".woff", ".woff2", ".ttf", ".eot", ".pdf",
                 ".gguf", ".safetensors", ".pt", ".pth", ".ckpt", ".h5"}
SKIP_FILES    = {"yolo.py", "security.py"}   # don't flag the tool itself


# ── Core scanner ──────────────────────────────────────────────────────────────

def scan_for_keys(start_path="."):
    """
    Legacy interface — used by the existing security gate in yolo.py.
    Returns list of (file_path, key_type) tuples.
    """
    results = deep_scan(start_path)
    return [(r["file"], r["label"]) for r in results if r["severity"] == "critical"]


def _load_yolignore(start_path: str) -> tuple[set[str], set[tuple[str, int]]]:
    """
    Parse .yolignore from start_path.
    Returns:
      ignored_files  — set of file paths to skip entirely
      ignored_lines  — set of (file, lineno) tuples to skip
    """
    ignored_files: set[str] = set()
    ignored_lines: set[tuple[str, int]] = set()
    ignore_path = os.path.join(start_path, ".yolignore")
    if not os.path.isfile(ignore_path):
        return ignored_files, ignored_lines

    with open(ignore_path) as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                parts = line.rsplit(":", 1)
                try:
                    fpath = os.path.normpath(os.path.join(start_path, parts[0]))
                    ignored_lines.add((fpath, int(parts[1])))
                except ValueError:
                    ignored_files.add(os.path.normpath(os.path.join(start_path, line)))
            else:
                ignored_files.add(os.path.normpath(os.path.join(start_path, line)))

    return ignored_files, ignored_lines


def deep_scan(start_path=".") -> list[dict]:
    """
    Full scan. Returns list of finding dicts:
      { file, line, label, severity, snippet }
    Sorted: critical first, then by file path.
    """
    findings = []
    ignored_files, ignored_lines = _load_yolignore(start_path)

    for root, dirs, files in os.walk(start_path):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

        for fname in files:
            if fname in SKIP_FILES:
                continue
            if any(fname.endswith(ext) for ext in IGNORED_FILES):
                continue

            fpath = os.path.join(root, fname)
            fpath_norm = os.path.normpath(fpath)

            # Skip files listed in .yolignore
            if fpath_norm in ignored_files:
                continue

            # Flag sensitive filenames unconditionally
            if fname in SENSITIVE_FILENAMES:
                findings.append({
                    "file":     fpath,
                    "line":     0,
                    "label":    "Sensitive file",
                    "severity": "critical",
                    "snippet":  f"File name: {fname}",
                })
                continue

            try:
                with open(fpath, "r", errors="ignore") as f:
                    lines = f.readlines()
            except Exception:
                continue

            for lineno, line in enumerate(lines, 1):
                # Skip lines suppressed in .yolignore
                if (fpath_norm, lineno) in ignored_lines:
                    continue
                for label, (pattern, severity) in SECRET_PATTERNS.items():
                    if re.search(pattern, line):
                        snippet = line.strip()[:80]
                        findings.append({
                            "file":     fpath,
                            "line":     lineno,
                            "label":    label,
                            "severity": severity,
                            "snippet":  snippet,
                        })
                        break  # one finding per line

    findings.sort(key=lambda r: (0 if r["severity"] == "critical" else 1, r["file"]))
    return findings
