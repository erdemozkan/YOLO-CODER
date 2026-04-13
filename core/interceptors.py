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
    return a FixResult so yoco.py can display what would have happened.
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
                # Scripts needing execute rights are handled by interceptor 8
                is_script = filepath.endswith(".sh") or filepath.startswith("./")
                if not is_executable and os.path.isfile(filepath) and not is_script:
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

    # ── NODE.JS ───────────────────────────────────────────────────────────────

    # --- 12. Node.js: Cannot find module (runtime require()) ---
    if "Cannot find module" in error_msg and "error TS" not in error_msg:
        match = re.search(r"Cannot find module '([^']+)'", error_msg)
        if match:
            mod = match.group(1)
            # Relative path → missing local file, not an npm package
            if mod.startswith("."):
                missing_file = mod if mod.endswith((".js", ".ts")) else mod + ".js"
                return FixResult(
                    command=f"touch {missing_file}",
                    summary=f"Missing local module: {mod}",
                    plan=f"Create stub file {missing_file} so require() resolves.",
                    source="interceptor",
                )
            else:
                # Strip scope/subpath to get installable package name
                pkg = mod.split("/")[0] if not mod.startswith("@") else "/".join(mod.split("/")[:2])
                return FixResult(
                    command=f"npm install {pkg}",
                    summary=f"Missing npm package: {pkg}",
                    plan=f"Install '{pkg}' via npm.",
                    source="interceptor",
                )

    # --- 13. npm ERR! — missing package / failed install ---
    if "npm ERR!" in error_msg:
        # npm ERR! 404 → package doesn't exist, nothing safe to do, skip
        if "404" in error_msg:
            pass
        else:
            # ENOENT — node_modules missing entirely
            if "ENOENT" in error_msg or "Cannot find" in error_msg:
                return FixResult(
                    command="npm install",
                    summary="npm: node_modules missing or incomplete",
                    plan="Run npm install to restore all dependencies.",
                    source="interceptor",
                )
            # peer dep / ERESOLVE conflicts
            if "ERESOLVE" in error_msg or "peer dep" in error_msg.lower():
                return FixResult(
                    command="npm install --legacy-peer-deps",
                    summary="npm: peer dependency conflict",
                    plan="Retry install with --legacy-peer-deps to bypass strict peer resolution.",
                    source="interceptor",
                )

    # --- 14. TypeScript compile errors (beyond TS2307) ---
    # TS2304: Cannot find name → likely missing type declaration
    if "error TS2304: Cannot find name" in error_msg:
        match = re.search(r"Cannot find name '([^']+)'", error_msg)
        if match:
            name = match.group(1)
            return FixResult(
                command="npm install --save-dev @types/node",
                summary=f"TypeScript: unknown name '{name}'",
                plan="Install @types/node — covers most global Node.js names.",
                source="interceptor",
            )

    # TS2345 / TS2322: type mismatch — report only, no safe auto-fix
    # TS2339: Property does not exist
    if "error TS2339: Property" in error_msg:
        match = re.search(r"Property '([^']+)' does not exist on type '([^']+)'", error_msg)
        if match:
            prop, typ = match.groups()
            return FixResult(
                command=f"echo 'TS2339: Property {prop!r} missing on {typ!r} — fix type or cast'",
                summary=f"TypeScript: property '{prop}' missing on type '{typ}'",
                plan="Cast the object with `as any` or extend the interface to include the property.",
                source="interceptor",
            )

    # ── DOCKER ────────────────────────────────────────────────────────────────

    # --- 15. Docker: image not found / pull required ---
    if "Unable to find image" in error_msg or \
       ("docker" in error_msg.lower() and "No such image" in error_msg):
        match = re.search(r"Unable to find image '([^']+)'", error_msg) or \
                re.search(r"No such image: ([^\s]+)", error_msg)
        if match:
            image = match.group(1)
            return FixResult(
                command=f"docker pull {image}",
                summary=f"Docker image not found: {image}",
                plan=f"Pull image '{image}' from the registry.",
                source="interceptor",
            )

    # --- 16. Docker: port already in use (bind error) ---
    if "driver failed programming external connectivity" in error_msg or \
       ("docker" in error_msg.lower() and "address already in use" in error_msg.lower()):
        match = re.search(r":(\d{2,5})", error_msg)
        if match:
            port = match.group(1)
            return FixResult(
                command=f"lsof -ti :{port} | xargs kill -9",
                summary=f"Docker port conflict on :{port}",
                plan=f"Kill the process holding port {port} so Docker can bind to it.",
                source="interceptor",
            )

    # --- 17. Docker: container name already in use ---
    if "Conflict. The container name" in error_msg or \
       "is already in use by container" in error_msg:
        match = re.search(r'The container name "?/?([^"]+)"? is already in use', error_msg)
        if match:
            name = match.group(1).lstrip("/")
            return FixResult(
                command=f"docker rm -f {name}",
                summary=f"Docker container name conflict: {name}",
                plan=f"Remove the existing container '{name}' so the new one can start.",
                source="interceptor",
            )

    # --- 18. Docker: daemon not running ---
    if "Cannot connect to the Docker daemon" in error_msg or \
       "Is the docker daemon running" in error_msg:
        return FixResult(
            command="open -a Docker" if os.uname().sysname == "Darwin" else "sudo systemctl start docker",
            summary="Docker daemon is not running",
            plan="Start the Docker daemon.",
            source="interceptor",
        )

    # ── GIT ───────────────────────────────────────────────────────────────────

    # --- 19. Git: merge conflict present ---
    if "CONFLICT" in error_msg and "Merge conflict" in error_msg or \
       ("Automatic merge failed" in error_msg and "fix conflicts" in error_msg):
        return FixResult(
            command="git merge --abort",
            summary="Git merge conflict detected",
            plan="Abort the conflicting merge so the repo returns to a clean state. Re-merge manually after resolving.",
            source="interceptor",
        )

    # --- 20. Git: detached HEAD ---
    if "HEAD detached at" in error_msg or "detached HEAD" in error_msg.lower():
        # Try to find the default branch
        default_branch = "main"
        try:
            import subprocess
            out = subprocess.check_output(
                ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
                stderr=subprocess.DEVNULL, text=True
            ).strip()
            default_branch = out.split("/")[-1] or "main"
        except Exception:
            pass
        return FixResult(
            command=f"git checkout {default_branch}",
            summary="Git HEAD is detached",
            plan=f"Re-attach HEAD by checking out '{default_branch}'.",
            source="interceptor",
        )

    # --- 21. Git: push rejected (non-fast-forward) ---
    if "rejected" in error_msg and ("non-fast-forward" in error_msg or "fetch first" in error_msg):
        return FixResult(
            command="git pull --rebase && git push",
            summary="Git push rejected — remote has diverged",
            plan="Rebase local commits on top of the remote, then push.",
            source="interceptor",
        )

    # --- 22. Git: nothing to push / up to date ---
    if "Everything up-to-date" in error_msg or \
       ("git" in error_msg.lower() and "nothing to commit" in error_msg):
        return FixResult(
            command="echo 'Git: already up-to-date, nothing to push'",
            summary="Git: nothing to push",
            plan="Working tree and remote are already in sync.",
            source="interceptor",
        )

    # --- 23. Git: not a git repository ---
    if "not a git repository" in error_msg.lower():
        return FixResult(
            command="git init",
            summary="Not a git repository",
            plan="Initialise a new git repo in the current directory.",
            source="interceptor",
        )

    # If no interceptors match, pass it to the Brain
    return None
