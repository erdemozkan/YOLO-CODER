import re
from pathlib import Path
from openai import OpenAI
from core.config import ModelConfig
from core.project import ProjectContext, flat_file_list
from core.schema import FixResult

# Multi-file context limits — keep prompts from ballooning
_MAX_RELATED_FILES = 5
_MAX_LINES_PER_FILE = 150

# Error pattern → (summary, plan) templates derived from stderr, not the model.
# Ordered from most specific to most general.
_ERROR_TEMPLATES = [
    (r"ModuleNotFoundError: No module named '(.+?)'",
        lambda m: (f"Missing local module '{m.group(1)}'",
                   f"Create '{m.group(1)}.py' locally — model treats missing modules as local files")),
    (r"FileNotFoundError.*: '(.+?)'",
        lambda m: (f"File not found: {m.group(1)}",
                   "Create the missing file or directory")),
    (r"JSONDecodeError",
        lambda m: ("Empty or malformed JSON file",
                   "Initialize the JSON file with valid content")),
    (r"SyntaxError: expected ':'",
        lambda m: ("Syntax error — missing colon",
                   "Append colon and indented block to the failing line")),
    (r"TypeError: can only concatenate str",
        lambda m: ("Type error — concatenating non-string with str",
                   "Wrap the non-string variable with str()")),
    (r"NameError: name '(.+?)' is not defined",
        lambda m: (f"Undefined variable '{m.group(1)}'",
                   f"Initialise '{m.group(1)}' before the line that uses it")),
    (r"PermissionError",
        lambda m: ("Permission denied",
                   "Fix file permissions with chmod or adjust ownership")),
    (r"ConnectionRefusedError|Address already in use",
        lambda m: ("Network/port error",
                   "Kill the conflicting process or free the port")),
    (r"ImportError: (.+)",
        lambda m: (f"Import error: {m.group(1)}",
                   "Install or create the missing dependency")),
    (r"OSError|IOError",
        lambda m: ("OS / IO error",
                   "Check file paths, permissions, and disk space")),
]

_FALLBACK_SUMMARY = "Unexpected error — consulting model for a fix"
_FALLBACK_PLAN    = "Apply the generated bash command"


def _collect_related_files(failing_path: Path, project_root: Path) -> list[tuple[str, str]]:
    """
    Parse import statements in failing_path and return content of local files.
    Returns list of (relative_path, numbered_content) tuples.
    Caps at _MAX_RELATED_FILES files, _MAX_LINES_PER_FILE lines each.
    """
    collected: list[tuple[str, str]] = []
    seen: set[Path] = {failing_path.resolve()}
    queue: list[Path] = [failing_path]

    while queue and len(collected) < _MAX_RELATED_FILES:
        current = queue.pop(0)
        try:
            source = current.read_text(errors="replace")
        except OSError:
            continue

        # Find all local imports: `import foo`, `from foo import bar`, `from .foo import bar`
        raw_imports = re.findall(
            r"^\s*(?:from\s+([\w\.]+)\s+import|import\s+([\w\.]+))",
            source, re.MULTILINE
        )

        for from_part, import_part in raw_imports:
            module = (from_part or import_part).lstrip(".")
            if not module:
                continue
            # Only consider top-level module name (e.g. "core.agent" → "core")
            top = module.split(".")[0]
            candidates = [
                project_root / f"{top}.py",
                project_root / top / "__init__.py",
                current.parent / f"{top}.py",
                current.parent / top / "__init__.py",
            ]
            for candidate in candidates:
                resolved = candidate.resolve()
                if resolved in seen or not candidate.is_file():
                    continue
                seen.add(resolved)
                try:
                    lines = candidate.read_text(errors="replace").splitlines()
                    truncated = lines[:_MAX_LINES_PER_FILE]
                    suffix = f"\n  ... ({len(lines) - _MAX_LINES_PER_FILE} more lines truncated)" if len(lines) > _MAX_LINES_PER_FILE else ""
                    numbered = "\n".join(f"{i+1}: {ln}" for i, ln in enumerate(truncated))
                    try:
                        rel = str(candidate.resolve().relative_to(Path.cwd()))
                    except ValueError:
                        rel = str(candidate.relative_to(project_root)) if candidate.is_relative_to(project_root) else candidate.name
                    collected.append((rel, numbered + suffix))
                    queue.append(candidate)
                except OSError:
                    pass
                if len(collected) >= _MAX_RELATED_FILES:
                    break

    return collected


def _derive_context(error_msg: str) -> tuple[str, str]:
    """Return (summary, plan) derived from stderr patterns — no model call needed."""
    for pattern, builder in _ERROR_TEMPLATES:
        m = re.search(pattern, error_msg)
        if m:
            return builder(m)
    return _FALLBACK_SUMMARY, _FALLBACK_PLAN


