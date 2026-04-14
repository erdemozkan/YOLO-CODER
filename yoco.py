#!/usr/bin/env python3
import itertools
import platform
import random
import sys
import threading
import time
from colorama import Fore, Style, init
from core.agent import YoloAgent
from core.schema import FixResult
from core.config import load_config
from core.interceptors import run_auto_intercept
from core.logger import RunLogger
from core.preflight import run_preflight
from core.project import detect_project
from core.snapshot import rollback_all, rollback_from_disk, rollback_file, list_session_files, clear_snapshots, set_command, modified_files
import core.history as _history
from skills import SKILL_REGISTRY

# --- INIT COLORAMA ---
init(autoreset=True)

_IS_MACOS = platform.system() == "Darwin"

_OR = "\033[38;5;208m"   # orange — matches banner brand colour
_YL = "\033[93m"          # yellow — lightning bolt

_QUIPS = [
    "YOLOing..", "Fixing..", "Debugging..", "Joking..", "Crying..",
    "Humming..", "Nagging..", "Thinking..", "Dreaming..", "Improving..",
    "Developing..", "Shimmering..", "Boiling..", "Joining..", "Accepting..",
    "Rejecting..", "Can't believing..", "Day dreaming..", "Hearing..",
    "Wondering..", "Greeting..", "Morning!", "Verifying..", "Validating..",
    "Forgetting..", "Talking..", "Sleeping..", "Cradling..", "Burping..",
    "Celebrating..",
]

_COLORS = [
    "\033[93m",         # yellow
    "\033[38;5;214m",   # amber
    "\033[97m",         # bright white
    "\033[38;5;208m",   # orange
    "\033[96m",         # cyan
    "\033[90m",         # dim grey
]
_RST = "\033[0m"

# Frames: bolt bounces left↔right across 5 positions, color cycles independently
_POSITIONS = ["⚡    ", " ⚡   ", "  ⚡  ", "   ⚡ ", "    ⚡", "   ⚡ ", "  ⚡  ", " ⚡   "]


def _quip():
    """Animate ⚡ bouncing + color-cycling next to a quip for 0.5–1.5 s."""
    quip = random.choice(_QUIPS)
    duration = random.uniform(0.5, 1.5)
    deadline = time.time() + duration

    if sys.stdout.isatty():
        # Direct terminal — overwrite same line with \r
        print()
        for i, pos in enumerate(itertools.cycle(_POSITIONS)):
            if time.time() >= deadline:
                break
            color = _COLORS[i % len(_COLORS)]
            print(f"\r  {color}{pos}{_RST}  {Style.DIM}{quip}{Style.RESET_ALL}", end="", flush=True)
            time.sleep(0.10)
        print()
    else:
        # Piped (test runner) — emit a marker so the runner can animate it in-place
        print(f"\x00QUIP:{quip}:{duration:.2f}", flush=True)


class YoloSpinner:
    """Animates <⚡> with a bouncing bolt while a blocking operation runs."""

    _FRAMES = [
        f"<{_YL}⚡{_OR}   >",
        f"< {_YL}⚡{_OR}  >",
        f"<  {_YL}⚡{_OR} >",
        f"<   {_YL}⚡{_OR}>",
        f"<  {_YL}⚡{_OR} >",
        f"< {_YL}⚡{_OR}  >",
    ]
    _RST = "\033[0m"

    def __init__(self, label: str = ""):
        self.label = label
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _spin(self):
        if not sys.stdout.isatty():
            return  # piped output (e.g. test runner) — skip animation
        for frame in itertools.cycle(self._FRAMES):
            if self._stop.is_set():
                break
            print(f"\r  {_OR}{frame}{self._RST}  {self.label}", end="", flush=True)
            time.sleep(0.10)
        # Erase the spinner line when done
        print(f"\r{' ' * (len(self.label) + 14)}\r", end="", flush=True)

    def __enter__(self):
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        if self._thread:
            self._thread.join()


def _patch_cmd_for_os(cmd: str) -> str:
    """Fix commands that differ between Linux and macOS before executing them."""
    if _IS_MACOS:
        # sed -i on macOS requires an empty-string backup suffix: sed -i '' ...
        # The model almost always emits the Linux form; patch it transparently.
        import re
        cmd = re.sub(r"\bsed -i(?! ''| \"\")", "sed -i ''", cmd)
    return cmd


