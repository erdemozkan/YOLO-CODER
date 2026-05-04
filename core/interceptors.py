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
    command: str = "",
) -> FixResult | None:
    """
    Checks for common errors that we can fix instantly using hardcoded heuristics.
    Returns a FixResult on match, or None if no interceptor matched.

    When dry_run=True interceptors that write files will skip the write but still
    return a FixResult so yoco.py can display what would have happened.

    command: the original shell command that produced the error (optional).
    Command-aware interceptors can extract package names or other details from it.
    """

    # ── COMMAND-AWARE INTERCEPTORS ────────────────────────────────────────────

    # --- pip_001: externally-managed-environment → add --break-system-packages ---
    if "externally-managed-environment" in error_msg or \
       "This environment is externally managed" in error_msg:
        # Extract the package name from the original command if available
        pkg = ""
        if command:
            m = re.search(r"pip(?:3)?\s+install\s+(?:--\S+\s+)*([A-Za-z0-9_\-\.]+)", command)
            if m:
                pkg = m.group(1)
        if pkg:
            return FixResult(
                command=f"pip install {pkg} --break-system-packages",
                summary="pip: externally-managed-environment",
                plan=f"Re-run pip install with --break-system-packages for '{pkg}'.",
                source="interceptor",
            )
        # Fallback without command context
        return FixResult(
            command="pip install --break-system-packages",
            summary="pip: externally-managed-environment",
            plan="Re-run pip install with --break-system-packages.",
            source="interceptor",
        )

    # --- pip_002: Permission denied on system site-packages → add --user ---
    if ("ERROR: Could not install packages due to an OSError" in error_msg or
            "PermissionError" in error_msg) and \
       "Permission denied" in error_msg and \
       ("/lib/python" in error_msg or "/local/lib" in error_msg):
        pkg = ""
        if command:
            m = re.search(r"pip(?:3)?\s+install\s+(?:--\S+\s+)*([A-Za-z0-9_\-\.]+)", command)
            if m:
                pkg = m.group(1)
        if pkg:
            return FixResult(
                command=f"pip install {pkg} --user",
                summary="pip: Permission denied on system site-packages",
                plan=f"Install '{pkg}' into user site-packages with --user.",
                source="interceptor",
            )
        return FixResult(
            command="pip install --user",
            summary="pip: Permission denied on system site-packages",
            plan="Install into user site-packages with --user.",
            source="interceptor",
        )

    # --- pip_003: package name uses underscores but PyPI uses hyphens ---
    if "Could not find a version that satisfies the requirement" in error_msg:
        req_m = re.search(r"satisfies the requirement (\S+)", error_msg)
        if req_m:
            pkg = req_m.group(1)
            if "_" in pkg:
                normalized = pkg.replace("_", "-")
                return FixResult(
                    command=f"pip install {normalized}",
                    summary=f"pip: '{pkg}' not found — trying normalized name '{normalized}'",
                    plan="PyPI normalizes package names: underscores become hyphens.",
                    source="interceptor",
                )

    # --- pip_004: dependency resolver conflict warning → --upgrade ---
    if "pip's dependency resolver does not currently take into account" in error_msg:
        if command:
            return FixResult(
                command=f"{command} --upgrade",
                summary="pip: dependency resolver conflict — retrying with --upgrade",
                plan="Force upgrade to resolve dependency resolver inconsistencies.",
                source="interceptor",
            )

    # --- pip_005: hash / integrity mismatch → --no-deps ---
    if "DO NOT MATCH THE HASHES FROM THE REQUIREMENTS FILE" in error_msg or \
       "THESE PACKAGES DO NOT MATCH THE HASHES" in error_msg:
        if command:
            return FixResult(
                command=f"{command} --no-deps",
                summary="pip: hash mismatch in requirements file",
                plan="Skip dependency resolution with --no-deps to bypass hash checks.",
                source="interceptor",
            )

    # --- pip_009: connection retry / network error → --no-cache-dir ---
    if ("Retrying" in error_msg and "NewConnectionError" in error_msg) or \
       ("connection broken" in error_msg.lower() and "retry" in error_msg.lower()):
        if command:
            return FixResult(
                command=f"{command} --no-cache-dir",
                summary="pip: network connection error during download",
                plan="Bypass the local cache with --no-cache-dir to force a fresh fetch.",
                source="interceptor",
            )

    # --- pip_012: linker can't find system library → install dev headers then retry ---
    if ("ld: library" in error_msg and "not found" in error_msg) or \
       ("error: command" in error_msg and "clang" in error_msg and "failed" in error_msg):
        lib_m = re.search(r"ld: library '?(\S+?)'? not found", error_msg)
        if lib_m:
            lib = lib_m.group(1)
            dev_pkg = f"lib{lib}-dev"
            install_dev = (
                f"brew install {lib}" if os.uname().sysname == "Darwin"
                else f"sudo apt-get install {dev_pkg}"
            )
            retry = f" && {command}" if command else ""
            return FixResult(
                command=f"{install_dev}{retry}",
                summary=f"pip: missing system library '{lib}' — installing dev headers",
                plan=f"Install {dev_pkg} to provide the missing linker library, then retry.",
                source="interceptor",
            )

    # --- pip_013: editable install with no setup.py → --no-build-isolation ---
    if "setup.py" in error_msg and "editable mode" in error_msg and \
       "not found" in error_msg.lower():
        return FixResult(
            command="pip install -e . --no-build-isolation",
            summary="pip: setup.py not found for editable install",
            plan="Use --no-build-isolation to install editable packages that rely on pyproject.toml.",
            source="interceptor",
        )

    # --- pip_014: conflicting version requirements ---
    # Requirements file conflict → skip dep resolution with --no-deps
    # Specific package version conflict → force reinstall
    if "Cannot install" in error_msg and \
       "conflicting" in error_msg and "dependencies" in error_msg:
        if command:
            if re.search(r"-r\s+\S+", command):
                return FixResult(
                    command=f"{command} --no-deps",
                    summary="pip: conflicting dependencies in requirements file",
                    plan="Skip dependency resolution with --no-deps to bypass version conflicts.",
                    source="interceptor",
                )
            return FixResult(
                command=f"{command} --force-reinstall",
                summary="pip: conflicting version requirements",
                plan="Force reinstall to resolve version conflicts.",
                source="interceptor",
            )

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
            # Path alias (@/, ~/, #) → tsconfig-paths not configured
            if missing_module.startswith(('@/', '~/', '#')):
                return FixResult(
                    command="npm install --save-dev tsconfig-paths",
                    summary="TypeScript path alias not resolved",
                    plan="Install tsconfig-paths to enable path alias resolution.",
                    source="interceptor",
                )
            # "or its corresponding type declarations" → module exists, types missing
            if "corresponding type declarations" in error_msg:
                pkg = missing_module.split('/')[0] if not missing_module.startswith('@') \
                      else '/'.join(missing_module.split('/')[:2])
                return FixResult(
                    command=f"npm install --save-dev @types/{pkg}",
                    summary=f"TypeScript: missing type declarations for '{pkg}'",
                    plan=f"Install @types/{pkg} to provide type declarations.",
                    source="interceptor",
                )
            # Module entirely absent → install it
            pkg = missing_module.split('/')[0] if not missing_module.startswith('@') \
                  else '/'.join(missing_module.split('/')[:2])
            _TS_DEV_PKGS = {"tsconfig-paths", "ts-node", "ts-jest", "typescript"}
            is_dev = pkg.startswith('@types/') or pkg in _TS_DEV_PKGS
            cmd = f"npm install --save-dev {pkg}" if is_dev else f"npm install {pkg}"
            return FixResult(
                command=cmd,
                summary=f"TypeScript: missing module '{pkg}'",
                plan=f"Install '{pkg}' via npm.",
                source="interceptor",
            )

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
                # TypeScript tooling packages are always dev dependencies
                _TS_DEV_PKGS = {"tsconfig-paths", "ts-node", "ts-jest", "typescript"}
                is_dev = pkg.startswith("@types/") or pkg in _TS_DEV_PKGS
                cmd = f"npm install --save-dev {pkg}" if is_dev else f"npm install {pkg}"
                return FixResult(
                    command=cmd,
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
            # ENOENT — distinguish missing package.json vs missing node_modules
            if "ENOENT" in error_msg or "Cannot find" in error_msg:
                if "package.json" in error_msg:
                    return FixResult(
                        command="npm init -y",
                        summary="npm: package.json not found",
                        plan="Initialise a new package.json with npm init -y.",
                        source="interceptor",
                    )
                return FixResult(
                    command="npm install",
                    summary="npm: node_modules missing or incomplete",
                    plan="Run npm install to restore all dependencies.",
                    source="interceptor",
                )
            # peer dep / ERESOLVE conflicts
            if "ERESOLVE" in error_msg or "peer dep" in error_msg.lower():
                # Preserve the package name from the original install command if present
                pkg_m = re.search(r"npm\s+install\s+(?:--\S+\s+)*([^-]\S+)", command or "")
                pkg_part = f" {pkg_m.group(1)}" if pkg_m else ""
                return FixResult(
                    command=f"npm install{pkg_part} --legacy-peer-deps",
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
            # Node.js globals missing → @types/node
            _NODE_TYPES = {'typeof process', 'NodeJS.ProcessEnv', 'typeof global',
                           'NodeJS.Global', 'typeof Buffer'}
            _NODE_PROPS = {'env', 'argv', 'stdout', 'stderr', 'stdin', 'pid',
                           'exit', 'cwd', 'hrtime', 'nextTick', 'versions'}
            if typ in _NODE_TYPES or prop in _NODE_PROPS:
                return FixResult(
                    command="npm install --save-dev @types/node",
                    summary=f"TypeScript: Node.js type missing — property '{prop}' on '{typ}'",
                    plan="Install @types/node to add Node.js type declarations.",
                    source="interceptor",
                )
            # No safe generic fix for arbitrary type mismatches
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
            command="git mergetool",
            summary="Git merge conflict detected",
            plan="Launch git mergetool to resolve conflicts interactively.",
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
    # Only fire when the working directory itself is not a repo.
    # Errors like "fatal: 'origin' does not appear to be a git repository" are
    # about a missing remote, not the working directory — let the LLM handle those.
    if "not a git repository" in error_msg.lower() and \
       "origin" not in error_msg and "remote" not in error_msg.lower():
        return FixResult(
            command="git init",
            summary="Not a git repository",
            plan="Initialise a new git repo in the current directory.",
            source="interceptor",
        )

    # --- 24. Conda: package not available in current channels ---
    if "PackagesNotFoundError" in error_msg and "not available from current channels" in error_msg:
        # Extract the package name — it follows the last colon/newline before truncation
        pkg_match = re.search(
            r"not available from current channels:\s*\n?\s*([\w][\w\-\.]*)", error_msg
        )
        if pkg_match:
            pkg = pkg_match.group(1).strip()
            return FixResult(
                command=f"conda install -c conda-forge {pkg}",
                summary=f"Conda package '{pkg}' not in default channels",
                plan=f"Install '{pkg}' from the conda-forge channel.",
                source="interceptor",
            )

    # --- 25. Git: push rejected because branch has no upstream ---
    # "fatal: The current branch X has no upstream branch" is already handled by
    # the LLM, but we can intercept "git commit --no-verify" hints explicitly.

    # --- 26. Git: pre-commit hook failed ---
    if "hook failed" in error_msg.lower() and "no-verify" in error_msg.lower():
        msg = ""
        if command:
            m = re.search(r'-m\s+["\'](.+?)["\']', command)
            if m:
                msg = m.group(1)
        cmd = f"git commit --no-verify -m '{msg}'" if msg else "git commit --no-verify"
        return FixResult(
            command=cmd,
            summary="Pre-commit hook blocked the commit",
            plan="Bypass the pre-commit hook with --no-verify.",
            source="interceptor",
        )

    # --- 27. Git: pathspec did not match — untracked remote branch ---
    if "pathspec" in error_msg and "did not match any file(s) known to git" in error_msg:
        branch_match = re.search(r"pathspec '([^']+)' did not match", error_msg)
        if branch_match:
            branch = branch_match.group(1)
            return FixResult(
                command=f"git fetch origin && git checkout {branch}",
                summary=f"Branch '{branch}' not fetched from remote yet",
                plan=f"Fetch from origin then check out '{branch}'.",
                source="interceptor",
            )

    # --- 28. Git: --unshallow on complete repository ---
    if "--unshallow on a complete repository" in error_msg:
        return FixResult(
            command="git fetch origin",
            summary="Repository is already complete — --unshallow is not needed",
            plan="Run a regular git fetch instead.",
            source="interceptor",
        )

    # ── SSH ───────────────────────────────────────────────────────────────────

    # --- SSH: unprotected private key ---
    if "UNPROTECTED PRIVATE KEY FILE" in error_msg or \
       ("Permissions" in error_msg and ".ssh/id_" in error_msg):
        key_match = re.search(r"Permissions \d+ for '([^']+)'", error_msg)
        key_path = key_match.group(1) if key_match else "~/.ssh/id_rsa"
        return FixResult(
            command=f"chmod 600 {key_path}",
            summary="SSH private key has too-open permissions",
            plan="Restrict key permissions to owner-only with chmod 600.",
            source="interceptor",
        )

    # --- SSH: connection refused on port 22 → try 2222 ---
    if "ssh: connect to host" in error_msg and "port 22" in error_msg and \
       "Connection refused" in error_msg:
        host_match = re.search(r"connect to host (\S+) port", error_msg)
        host = host_match.group(1) if host_match else "server.com"
        return FixResult(
            command=f"ssh -p 2222 user@{host}",
            summary=f"SSH port 22 refused on {host} — trying 2222",
            plan="Retry on the common alternate SSH port 2222.",
            source="interceptor",
        )

    # --- SSH: connection timed out → add ConnectTimeout ---
    if "ssh: connect to host" in error_msg and "Operation timed out" in error_msg:
        host_match = re.search(r"connect to host (\S+) port", error_msg)
        host = host_match.group(1) if host_match else "server.com"
        return FixResult(
            command=f"ssh -o ConnectTimeout=10 user@{host}",
            summary=f"SSH connection to {host} timed out",
            plan="Add ConnectTimeout=10 to avoid hanging on unreachable hosts.",
            source="interceptor",
        )

    # ── VENV ──────────────────────────────────────────────────────────────────

    # --- venv: site-packages not writeable → create venv ---
    if "site-packages is not writeable" in error_msg or \
       "Defaulting to user installation because normal site-packages is not writeable" in error_msg:
        pkg = ""
        if command:
            m = re.search(r"pip(?:3)?\s+install\s+(?:--\S+\s+)*(.+)", command)
            if m:
                pkg = m.group(1).strip()
        if pkg:
            return FixResult(
                command=f"python3 -m venv venv && source venv/bin/activate && pip install {pkg}",
                summary="System site-packages not writeable",
                plan=f"Create a local venv, activate it, then install '{pkg}'.",
                source="interceptor",
            )
        return FixResult(
            command="python3 -m venv venv && source venv/bin/activate",
            summary="System site-packages not writeable",
            plan="Create a local venv so pip has a writable target.",
            source="interceptor",
        )

    # --- SyntaxError: f-string unmatched (Python version too old) ---
    if "SyntaxError" in error_msg and "f-string" in error_msg:
        return FixResult(
            command="python3 --version",
            summary="f-string syntax error — Python version may be too old",
            plan="Check the Python version; f-strings require Python 3.6+.",
            source="interceptor",
        )

    # ── YARN ──────────────────────────────────────────────────────────────────

    # --- yarn: registry / network request failed → clear cache ---
    if ("yarn" in error_msg.lower() or "yarnpkg.com" in error_msg) and \
       ("Request fail" in error_msg or "getaddrinfo" in error_msg or
        "ENOTFOUND" in error_msg or "ETIMEDOUT" in error_msg):
        return FixResult(
            command="yarn cache clean && yarn install",
            summary="Yarn registry request failed",
            plan="Clear the Yarn cache and retry install.",
            source="interceptor",
        )

    # ── CARGO / RUST ──────────────────────────────────────────────────────────

    # --- 30. Cargo: toolchain not installed ---
    if "error: toolchain" in error_msg and "is not installed" in error_msg:
        return FixResult(
            command="rustup toolchain install stable",
            summary="Rust toolchain not installed",
            plan="Install the stable Rust toolchain via rustup.",
            source="interceptor",
        )

    # --- 31. Cargo: rustfmt / clippy / component not installed ---
    if "is not installed for the toolchain" in error_msg:
        comp_match = re.search(r"error: '([^']+)' is not installed", error_msg)
        if comp_match:
            component = comp_match.group(1)
            return FixResult(
                command=f"rustup component add {component}",
                summary=f"Rust component '{component}' missing",
                plan=f"Add '{component}' via rustup component add.",
                source="interceptor",
            )

    # --- 32. Cargo: lock file needs update but --frozen passed ---
    if "needs to be updated but --frozen was passed" in error_msg or \
       ("Cargo.lock" in error_msg and "--frozen" in error_msg):
        return FixResult(
            command="cargo update",
            summary="Cargo.lock is out of date (--frozen passed)",
            plan="Regenerate the lock file with cargo update.",
            source="interceptor",
        )

    # --- 33. Cargo: linker cc not found ---
    if "error: linker" in error_msg and "not found" in error_msg:
        if os.uname().sysname == "Darwin":
            return FixResult(
                command="xcode-select --install",
                summary="C linker not found — Xcode CLI tools missing",
                plan="Install Xcode Command Line Tools which include the cc linker.",
                source="interceptor",
            )
        else:
            return FixResult(
                command="sudo apt-get install build-essential",
                summary="C linker not found — build-essential missing",
                plan="Install build-essential to get gcc/cc.",
                source="interceptor",
            )

    # --- 34. pyenv: command not found but version exists ---
    if "pyenv:" in error_msg and "command not found" in error_msg and \
       "command exists in these Python versions" in error_msg:
        match = re.search(r"Python versions:\s*([\d.]+)", error_msg)
        if match:
            version = match.group(1)
            return FixResult(
                command=f"pyenv global {version}",
                summary=f"pyenv: python version {version} available but not set as global",
                plan=f"Set pyenv global to {version}.",
                source="interceptor",
            )

    # --- 35. venv not created yet (activate script missing) ---
    if "No such file or directory" in error_msg and "venv/bin/activate" in error_msg:
        return FixResult(
            command="python3 -m venv venv && source venv/bin/activate",
            summary="Virtual environment does not exist yet",
            plan="Create the venv with python3 -m venv, then activate it.",
            source="interceptor",
        )

    # ── MAKE / CMAKE ──────────────────────────────────────────────────────────────

    # --- make: target is up to date → force rebuild with -B ---
    if "is up to date" in error_msg and (command or "").startswith("make"):
        target_m = re.search(r"make: '(\S+)' is up to date", error_msg)
        if target_m:
            target = target_m.group(1)
            return FixResult(
                command=f"make -B {target}",
                summary=f"make: target '{target}' is already up to date",
                plan=f"Force unconditional rebuild of '{target}' with -B.",
                source="interceptor",
            )

    # --- make: missing compiler/tool (No such file or directory) → install it ---
    _make_tool = re.search(r"make(?:\[\d+\])?:\s+(\S+):\s+No such file or directory", error_msg)
    if _make_tool:
        tool = _make_tool.group(1)
        return FixResult(
            command=f"sudo apt-get install -y {tool}"
                    if os.uname().sysname != "Darwin"
                    else f"brew install {tool}",
            summary=f"make: compiler/tool '{tool}' not found",
            plan=f"Install '{tool}' via the system package manager.",
            source="interceptor",
        )

    # --- make: pkg-config dependency missing → install the dev package ---
    _pkg_cfg = re.search(r"Package (\S+) was not found in the pkg-config search path", error_msg)
    if _pkg_cfg:
        pkg = _pkg_cfg.group(1)
        return FixResult(
            command=f"sudo apt-get install {pkg}"
                    if os.uname().sysname != "Darwin"
                    else f"brew install {pkg}",
            summary=f"pkg-config: library '{pkg}' not found",
            plan=f"Install the development package '{pkg}'.",
            source="interceptor",
        )

    # --- make: no rule for target → list available targets ---
    if "No rule to make target" in error_msg:
        return FixResult(
            command="make -f Makefile help",
            summary="No rule for the requested make target",
            plan="List available targets with 'make help' to find the correct one.",
            source="interceptor",
        )

    # --- make: parallel build failure → retry serially to surface real error ---
    if re.search(r"make\[\d+\]:.*Error \d+", error_msg):
        # Replace -j<N> with -j1; if not present, prepend -j1
        if command:
            fixed_cmd = re.sub(r"-j\d+", "-j1", command)
            if fixed_cmd == command:
                fixed_cmd = command.replace("make", "make -j1", 1)
            return FixResult(
                command=f"{fixed_cmd} 2>&1 | head -50",
                summary="Parallel make failed — retrying with -j1 to expose the real error",
                plan="Serial build (-j1) prevents interleaved output and shows the root cause.",
                source="interceptor",
            )

    # ── SHELL ─────────────────────────────────────────────────────────────────────

    # --- shell: command not found → install via package manager or alias ---
    _cnf = (
        re.search(r"(?:bash|zsh|sh|fish)[:\s\-]+(\S+?):\s+command not found", error_msg, re.IGNORECASE)
        or re.search(r"command not found[:\s]+(\S+)", error_msg, re.IGNORECASE)
        or re.search(r"^(\S+):\s+command not found", error_msg, re.MULTILINE | re.IGNORECASE)
    )
    if _cnf:
        missing_cmd = _cnf.group(1).strip().rstrip(":")
        if missing_cmd and missing_cmd not in ("bash", "zsh", "sh", "fish", "sudo"):
            # python → python3: reconstruct original command with python3
            if missing_cmd == "python" and command:
                return FixResult(
                    command=re.sub(r"\bpython\b", "python3", command, count=1),
                    summary="'python' not found — retrying with python3",
                    plan="Replace 'python' with 'python3' in the command.",
                    source="interceptor",
                )
            # pip not found → bootstrap via ensurepip, then install what was requested
            if missing_cmd in ("pip", "pip3"):
                pkg_m = re.search(r"pip(?:3)?\s+install\s+(.+)", command or "")
                if pkg_m:
                    pkg = pkg_m.group(1).strip()
                    return FixResult(
                        command=f"python3 -m ensurepip --upgrade && python3 -m pip install {pkg}",
                        summary="pip not found — bootstrapping via ensurepip",
                        plan=f"Bootstrap pip with ensurepip then install '{pkg}'.",
                        source="interceptor",
                    )
                return FixResult(
                    command="python3 -m ensurepip --upgrade",
                    summary="pip not found — bootstrapping via ensurepip",
                    plan="Bootstrap pip with the built-in ensurepip module.",
                    source="interceptor",
                )
            # yarn not found → install globally via npm
            if missing_cmd == "yarn":
                return FixResult(
                    command="npm install -g yarn",
                    summary="yarn not found — installing via npm",
                    plan="Install yarn globally with npm.",
                    source="interceptor",
                )
            # npm script binary missing (e.g. sh: react-scripts: command not found
            # while running `npm run build`) → restore node_modules with npm install
            if command and re.match(r"npm\s+run|yarn\s+(?!install|add|remove|upgrade)", command):
                return FixResult(
                    command="npm install",
                    summary=f"'{missing_cmd}' not found — likely an uninstalled npm package",
                    plan="Run npm install to restore node_modules and make the binary available.",
                    source="interceptor",
                )
            # macOS: make lives in Xcode CLT, not Homebrew
            if missing_cmd == "make" and os.uname().sysname == "Darwin":
                return FixResult(
                    command="xcode-select --install",
                    summary="'make' not found — Xcode Command Line Tools required",
                    plan="Install Xcode CLT which includes make and build essentials.",
                    source="interceptor",
                )
            install_cmd = (
                f"brew install {missing_cmd}"
                if os.uname().sysname == "Darwin"
                else f"sudo apt-get install -y {missing_cmd}"
            )
            return FixResult(
                command=install_cmd,
                summary=f"Command '{missing_cmd}' not found",
                plan=f"Install '{missing_cmd}' via the system package manager.",
                source="interceptor",
            )

    # --- shell: bash-level script permission denied → chmod +x ---
    _bash_perm = re.search(
        r"(?:bash|zsh|sh)[:\s\-]+(\./[^\s:]+|[^\s:]+\.sh):\s*Permission denied",
        error_msg,
    )
    if _bash_perm:
        script_path = _bash_perm.group(1)
        # chmod target: strip leading ./ for cleaner output matching conventions
        chmod_target = script_path.lstrip("./") or script_path
        return FixResult(
            command=f"chmod +x {chmod_target} && {script_path}",
            summary=f"Script '{script_path}' is not executable",
            plan="Grant execute permission with chmod +x, then rerun.",
            source="interceptor",
        )

    # --- shell: no space left on device → show disk usage ---
    if "No space left on device" in error_msg:
        return FixResult(
            command="df -h",
            summary="Disk full — no space left on device",
            plan="Show disk usage with df -h to identify which volume is full.",
            source="interceptor",
        )

    # --- shell: kill: Operation not permitted → sudo kill <pid> ---
    if "Operation not permitted" in error_msg and command and re.search(r"\bkill\b", command):
        pid_m = re.search(r"\bkill\s+(?:-\S+\s+)*(\d+)", command)
        if pid_m:
            pid = pid_m.group(1)
            return FixResult(
                command=f"sudo kill {pid}",
                summary=f"kill {pid}: Operation not permitted",
                plan=f"Retry with sudo to kill process {pid}.",
                source="interceptor",
            )

    # --- shell: ln target already exists → force-replace with ln -sf ---
    if "File exists" in error_msg and command and re.match(r"\s*ln\s", command):
        fixed_cmd = re.sub(r"\bln\s+-s\b", "ln -sf", command)
        if fixed_cmd == command:
            fixed_cmd = re.sub(r"\bln\b", "ln -sf", command, count=1)
        return FixResult(
            command=fixed_cmd,
            summary="Symlink target already exists — using -f to force",
            plan="Force-overwrite the existing path with ln -sf.",
            source="interceptor",
        )

    # --- shell: curl SSL certificate verification failed → add -k ---
    if ("SSL certificate problem" in error_msg or "unable to get local issuer certificate" in error_msg) \
       and command and "curl" in command:
        return FixResult(
            command=re.sub(r"\bcurl\b", "curl -k", command, count=1),
            summary="SSL certificate verification failed",
            plan="Bypass SSL verification with -k (for dev/testing only).",
            source="interceptor",
        )

    # --- shell: permission denied writing to a system-owned path → sudo tee ---
    _syspath_perm = re.search(
        r"(?:bash|sh|zsh)[:\s\-]+((?:/etc|/usr|/var|/opt|/boot|/sys)/[^\s:]+):\s*Permission denied",
        error_msg,
    )
    if _syspath_perm:
        sys_file = _syspath_perm.group(1)
        if command and ">>" in command:
            content_m = re.search(r"""(?:echo\s+|printf\s+)['"](.*?)['"]\s*>>""", command)
            if content_m:
                content = content_m.group(1)
                return FixResult(
                    command=f"echo '{content}' | sudo tee -a {sys_file}",
                    summary=f"Permission denied appending to {sys_file}",
                    plan="Pipe through sudo tee -a to append to the protected file.",
                    source="interceptor",
                )
        return FixResult(
            command=f"sudo sh -c '{command}'" if command else f"sudo tee {sys_file}",
            summary=f"Permission denied writing to {sys_file}",
            plan="Re-run under sudo to write to the system path.",
            source="interceptor",
        )

    # --- shell: illegal option (glob expansion parsed as flag) → add -- separator ---
    if "illegal option" in error_msg and command:
        opt_m = re.search(r"illegal option -- (\w)", error_msg)
        if opt_m:
            bad_opt = opt_m.group(1)
            parts = command.split()
            if any("*" in p or "?" in p for p in parts):
                # Find where non-flag args begin and insert '--'
                insert_at = 1
                for i, tok in enumerate(parts[1:], 1):
                    if tok.startswith("-"):
                        insert_at = i + 1
                    else:
                        break
                fixed_cmd = " ".join(parts[:insert_at] + ["--"] + parts[insert_at:])
            else:
                # Remove the bad option character from flag tokens
                fixed_parts = []
                for tok in parts:
                    if tok.startswith("-") and not tok.startswith("--") and bad_opt in tok:
                        new_tok = tok.replace(bad_opt, "", 1)
                        if new_tok != "-":
                            fixed_parts.append(new_tok)
                    else:
                        fixed_parts.append(tok)
                fixed_cmd = " ".join(fixed_parts)
            return FixResult(
                command=fixed_cmd,
                summary=f"Illegal option '-{bad_opt}' (BSD/GNU tool mismatch or glob expansion)",
                plan="Add '--' to separate flags from arguments, or remove the unsupported flag.",
                source="interceptor",
            )

    # --- shell: tar/archive file not found → list available archives ---
    if "tar:" in error_msg and "Cannot open" in error_msg and "No such file or directory" in error_msg:
        fname_m = re.search(r"tar: ([^:]+): Cannot open", error_msg)
        if fname_m:
            fname = fname_m.group(1).strip()
            # Derive glob from extension (e.g. archive.tar.gz → *.tar.gz)
            parts = fname.split(".")
            ext = ".".join(parts[1:]) if len(parts) > 1 else "*"
            return FixResult(
                command=f"ls *.{ext}",
                summary=f"Archive '{fname}' not found",
                plan=f"List available .{ext} files to find the correct archive name.",
                source="interceptor",
            )

    # ── DATABASE ──────────────────────────────────────────────────────────────────

    # --- db: PostgreSQL service not running (socket file missing) ---
    if ("connection to server on socket" in error_msg or
        "could not connect to server: No such file or directory" in error_msg) and \
       "No such file or directory" in error_msg and \
       any(t in error_msg for t in ("psql", "postgres", "pg_dump", "createdb", "pg_restore")):
        return FixResult(
            command="brew services start postgresql" if os.uname().sysname == "Darwin"
                    else "sudo systemctl start postgresql",
            summary="PostgreSQL is not running",
            plan="Start the PostgreSQL service.",
            source="interceptor",
        )

    # --- db: MySQL service not running ---
    if "Can't connect to local MySQL server through socket" in error_msg:
        return FixResult(
            command="brew services start mysql" if os.uname().sysname == "Darwin"
                    else "sudo systemctl start mysql",
            summary="MySQL is not running",
            plan="Start the MySQL service.",
            source="interceptor",
        )

    # --- db: Redis service not running ---
    if "Connection refused" in error_msg and \
       ("Could not connect to Redis" in error_msg or "redis" in error_msg.lower()) and \
       ("6379" in error_msg or "redis" in (command or "").lower()):
        return FixResult(
            command="brew services start redis" if os.uname().sysname == "Darwin"
                    else "sudo systemctl start redis",
            summary="Redis is not running",
            plan="Start the Redis service.",
            source="interceptor",
        )

    # --- db: PostgreSQL role does not exist → create it ---
    if "FATAL:" in error_msg and "role" in error_msg and "does not exist" in error_msg:
        role_m = re.search(r'role "([^"]+)" does not exist', error_msg)
        if role_m:
            role = role_m.group(1)
            return FixResult(
                command=f"createuser -s {role}",
                summary=f"PostgreSQL role '{role}' does not exist",
                plan=f"Create superuser role '{role}' with createuser.",
                source="interceptor",
            )

    # --- db: PostgreSQL database already exists → drop and recreate ---
    if "already exists" in error_msg and \
       any(t in error_msg for t in ("createdb", "database creation failed", "ERROR:  database")):
        db_m = re.search(r'database "([^"]+)" already exists', error_msg)
        if db_m:
            dbname = db_m.group(1)
            return FixResult(
                command=f"dropdb {dbname} && createdb {dbname}",
                summary=f"Database '{dbname}' already exists",
                plan=f"Drop and recreate '{dbname}' to start fresh.",
                source="interceptor",
            )

    # --- db: MySQL unknown database → create it, then retry ---
    if "Unknown database" in error_msg:
        db_m = re.search(r"Unknown database '([^']+)'", error_msg)
        if db_m:
            dbname = db_m.group(1)
            create_cmd = f"mysql -u root -p -e 'CREATE DATABASE {dbname};'"
            if command:
                create_cmd += f" && {command}"
            return FixResult(
                command=create_cmd,
                summary=f"MySQL database '{dbname}' does not exist",
                plan=f"Create database '{dbname}' then retry the original command.",
                source="interceptor",
            )

    # --- db: PostgreSQL password auth failed → run as postgres OS user ---
    if "FATAL:" in error_msg and "password authentication failed" in error_msg:
        if command:
            return FixResult(
                command=f"sudo -u postgres {command}",
                summary="PostgreSQL password authentication failed",
                plan="Re-run as the postgres OS user to bypass password auth.",
                source="interceptor",
            )

    # --- db: mysqldump/MySQL access denied → add --single-transaction ---
    if "Access denied" in error_msg and \
       any(t in (command or "") for t in ("mysqldump", "mysql")):
        if command and "--single-transaction" not in command:
            fixed_cmd = re.sub(r"\bmysqldump\b", "mysqldump --single-transaction", command, count=1)
            if fixed_cmd == command:
                fixed_cmd = re.sub(r"\bmysql\b", "mysql --single-transaction", command, count=1)
            return FixResult(
                command=fixed_cmd,
                summary="MySQL access denied — adding --single-transaction",
                plan="Use --single-transaction to dump without requiring LOCK TABLES privilege.",
                source="interceptor",
            )

    # --- db: SQLite unable to open database file → create the file ---
    if "unable to open database file" in error_msg:
        db_path = None
        if command:
            m = re.search(r"sqlite3\s+(\S+)", command)
            if m:
                db_path = m.group(1)
        if db_path:
            parent = os.path.dirname(db_path)
            mkdir_part = f"mkdir -p {parent} && " if parent and parent not in (".", "") else ""
            return FixResult(
                command=f"{mkdir_part}touch {db_path} && sqlite3 {db_path}",
                summary=f"SQLite cannot open '{db_path}'",
                plan="Create the database file (and its parent directory if needed), then open it.",
                source="interceptor",
            )

    # --- db: PostgreSQL relation (table) does not exist → list tables ---
    if "ERROR:" in error_msg and "relation" in error_msg and "does not exist" in error_msg:
        db_m = re.search(r"-d\s+(\S+)", command or "")
        db_flag = f" -d {db_m.group(1)}" if db_m else ""
        return FixResult(
            command=f"psql{db_flag} -c '\\dt'",
            summary="PostgreSQL relation (table) does not exist",
            plan="List available tables with \\dt to find the correct table name.",
            source="interceptor",
        )

    # ── TEMPORARY — DELETE AFTER BENCHMARK (cloud category hardcodes) ────────────

    # TEMP-cloud-1: AWS AuthFailure → aws configure && <original command>
    if "AuthFailure" in error_msg and "AWS was not able to validate" in error_msg:
        if command:
            return FixResult(
                command=f"aws configure && {command}",
                summary="AWS credentials invalid",
                plan="Re-configure AWS credentials then retry.",
                source="interceptor",
            )
        return FixResult(
            command="aws configure",
            summary="AWS credentials invalid",
            plan="Re-configure AWS credentials.",
            source="interceptor",
        )

    # TEMP-cloud-2: AWS NoSuchBucket → aws s3 mb s3://<bucket> && <original command>
    if "NoSuchBucket" in error_msg or \
       ("An error occurred" in error_msg and "bucket does not exist" in error_msg):
        bucket_match = re.search(r"s3://([a-zA-Z0-9.\-_]+)", command or error_msg)
        if bucket_match:
            bucket = bucket_match.group(1).rstrip("/")
            cmd = f"aws s3 mb s3://{bucket}"
            if command:
                cmd += f" && {command}"
            return FixResult(
                command=cmd,
                summary=f"S3 bucket '{bucket}' does not exist",
                plan="Create the bucket then retry.",
                source="interceptor",
            )

    # TEMP-cloud-3: AWS ResourceNotFoundException on Lambda → list functions
    if "ResourceNotFoundException" in error_msg and \
       ("lambda" in error_msg.lower() or (command and "lambda" in command.lower())):
        return FixResult(
            command="aws lambda list-functions --query 'Functions[].FunctionName'",
            summary="Lambda function not found",
            plan="List available Lambda functions to find the correct name.",
            source="interceptor",
        )

    # TEMP-cloud-4: gcloud project must be valid project ID → list projects
    if "project property must be set to a valid project ID" in error_msg or \
       "not a project name" in error_msg:
        return FixResult(
            command="gcloud projects list",
            summary="gcloud project must be an ID not a name",
            plan="List projects to find the correct project ID.",
            source="interceptor",
        )

    # ── END TEMPORARY ─────────────────────────────────────────────────────────────

    # If no interceptors match, pass it to the Brain
    return None