def _build_system_prompt(ctx: ProjectContext) -> str:
    """Compose a context-aware system prompt from the detected project environment."""
    files = flat_file_list(ctx.repo_structure)
    repo_json = ", ".join(f'"{f}"' for f in files[:60])  # cap at 60 entries
    if len(files) > 60:
        repo_json += f', ... ({len(files) - 60} more)'

    env_block = (
        f"OS: {ctx.os_name} {ctx.os_version} ({ctx.arch}) | "
        f"Shell: {ctx.shell} | "
        f"Python: {ctx.python_version}"
        + (f" | Node: {ctx.node_version}" if ctx.node_version else "")
    )

    project_block = (
        f"Project type: {ctx.type} | "
        f"Package manager: {ctx.package_manager} | "
        f"Test runner: {ctx.test_runner}"
    )

    deps_block = ""
    if ctx.declared_deps:
        deps_block = f"\nDeclared deps: {', '.join(ctx.declared_deps[:30])}"
        if len(ctx.declared_deps) > 30:
            deps_block += f" ... ({len(ctx.declared_deps) - 30} more)"

    return (
        "You are a CLI repair tool. "
        "Output ONLY a single bare bash command to fix the error. "
        "No explanation. No markdown. No backticks. No multi-line output.\n\n"
        "To fix a Python source file, use the yoco_replace tool:\n"
        "  python3 yoco_replace.py <filepath> <line_number> <new_line_content>\n"
        "Example: python3 yoco_replace.py src/app.py 7 '    return a / b if b != 0 else 0'\n"
        "The line number comes from the traceback. The new content replaces that exact line.\n\n"
        "RULES for the replacement line:\n"
        "- Must be valid Python on a SINGLE line.\n"
        "- Use ternary expressions: `x if cond else y` — NOT `if cond: x else: y`.\n"
        "- Use `or` guards: `(val or '').strip()` — NOT multi-statement if/else.\n"
        "- Preserve the original indentation exactly.\n\n"
        "For missing packages:  pip install <package>\n"
        "For missing dirs:      mkdir -p <path>\n"
        "For permissions:       chmod +x <file>\n\n"
        f"Environment: {env_block}\n"
        f"Project: {project_block}{deps_block}\n"
        f"Repo files: [{repo_json}]"
    )


class YoloAgent:
    def __init__(self, ctx: ProjectContext, cfg: ModelConfig):
        self.client = OpenAI(base_url=cfg.base_url, api_key=cfg.api_key)
        self.model_name = cfg.model
        self.ctx = ctx
        self.system_prompt = _build_system_prompt(ctx)

    def ask(
        self,
        user_cmd: str,
        exit_code: int,
        error_msg: str,
        history: list[tuple[str, str]] | None = None,
    ) -> FixResult:
        """
        Returns a FixResult.
        summary and plan are derived from the error message locally.
        The model is asked only for the bare bash command it was trained to produce.

        history: list of (fix_command, new_stderr) tuples from prior attempts.
                 Injected as a compact text block so the model avoids repeating
                 commands that already failed. Kept in single-message format to
                 match the fine-tuning data — no multi-turn chat.
        """
        summary, plan = _derive_context(error_msg)

        prior_block = ""
        if history:
            lines = ["", "Previous attempts that did NOT fix the problem:"]
            for i, (cmd, err) in enumerate(history, 1):
                err_headline = err.strip().splitlines()[0][:120] if err.strip() else "unknown error"
                lines.append(f"  [{i}] Tried: {cmd}")
                lines.append(f"       Still failing: {err_headline}")
            prior_block = "\n".join(lines)

        # Inject the failing file + related local imports for full context.
        file_block = ""
        file_match = re.search(r'File "(.+?\.py)"', error_msg)
        if file_match:
            fpath = Path(file_match.group(1))
            project_root = Path(self.ctx.cwd).resolve() if self.ctx.cwd else fpath.parent
            try:
                lines = fpath.read_text().splitlines()
                numbered = "\n".join(f"{i+1}: {ln}" for i, ln in enumerate(lines))
                # Use full relative path so LLM uses it verbatim in yoco_replace
                try:
                    fpath_rel = str(fpath.resolve().relative_to(Path.cwd()))
                except ValueError:
                    fpath_rel = str(fpath)
                file_block = f"\nFile content ({fpath_rel}):\n{numbered}\n"

                # Pull in related local files the failing file imports
                related = _collect_related_files(fpath, project_root)
                if related:
                    file_block += "\nRelated files:\n"
                    for rel_path, content in related:
                        file_block += f"\n--- {rel_path} ---\n{content}\n"
            except OSError:
                pass

        user_prompt = (
            f"Command: {user_cmd}\n"
            f"Exit Code: {exit_code}\n"
            f"Error: {error_msg}"
            f"{file_block}"
            f"{prior_block}\n"
            f"FIX:"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                temperature=0.1,
            )

            raw = response.choices[0].message.content.strip()

            # Minimal sanitisation — strip markdown fences only.
            command = (
                raw.replace("```bash", "")
                   .replace("```sh", "")
                   .replace("```", "")
                   .strip()
            )

            return FixResult(command=command, summary=summary, plan=plan, source="llm")

        except Exception:
            return FixResult.fallback()
