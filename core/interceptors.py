import re
import os
import glob
import stat
from core.snapshot import take_snapshot
from core.schema import FixResult

# Known pip-installable packages that are commonly mistaken for local modules.
# Module name (as it appears in the ImportError) → pip package name.
_PIP_PACKAGES = {
    "requests": "requests",
    "flask": "flask",
    "django": "django",
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "numpy": "numpy",
    "pandas": "pandas",
    "scipy": "scipy",
    "sklearn": "scikit-learn",
    "matplotlib": "matplotlib",
    "PIL": "Pillow",
    "cv2": "opencv-python",
    "yaml": "pyyaml",
    "dotenv": "python-dotenv",
    "rich": "rich",
    "colorama": "colorama",
    "pydantic": "pydantic",
    "sqlalchemy": "sqlalchemy",
    "aiohttp": "aiohttp",
    "httpx": "httpx",
    "boto3": "boto3",
    "paramiko": "paramiko",
    "cryptography": "cryptography",
    "jwt": "PyJWT",
    "bs4": "beautifulsoup4",
    "lxml": "lxml",
    "toml": "toml",
    "click": "click",
    "typer": "typer",
    "pytest": "pytest",
    "pyfiglet": "pyfiglet",
    "redis": "redis",
    "celery": "celery",
    "openai": "openai",
    "anthropic": "anthropic",
    "google.generativeai": "google-generativeai",
}


