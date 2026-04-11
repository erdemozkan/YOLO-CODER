import os
import sys
import json
import platform
import subprocess
from dataclasses import dataclass, field

# Directories and file extensions to exclude from repo structure scan.
_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".next", ".nuxt", "coverage", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "eggs", "*.egg-info",
}
_SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd", ".so", ".dylib", ".dll",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".mp4", ".mp3", ".pdf", ".zip", ".tar", ".gz",
    ".bin", ".lock", ".whl", ".DS_Store",
}


@dataclass
class ProjectContext:
    # Project identity
    type: str               # "python" | "node" | "typescript" | "rust" | "go" | "unknown"
    package_manager: str    # "pip" | "npm" | "yarn" | "pnpm" | "cargo" | "go" | "unknown"
    declared_deps: list[str] = field(default_factory=list)
    test_runner: str = "unknown"

    # Runtime environment
    os_name: str = ""       # Darwin | Linux | Windows
    os_version: str = ""    # kernel/OS version string
    arch: str = ""          # arm64 | x86_64
    shell: str = ""         # /bin/zsh | /bin/bash | etc.
    cwd: str = ""           # current working directory name

    python_version: str = ""   # e.g. "3.11.4"
    node_version: str = ""     # e.g. "20.1.0" — empty if not found

    # Repository structure stored as a nested dict (JSON-serialisable).
    # Files are represented as null values; directories as nested dicts.
    repo_structure: dict = field(default_factory=dict)


def _build_repo_structure(root: str = ".", max_depth: int = 3) -> dict:
    """
    Walk the current directory up to max_depth levels and return a nested dict.
    Files → None.  Directories → nested dict.
    Skips hidden dirs, build artefacts, and binary file types.
    """
    def _walk(path: str, depth: int) -> dict:
        result = {}
        try:
            entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name))
        except PermissionError:
            return result

        for entry in entries:
            if entry.name.startswith(".") and entry.name not in (".env",):
                continue
            if entry.name in _SKIP_DIRS:
                continue

            if entry.is_dir(follow_symlinks=False):
                if depth < max_depth:
                    result[entry.name] = _walk(entry.path, depth + 1)
                else:
                    result[entry.name] = {}   # truncated — too deep
            else:
                _, ext = os.path.splitext(entry.name)
                if ext.lower() in _SKIP_EXTENSIONS:
                    continue
                result[entry.name] = None

        return result

    return _walk(root, 1)


def _read_deps_requirements(path: str) -> list[str]:
    deps = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("-"):
                    # Strip version specifiers: requests>=2.0 → requests
                    pkg = line.split(">=")[0].split("<=")[0].split("==")[0].split("!=")[0].split("~=")[0]
                    deps.append(pkg.strip().lower())
    except Exception:
        pass
    return deps


def _read_deps_pyproject(path: str) -> list[str]:
    deps = []
    try:
        with open(path) as f:
            content = f.read()
        # Naive line-based parse — avoids requiring toml library
        in_deps = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped in ("[project.dependencies]", "dependencies = [", "dependencies=["):
                in_deps = True
                continue
            if in_deps:
                if stripped.startswith("[") or stripped == "]":
                    in_deps = False
                    continue
                pkg = stripped.strip('",').split(">=")[0].split("<=")[0].split("==")[0]
                if pkg:
                    deps.append(pkg.strip().lower())
    except Exception:
        pass
    return deps


def _read_deps_package_json(path: str) -> list[str]:
    deps = []
    try:
        with open(path) as f:
            data = json.load(f)
        for section in ("dependencies", "devDependencies"):
            deps.extend(data.get(section, {}).keys())
    except Exception:
        pass
    return deps


def _run(cmd: list[str]) -> str:
    """Run a subprocess and return stdout, or empty string on failure."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        return result.stdout.strip()
    except Exception:
        return ""


def detect_project() -> ProjectContext:
    """
    Inspect the current working directory and environment, returning a
    fully-populated ProjectContext. Always safe to call — never raises.
    """
    cwd = os.getcwd()

    # --- OS / environment ---
    os_name = platform.system()           # Darwin | Linux | Windows
    os_version = platform.release()       # kernel version string
    arch = platform.machine()             # arm64 | x86_64
    shell = os.environ.get("SHELL", "unknown")
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    node_version = _run(["node", "--version"]).lstrip("v")  # "20.1.0" or ""

    # --- Project type detection (order matters — most specific first) ---
    files = set(os.listdir(cwd))

    # TypeScript
    if "tsconfig.json" in files:
        proj_type = "typescript"
        pm = "npm"
        if "yarn.lock" in files:
            pm = "yarn"
        elif "pnpm-lock.yaml" in files:
            pm = "pnpm"
        deps = _read_deps_package_json(os.path.join(cwd, "package.json"))
        test_runner = "jest" if "jest.config.js" in files or "jest.config.ts" in files else "unknown"

    # Node.js
    elif "package.json" in files:
        proj_type = "node"
        pm = "npm"
        if "yarn.lock" in files:
            pm = "yarn"
        elif "pnpm-lock.yaml" in files:
            pm = "pnpm"
        deps = _read_deps_package_json(os.path.join(cwd, "package.json"))
        test_runner = "jest" if "jest.config.js" in files else "mocha" if "mocha" in str(deps) else "unknown"

    # Rust
    elif "Cargo.toml" in files:
        proj_type = "rust"
        pm = "cargo"
        deps = []
        test_runner = "cargo test"

    # Go
    elif "go.mod" in files:
        proj_type = "go"
        pm = "go"
        deps = []
        test_runner = "go test"

    # Python — prefer pyproject.toml, fall back to requirements.txt / setup.py
    elif any(f in files for f in ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg")):
        proj_type = "python"
        pm = "pip"
        if "pyproject.toml" in files:
            deps = _read_deps_pyproject(os.path.join(cwd, "pyproject.toml"))
        elif "requirements.txt" in files:
            deps = _read_deps_requirements(os.path.join(cwd, "requirements.txt"))
        else:
            deps = []
        test_runner = "pytest" if ("pytest.ini" in files or "pyproject.toml" in files or "conftest.py" in files) else "unittest"

    else:
        proj_type = "unknown"
        pm = "unknown"
        deps = []
        test_runner = "unknown"

    # --- Repo structure ---
    repo_structure = _build_repo_structure(cwd)

    return ProjectContext(
        type=proj_type,
        package_manager=pm,
        declared_deps=deps,
        test_runner=test_runner,
        os_name=os_name,
        os_version=os_version,
        arch=arch,
        shell=shell,
        cwd=os.path.basename(cwd),
        python_version=python_version,
        node_version=node_version,
        repo_structure=repo_structure,
    )


def flat_file_list(repo_structure: dict, prefix: str = "") -> list[str]:
    """Flatten the nested repo_structure dict into a list of relative paths."""
    paths = []
    for name, value in repo_structure.items():
        full = f"{prefix}{name}" if not prefix else f"{prefix}/{name}"
        if value is None:
            paths.append(full)
        elif isinstance(value, dict):
            paths.append(full + "/")
            paths.extend(flat_file_list(value, full))
    return paths