def print_banner():
    OR  = "\033[38;5;208m"   # orange — brand colour
    RST = "\033[0m"

    lines = [
        "",
        "                                    %%%",
        "                                   %%%%",
        "                                 %%%%",
        "                               %%%%%%",
        "               %%            %%%%%%%   %%             %%%%   %%% %%%%%%   %%%      %%%%%%",
        "            %%%%%          %%%%%%%     %%%%            %%%  %%%%%%%%%%%%% %%%     %%%%%%%%%",
        "          %%%%           %%%%%%%%%        %%%%         %%%%%%%% %%%  %%%% %%%     %%%   %%%",
        "       %%%%            %%%%%%%%%%           %%%%        %%%%%%  %%%  %%%% %%%     %%%   %%%",
        "     %%%%             %%%%%%%%%%%%%%%%         %%%%      %%%%   %%%  %%%% %%%     %%%   %%%",
        "  %%%%              %%%%%%%%%%%%%%%%%%           %%%%    %%%%   %%%%%%%%% %%%%%%%%%%%%%%%%%",
        "  %%%             %%%%%%%%%%%%%%%%%%%              %%%   %%%%    %%%%%%%  %%%%%%%%%%%%%%%%",
        "   %%%%          %%%%%%%%%%%%%%%%%              %%%%",
        "     %%%%%             %%%%%%%%%%             %%%%       %%%%%  %%%%%  %%%%%% %%%%%% %%%%%",
        "        %%%%          %%%%%%%%%            %%%%         %%     %%   %% %%  %%%%%%%%  %% %%%",
        "           %%%%      %%%%%%%%            %%%%           %%%  % %%   %% %%  %%%%%%    %%%%%",
        "             %%%%    %%%%%%            %%%               %%%%%  %%%%%  %%%%%% %%%%%% %% %%%",
        "                   %%%%%%",
        "                  %%%%%",
        "                  %%%",
        "                 %%%",
    ]

    for i, line in enumerate(lines):
        suffix = ""
        if i == 5:
            suffix = f"   {Fore.WHITE}v0.0.2-AGENTIC{Style.RESET_ALL}"
        print(f"{OR}{line}{RST}{suffix}")
    print(f"   {Fore.BLUE}{Style.BRIGHT}https://github.com/erdemozkan/YOLO-CODER{Style.RESET_ALL}")
    print()