def run_auto_intercept(
    error_msg,
    declared_deps: list[str] | None = None,
    dry_run: bool = False,
) -> FixResult | None:
    """
    Checks for common errors that we can fix instantly using hardcoded heuristics.
    Returns a FixResult on match, or None if no interceptor matched.

    When dry_run=True interceptors that write files will skip the write but still
    return a FixResult so yolo.py can display what would have happened.
    """

    # --- 1. SyntaxError: Missing Colon ---
    if "SyntaxError: expected ':'" in error_msg:
        matches = re.findall(r'File "(.*?)", line (\d+)', error_msg)
        if matches:
            filepath = matches[-1][0]
            line_idx = int(matches[-1][1]) - 1
            try:
                with open(filepath, "r") as f:
                    lines = f.readlines()

                original_line = lines[line_idx].rstrip("\n")
                indent = len(original_line) - len(original_line.lstrip())
                new_content = original_line + ":\n" + (" " * (indent + 4)) + "pass\n"

                if not dry_run:
                    take_snapshot(filepath)
                    lines[line_idx] = new_content
                    with open(filepath, "w") as f:
                        f.writelines(lines)

                return FixResult(
                    command=f"echo 'Fixed colon in {filepath}'",
                    summary="Detected a missing colon.",
                    plan=f"Append colon + indented pass block to line {matches[-1][1]} of {filepath}.",
                    source="interceptor",
                )
            except Exception:
                pass

    # --- 2. TypeError: String Concatenation ---
    if "TypeError: can only concatenate str" in error_msg:
        matches = re.findall(r'File "(.*?)", line (\d+)', error_msg)
        if matches:
            filepath = matches[-1][0]
            line_idx = int(matches[-1][1]) - 1
            try:
                with open(filepath, "r") as f:
                    lines = f.readlines()

                original_line = lines[line_idx]
                new_line = re.sub(r"\+\s+([a-zA-Z0-9_\.]+)", r"+ str(\1)", original_line)
                if new_line == original_line:
                    new_line = re.sub(r"([a-zA-Z0-9_\.]+)\s+\+", r"str(\1) +", original_line)

                if not dry_run:
                    take_snapshot(filepath)
                    lines[line_idx] = new_line
                    with open(filepath, "w") as f:
                        f.writelines(lines)

                return FixResult(
                    command=f"echo 'Fixed TypeError in {filepath}'",
                    summary="Detected string concatenation with a non-string type.",
                    plan=f"Wrap non-string variable with str() on line {matches[-1][1]} of {filepath}.",
                    source="interceptor",
                )
            except Exception:
                pass

    # --- 3. NameError: Undefined Variable ---
    if "NameError: name " in error_msg:
        matches = re.findall(r'File "(.*?)", line (\d+)', error_msg)
        var_match = re.search(r"NameError: name '(.*?)' is not defined", error_msg)
        if matches and var_match:
            filepath = matches[-1][0]
            line_idx = int(matches[-1][1]) - 1
            var_name = var_match.group(1)
            try:
                with open(filepath, "r") as f:
                    lines = f.readlines()

                original_line = lines[line_idx]
                indent = len(original_line) - len(original_line.lstrip())
                new_line = (" " * indent) + f'{var_name} = "auto_fixed_payload"\n'

                if not dry_run:
                    take_snapshot(filepath)
                    lines.insert(line_idx, new_line)
                    with open(filepath, "w") as f:
                        f.writelines(lines)

                return FixResult(
                    command=f"echo 'Fixed NameError in {filepath}'",
                    summary="Detected an undefined variable.",
                    plan=f"Inject `{var_name} = \"auto_fixed_payload\"` above line {matches[-1][1]} of {filepath}.",
                    source="interceptor",
                )
            except Exception:
                pass

    # --- 4. FileNotFoundError: Missing JSON ---
    if "FileNotFoundError:" in error_msg and ".json'" in error_msg:
        match = re.search(r"No such file or directory: '(.*\.json)'", error_msg)
        if match:
            missing_file = match.group(1)
            try:
                if not dry_run:
                    take_snapshot(missing_file)
                    with open(missing_file, "w") as f:
                        f.write("{}\n")

                return FixResult(
                    command=f"echo 'Auto-created JSON file: {missing_file}'",
                    summary="Detected a missing JSON file.",
                    plan=f"Create {missing_file} with content: {{}}.",
                    source="interceptor",
                )
            except Exception:
                pass

    # --- 5. JSONDecodeError: Empty JSON File ---
    if "json.decoder.JSONDecodeError: Expecting value" in error_msg:
        try:
            affected = [
                f for f in glob.glob("**/*.json", recursive=True)
                if os.path.getsize(f) == 0
            ]
            if affected:
                if not dry_run:
                    for json_file in affected:
                        take_snapshot(json_file)
                        with open(json_file, "w") as f:
                            f.write("{}\n")

                return FixResult(
                    command=f"echo 'Initialized empty JSON files: {', '.join(affected)}'",
                    summary="Detected empty JSON file(s) causing a crash.",
                    plan=f"Initialize with {{}} : {', '.join(affected)}.",
                    source="interceptor",
                )
        except Exception:
            pass

    # --- 6. TypeScript TS2307: Missing Module ---
    if "error TS2307: Cannot find module" in error_msg:
        match = re.search(r"Cannot find module '(.*?)'", error_msg)
        if match:
            missing_module = match.group(1)
            try:
                if not dry_run:
                    os.makedirs(f"node_modules/{missing_module}", exist_ok=True)
                    take_snapshot(f"node_modules/{missing_module}/index.ts")
                    with open(f"node_modules/{missing_module}/index.ts", "w") as f:
                        f.write("export const fakeHelper: any = {};\nexport default {};\n")

                return FixResult(
                    command=f"echo 'Auto-created mock npm module: {missing_module}'",
                    summary="Detected a missing TypeScript module.",
                    plan=f"Create node_modules/{missing_module}/index.ts with a stub export.",
                    source="interceptor",
                )
            except Exception:
                pass

    # --- 7. PermissionError: Read-only file ---
    if "PermissionError" in error_msg and "Permission denied" in error_msg:
        match = re.search(r"PermissionError: \[Errno 13\] Permission denied: '(.*?)'", error_msg)
        if match:
            filepath = match.group(1)
            try:
                file_stat = os.stat(filepath)
                is_executable = bool(file_stat.st_mode & stat.S_IXUSR)
                # If the file is a script that needs execute rights, handle in interceptor 8
                if not is_executable and os.path.isfile(filepath):
                    return FixResult(
                        command=f"chmod 644 {filepath}",
                        summary=f"Read-only file blocking write: {filepath}",
                        plan="Grant write permission with chmod 644.",
                        source="interceptor",
                    )
            except Exception:
                pass

    # --- 8. PermissionError: Non-executable script ---
    if "PermissionError" in error_msg and "Permission denied" in error_msg:
        match = re.search(r"PermissionError: \[Errno 13\] Permission denied: '(.*?)'", error_msg)
        if match:
            filepath = match.group(1)
            if filepath.endswith(".sh") or filepath.startswith("./"):
                try:
                    return FixResult(
                        command=f"chmod +x {filepath}",
                        summary=f"Script not executable: {filepath}",
                        plan="Grant execute permission with chmod +x.",
                        source="interceptor",
                    )
                except Exception:
                    pass

    # --- 9. FileNotFoundError: Missing directory (non-JSON) ---
    if "FileNotFoundError" in error_msg and ".json'" not in error_msg:
        match = re.search(r"No such file or directory: '(.*?)'", error_msg)
        if match:
            missing_path = match.group(1)
            parent_dir = os.path.dirname(missing_path)
            if parent_dir and not os.path.exists(parent_dir):
                try:
                    return FixResult(
                        command=f"mkdir -p {parent_dir}",
                        summary=f"Missing directory: {parent_dir}",
                        plan="Create the missing directory tree with mkdir -p.",
                        source="interceptor",
                    )
                except Exception:
                    pass

    # --- 10. Port already in use ---
    if "Address already in use" in error_msg or "OSError: [Errno 48]" in error_msg or "OSError: [Errno 98]" in error_msg:
        match = re.search(r":(\d{2,5})", error_msg)
        if match:
            port = match.group(1)
            try:
                return FixResult(
                    command=f"lsof -ti :{port} | xargs kill -9",
                    summary=f"Port {port} is already in use.",
                    plan=f"Kill the process occupying port {port}.",
                    source="interceptor",
                )
            except Exception:
                pass

    # --- 11. ModuleNotFoundError: Known pip package ---
    # Priority: declared_deps from pyproject.toml/requirements.txt first,
    # then fall back to the hardcoded _PIP_PACKAGES dict.
    if "ModuleNotFoundError: No module named" in error_msg:
        mod_match = re.search(r"No module named '([^']+)'", error_msg)
        if mod_match:
            module_name = mod_match.group(1).split(".")[0]

            # Check declared deps first — most accurate signal
            pip_name = None
            if declared_deps:
                for dep in declared_deps:
                    if dep.lower() == module_name.lower():
                        pip_name = dep  # use the name exactly as declared
                        break

            # Fall back to hardcoded known-packages map
            if not pip_name:
                pip_name = _PIP_PACKAGES.get(module_name)

            if pip_name:
                try:
                    return FixResult(
                        command=f"pip install {pip_name}",
                        summary=f"Missing pip package: {pip_name}",
                        plan=f"Install '{pip_name}' via pip.",
                        source="interceptor",
                    )
                except Exception:
                    pass

    # If no interceptors match, pass it to the Brain
    return None