def main():
    print_banner()
    if len(sys.argv) < 2:
        print(f"{Fore.YELLOW}Usage: yoco <command>")
        print(f"{Fore.YELLOW}       yoco --explain <command>  Show plain-English diff after fix")
        print(f"{Fore.YELLOW}       yoco --watch <command>   Auto-fix on every file change")
        print(f"{Fore.YELLOW}       yoco --scan              Scan project for secrets & credentials")
        print(f"{Fore.YELLOW}       yoco --rollback          Undo changes from the last run")
        print(f"{Fore.YELLOW}       yoco --history           Browse past sessions")
        print(f"{Fore.YELLOW}       yoco --reset-tests       Restore all test files to original state")
        print(f"{Fore.YELLOW}       yoco --clear-memory      Wipe the fix memory cache")
        sys.exit(0)

    # ---- HISTORY MODE ----
    raw_args = sys.argv[1:]
    if "--history" in raw_args:
        raw_args = [a for a in raw_args if a != "--history"]
        # --history --clear  →  wipe log
        if "--clear" in raw_args:
            _history.clear()
            print(f"{Fore.YELLOW}  History cleared.")
            sys.exit(0)
        # --history N  →  show last N (default 10)
        n = 10
        if raw_args and raw_args[0].isdigit():
            n = int(raw_args[0])
        entries = _history.load(n)
        print(_history.render_list(entries))
        if not entries:
            sys.exit(0)
        print(f"\n  {Fore.CYAN}Enter a number{Fore.RESET} to see details, or {Fore.RED}q{Fore.RESET} to quit.\n")
        try:
            choice = input(f"{Fore.YELLOW}> {Fore.RESET}").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
        if choice.isdigit() and 1 <= int(choice) <= len(entries):
            print(_history.render_detail(entries[int(choice) - 1]))
        sys.exit(0)
    # -----------------------------------------------

    # ---- RESET-TESTS MODE ----
    if "--reset-tests" in raw_args:
        import shutil
        import pathlib
        root      = pathlib.Path(__file__).parent
        originals = root / "tests" / "originals"
        targets   = root / "tests" / "test_files"
        if not originals.exists():
            print(f"{Fore.RED}  No originals directory found at {originals}")
            sys.exit(1)
        restored = 0
        for src in originals.rglob("*"):
            if src.is_file():
                rel  = src.relative_to(originals)
                dest = targets / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                print(f"  {Fore.GREEN}✓{Style.RESET_ALL}  {rel}")
                restored += 1
        print(f"\n{Fore.GREEN}{restored} file(s) restored.{Style.RESET_ALL}")
        sys.exit(0)
    # ---------------------------

    # ---- CLEAR-MEMORY MODE ----
    if "--clear-memory" in raw_args:
        import os as _os
        mem_file = _os.path.expanduser("~/.yolo/fix_memory.jsonl")
        if not _os.path.exists(mem_file):
            print(f"{Fore.YELLOW}  Fix memory is already empty.")
            sys.exit(0)
        count = sum(1 for _ in open(mem_file))
        print(f"{Fore.YELLOW}  This will delete {count} remembered fix(es).")
        try:
            choice = input(f"{Fore.YELLOW}  Are you sure? [Y/n]: {Style.RESET_ALL}").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
        if choice in ("y", "yes", ""):
            _os.remove(mem_file)
            print(f"{Fore.GREEN}  ✓ Fix memory cleared.")
        else:
            print(f"{Fore.YELLOW}  Aborted.")
        sys.exit(0)
    # ---------------------------

    # ---- SCAN MODE: standalone security audit ----
    if "--scan" in raw_args:
        from core.scanner import run_scan
        sys.exit(run_scan("."))
    # -----------------------------------------------

    # ---- WATCH MODE: hand off to sub-agent immediately ----
    if "--watch" in raw_args:
        raw_args.remove("--watch")
        import subprocess as _sp
        try:
            _sp.run([sys.executable, "-m", "core.watcher"] + raw_args)
        except KeyboardInterrupt:
            pass
        sys.exit(0)
    # -------------------------------------------------------------------

    # ---- PARSE YOLO FLAGS (strip before passing command downstream) ----
    dry_run  = "--dry-run" in raw_args
    explain  = "--explain" in raw_args
    raw_args = [a for a in raw_args if a != "--explain"]

    def _pop_flag(flag: str) -> str | None:
        """Extract --flag value from raw_args, removing both tokens in-place."""
        if flag in raw_args:
            idx = raw_args.index(flag)
            raw_args.pop(idx)           # remove --flag
            if idx < len(raw_args):
                return raw_args.pop(idx)  # remove value
        return None

    provider_arg = _pop_flag("--provider")
    host_arg     = _pop_flag("--host")
    port_arg     = _pop_flag("--port")
    model_arg    = _pop_flag("--model")

    args = [a for a in raw_args if a != "--dry-run"]
    if not args:
        print(f"{Fore.YELLOW}Usage: yoco [--provider ollama|lmstudio|llamacpp]")
        print(f"{Fore.YELLOW}            [--host <ip>] [--port <port>] [--model <name>]")
        print(f"{Fore.YELLOW}            [--dry-run] [--rollback] <command>")
        sys.exit(0)
    # -------------------------------------------------------------------

    # ---- ROLLBACK SUBCOMMAND ----
    if args[0] == "--rollback":
        # yolo --rollback <file>  →  direct selective restore (non-interactive)
        if len(args) > 1:
            target = args[1]
            result, command = rollback_file(target)
            if result == "no_session":
                print(f"{Fore.YELLOW}   Nothing to roll back (no session file found).")
            elif result == "not_found":
                print(f"{Fore.YELLOW}   '{target}' not found in last session.")
                files, _ = list_session_files()
                if files:
                    print(f"{Fore.YELLOW}   Files available for rollback:")
                    for f in files:
                        print(f"     {f}")
            else:
                if command:
                    print(f"{Fore.YELLOW}   Session: {Style.BRIGHT}{command}")
                print(f"   {result}")
                print(f"{Fore.GREEN}✅ Rollback complete.")
            sys.exit(0)

        # yolo --rollback  →  interactive picker
        files, command = list_session_files()
        if not files:
            print(f"{Fore.YELLOW}   Nothing to roll back (no session file found).")
            sys.exit(0)

        shown = files[:10]  # cap at 10
        print(f"\n{Fore.YELLOW}↩  Last session:{Style.RESET_ALL}  {Style.BRIGHT}{command or '(unknown)'}{Style.RESET_ALL}\n")
        for i, f in enumerate(shown, 1):
            print(f"  {Fore.CYAN}{i}{Style.RESET_ALL}  {f}")
        if len(files) > 10:
            print(f"  {Fore.WHITE}... ({len(files) - 10} more not shown){Style.RESET_ALL}")
        print(f"\n  {Fore.CYAN}a{Style.RESET_ALL}  Restore ALL files")
        print(f"  {Fore.RED}q{Style.RESET_ALL}  Quit\n")

        try:
            choice = input(f"{Fore.YELLOW}Pick a number (or a/q): {Style.RESET_ALL}").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)

        if choice == "q" or choice == "":
            sys.exit(0)
        elif choice == "a":
            print(f"{Fore.YELLOW}↩  Restoring all files...")
            restored, _ = rollback_from_disk()
            for entry in restored:
                print(f"   {entry}")
            print(f"{Fore.GREEN}✅ Rollback complete.")
        elif choice.isdigit() and 1 <= int(choice) <= len(shown):
            target = shown[int(choice) - 1]
            result, _ = rollback_file(target)
            print(f"   {result}")
            print(f"{Fore.GREEN}✅ Rollback complete.")
        else:
            print(f"{Fore.RED}   Invalid choice.")
        sys.exit(0)
    # -----------------------------

    original_cmd = " ".join(args)
    set_command(original_cmd)
    _t0 = time.time()

    # ---- MODEL CONFIG + PRE-FLIGHT ----
    cfg = load_config(
        provider=provider_arg,
        host=host_arg,
        port=int(port_arg) if port_arg else None,
        model=model_arg,
    )
    run_preflight(cfg)
    logger = RunLogger(original_cmd, cfg, dry_run)
    # -----------------------------------

    if dry_run:
        print(f"{Fore.YELLOW}⚠  DRY-RUN MODE — no files will be modified")

    def _summary(outcome: str, attempts: int = 0, source: str = "") -> None:
        elapsed = time.time() - _t0
        _W  = "\033[97m"
        _DIM = "\033[2m"
        _R  = "\033[0m"
        _G  = "\033[92m"
        _RD = "\033[91m"
        _Y  = "\033[93m"
        _C  = "\033[96m"

        if outcome == "clean":
            bugs, heals = 0, 0
            confidence = "∞%  (Nothing Was Broken)"
            conf_color = _G
        elif outcome == "fixed":
            bugs, heals = 1, attempts
            if source == "interceptor":
                confidence = "99%  (Rule-Based, Zero Doubt)"
            elif source == "memory":
                confidence = "97%  (Been There, Fixed That)"
            else:
                confidence = f"{max(70, 95 - (attempts - 1) * 8)}%  (No Permission Asked)"
            conf_color = _G
        elif outcome == "dry_run":
            bugs, heals = 0, 0
            confidence = "—    (Dry Run, No Changes Made)"
            conf_color = _Y
        else:  # failed
            bugs, heals = 0, attempts
            confidence = "0%   (We Tried. We Really Did.)"
            conf_color = _RD

        # INNER = visible columns between │ borders.
        # Longest row: 2 (indent) + 20 (label) + 1 (space) + len(longest_value)
        # Longest value: "0%   (We Tried. We Really Did.)" = 31 chars
        # → min needed = 54; add 4 cols right padding → 58
        INNER = 58
        LABEL_W = 20   # fixed label column width

        def _row(label: str, value: str, val_color: str = _W) -> None:
            prefix = f"  {label:<{LABEL_W}} "          # 2 + LABEL_W + 1 = 23 chars
            content_len = len(prefix) + len(value)
            pad = " " * max(0, INNER - content_len)
            print(f"{_C}│{_R}{_DIM}{prefix}{_R}{val_color}{value}{_R}{pad}{_C}│{_R}")

        # Title: 🧠 is 2 visual cols but len()=1 → subtract 1 from right padding
        title     = "🧠  YOLO CODER SUMMARY"
        t_len     = len(title) + 1          # +1 corrects for emoji double-width
        t_left    = (INNER - t_len) // 2
        t_right   = INNER - t_len - t_left
        title_line = " " * t_left + title + " " * t_right

        print(f"\n{_C}┌{'─' * INNER}┐{_R}")
        print(f"{_C}│{_R}{title_line}{_C}│{_R}")
        print(f"{_C}├{'─' * INNER}┤{_R}")
        _row("Bugs Obliterated   :", str(bugs))
        _row("Self-Heals         :", str(heals))
        _row("Time Elapsed       :", f"{elapsed:.1f}s")
        _row("Confidence         :", confidence, conf_color)
        print(f"{_C}└{'─' * INNER}┘{_R}\n")

    # --- USING THE BYPASSED SKILL ---
    run_cmd = SKILL_REGISTRY["run_in_sandbox"]

    # ==========================================
    # 🛑 SECURITY GATEKEEPER
    # ==========================================
    security_check = SKILL_REGISTRY.get("security_audit")
    dangerous_keywords = ["git push", "deploy", "publish", "commit"]

    if security_check and (
        any(word in original_cmd for word in dangerous_keywords) or "--scan" in sys.argv
    ):
        print(f"{Fore.YELLOW}🛡️  Running security audit...")
        leaks = security_check()

        if leaks:
            print(
                f"\n{Fore.RED}🛑 SECURITY BLOCK: Secrets detected! YOLO stopped execution."
            )
            # If your security_audit returns a list of leaks, print them out
            if isinstance(leaks, list):
                for filepath, key_type in leaks:
                    print(f"   - {key_type} exposed in {filepath}")
            sys.exit(1)
    # ==========================================

    _quip()
    print(f"{Fore.CYAN}🚀 Executing: {Style.BRIGHT}{original_cmd}")
    with YoloSpinner(original_cmd[:60]):
        exit_code, stdout, stderr = run_cmd(original_cmd)

    if exit_code == 0:
        print(stdout)
        print(f"{Fore.GREEN}✨ CODE WORKS")
        _summary("clean")
        sys.exit(0)

    print(stdout)
    print(f"{Fore.RED}❌ Command failed (Exit {exit_code})")
    print(f"{Fore.RED}Error Log:\n{stderr.strip()}")

    _quip()
    print(f"\n{Fore.YELLOW}🤖 YOLO Mode Activating...")

    from core.memory import recall, remember, forget
    ctx = detect_project()
    agent = YoloAgent(ctx, cfg)
    max_attempts = 3
    attempt_history: list[tuple[str, str]] = []  # (fix_cmd, new_stderr) per failed attempt
    original_stderr = stderr  # keep the original error for memory lookups

    for attempt in range(1, max_attempts + 1):
        print(f"\n{Fore.MAGENTA}--- Attempt {attempt}/{max_attempts} ---")

        # 1. Check Auto-Interceptors First
        result = run_auto_intercept(stderr, ctx.declared_deps, dry_run=dry_run)

        if result is not None:
            _quip()
            print(f"{Fore.MAGENTA}✨ AUTO-INTERCEPT TRIGGERED")
        else:
            # 2. Check fix memory before calling the LLM
            memory_hit = recall(original_stderr)
            if memory_hit and attempt == 1:
                _quip()
                print(f"{Fore.CYAN}🧠 Fix Memory hit! (used {memory_hit['hits']}x before)")
                result = FixResult(
                    command=memory_hit["command"],
                    summary="Recalled from fix memory",
                    plan=f"Previously fixed this error {memory_hit['hits']} time(s) with this command.",
                    source="memory",
                )
            else:
                _quip()
                print(f"{Fore.YELLOW}🤖 Consulting the Brain...")
                # 3. Ask the LLM — pass full attempt history so it avoids repeating itself
                with YoloSpinner("Thinking…"):
                    result = agent.ask(
                        original_cmd, exit_code, stderr,
                        history=attempt_history if attempt_history else None,
                    )
            safe, reason = result.is_valid()
            if not safe:
                print(f"{Fore.RED}💀 Fix command blocked: {reason}")
                print(f"{Fore.RED}   Command was: {result.command}")
                logger.flush("failed")
                sys.exit(1)

            result.command = _patch_cmd_for_os(result.command)

        # 3. Diagnostic Box
        print(f"\n{Fore.MAGENTA}--- AI DIAGNOSTICS ---")
        print(f"{Fore.YELLOW}🔍 SUMMARY: {Style.RESET_ALL}{result.summary}")
        print(f"{Fore.CYAN}📝 PLAN: {Style.RESET_ALL}{result.plan}")
        print(f"{Fore.MAGENTA}----------------------\n")

        print(f"{Fore.GREEN}💡 Suggested Fix: {Style.BRIGHT}{result.command}")

        # 4a. DRY-RUN: show diff and stop
        if dry_run:
            from core.diff import render_diff
            diff_output = render_diff(result.command)
            # Patch in source on the "Source:" line
            diff_output = diff_output.replace(
                "  \033[2mSource  :\033[0m  ",
                f"  \033[2mSource  :\033[0m  {result.source}"
            )
            print(diff_output)
            print(f"{Fore.YELLOW}  Plan    :  {Style.RESET_ALL}{result.plan}")
            print(f"\n{Fore.YELLOW}No changes made. Remove --dry-run to apply the fix.")
            logger.flush("dry_run")
            _history.record(original_cmd, "dry_run", stderr, result.command, result.source, attempt, [])
            _summary("dry_run")
            sys.exit(0)

        # 4b. Execute Fix (using the bypassed skill or native replacer)
        print(f"{Fore.CYAN}🔧 Applying fix...")

        if result.command.startswith("python3 yoco_replace.py"):
            try:
                import re
                m = re.search(r"python3 yoco_replace.py\s+(\S+)\s+(\d+)\s+(.*)", result.command)
                if m:
                    filepath, line_num, new_text = m.groups()
                    # Strip surrounding shell quotes the model may have added
                    if (new_text.startswith("'") and new_text.endswith("'")) or \
                       (new_text.startswith('"') and new_text.endswith('"')):
                        new_text = new_text[1:-1]
                    replacer = SKILL_REGISTRY["line_replacer"]
                    replace_result = replacer(filepath, line_num, new_text)
                    print(replace_result)
                    if "✅" in replace_result:
                        fix_code, fix_err = 0, ""
                    else:
                        fix_code, fix_err = 1, replace_result
                else:
                    with YoloSpinner("Applying fix…"):
                        fix_code, _, fix_err = run_cmd(result.command)
            except Exception as e:
                fix_code, fix_err = 1, str(e)
        else:
            with YoloSpinner("Applying fix…"):
                fix_code, _, fix_err = run_cmd(result.command)

        if fix_code != 0:
            print(f"{Fore.RED}⚠️ Fix failed: {fix_err.strip()}")
            fail_msg = f"Fix command itself failed: {fix_err}"
            logger.record_attempt(result, fix_code, None, fail_msg)
            attempt_history.append((result.command, fail_msg))
            stderr += f"\nFix failed: {fix_err}"
            continue

        # 5. Verify by re-running original command
        _quip()
        print(f"{Fore.GREEN}✅ Fix applied. Retrying original command...")
        with YoloSpinner(original_cmd[:60]):
            exit_code, stdout, stderr = run_cmd(original_cmd)

        if exit_code == 0:
            print(stdout)
            logger.record_attempt(result, fix_code, 0, "")
            if explain:
                from core.explain import render_explain
                print(render_explain(result, original_stderr))
            mods = modified_files()
            clear_snapshots()
            logger.flush("success", mods)
            _history.record(original_cmd, "fixed", original_stderr, result.command, result.source, attempt, mods)
            # Write to fix memory so next time we skip the LLM
            if result.source != "interceptor":
                remember(original_stderr, result.command)
            print(f"{Fore.GREEN}✨ CODE WORKS")
            _summary("fixed", attempt, result.source)
            sys.exit(0)
        else:
            print(f"{Fore.RED}❌ Command failed again (Exit {exit_code})")
            print(f"{Fore.RED}New Error Log:\n{stderr.strip()}")
            logger.record_attempt(result, fix_code, exit_code, stderr)
            # If the fix came from memory and it failed, evict it
            if result.source == "memory":
                forget(original_stderr)
                print(f"{Fore.YELLOW}🧠 Memory fix failed — evicted from memory.")
            attempt_history.append((result.command, stderr))

    print(f"{Fore.RED}💀 Failed after {max_attempts} attempts.")

    mods = modified_files()
    restored = rollback_all()
    if restored:
        print(f"\n{Fore.YELLOW}↩ Rolling back changes:")
        for entry in restored:
            print(f"   {entry}")
    logger.flush("rolled_back", mods, rolled_back=True)
    _history.record(original_cmd, "failed", original_stderr, "", "", max_attempts, mods)
    _summary("failed", max_attempts)


if __name__ == "__main__":
    main()
