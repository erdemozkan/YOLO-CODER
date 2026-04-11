import platform
import sys
from colorama import Fore, Style, init
from core.agent import YoloAgent
from core.config import load_config
from core.interceptors import run_auto_intercept
from core.logger import RunLogger
from core.preflight import run_preflight
from core.project import detect_project
from core.snapshot import rollback_all, rollback_from_disk, clear_snapshots, set_command, modified_files
from skills import SKILL_REGISTRY

# --- INIT COLORAMA ---
init(autoreset=True)

_IS_MACOS = platform.system() == "Darwin"


def _patch_cmd_for_os(cmd: str) -> str:
    """Fix commands that differ between Linux and macOS before executing them."""
    if _IS_MACOS:
        # sed -i on macOS requires an empty-string backup suffix: sed -i '' ...
        # The model almost always emits the Linux form; patch it transparently.
        import re
        cmd = re.sub(r"\bsed -i(?! ''| \"\")", "sed -i ''", cmd)
    return cmd


def print_banner():
    S, D = "█", "░"
    N = "\033[38;5;208m"
    print(
        f"{N}{S}{S}   {S}{S}{D}  {S}{S}{S}{S}{S}{S}{D}  {S}{S}{D}       {S}{S}{S}{S}{S}{S}{D}    {Fore.WHITE}v0.0.2-AGENTIC"
    )
    print(
        f"{N} {S}{S} {S}{S}{D}  {S}{S}    {S}{S}{D} {S}{S}{D}      {S}{S}    {S}{S}{D}  "
    )
    print(
        f"{N}  {S}{S}{S}{D}   {S}{S}    {S}{S}{D} {S}{S}{D}      {S}{S}    {S}{S}{D}  {Fore.BLUE}{Style.BRIGHT}https://github.com/erdemozkan/YOLO-APR{Style.RESET_ALL}{N}"
    )
    print(
        f"{N}  {S}{S}{S}{D}   {S}{S}    {S}{S}{D} {S}{S}{D}      {S}{S}    {S}{S}{D}  "
    )
    print(
        f"{N}  {S}{S}{S}{D}    {S}{S}{S}{S}{S}{S}{D}  {S}{S}{S}{S}{S}{S}{S}{D}  {S}{S}{S}{S}{S}{S}{D}   {Style.RESET_ALL}\n"
    )


def main():
    print_banner()
    if len(sys.argv) < 2:
        print(f"{Fore.YELLOW}Usage: yolo <command>")
        print(f"{Fore.YELLOW}       yolo --rollback    Undo changes from the last run")
        sys.exit(0)

    # ---- PARSE YOLO FLAGS (strip before passing command downstream) ----
    raw_args = sys.argv[1:]
    dry_run  = "--dry-run" in raw_args

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
        print(f"{Fore.YELLOW}Usage: yolo [--provider ollama|lmstudio|llamacpp]")
        print(f"{Fore.YELLOW}            [--host <ip>] [--port <port>] [--model <name>]")
        print(f"{Fore.YELLOW}            [--dry-run] [--rollback] <command>")
        sys.exit(0)
    # -------------------------------------------------------------------

    # ---- ROLLBACK SUBCOMMAND ----
    if args[0] == "--rollback":
        print(f"{Fore.YELLOW}↩  Rolling back last YOLO session...")
        restored, command = rollback_from_disk()
        if not restored:
            print(f"{Fore.YELLOW}   Nothing to roll back (no session file found).")
        else:
            if command:
                print(f"{Fore.YELLOW}   Session: {Style.BRIGHT}{command}")
            for entry in restored:
                print(f"   {entry}")
            print(f"{Fore.GREEN}✅ Rollback complete.")
        sys.exit(0)
    # -----------------------------

    original_cmd = " ".join(args)
    set_command(original_cmd)

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

    print(f"{Fore.CYAN}🚀 Executing: {Style.BRIGHT}{original_cmd}")
    exit_code, stdout, stderr = run_cmd(original_cmd)

    if exit_code == 0:
        print(stdout)
        print(f"{Fore.GREEN}✨ CODE WORKS")
        sys.exit(0)

    print(stdout)
    print(f"{Fore.RED}❌ Command failed (Exit {exit_code})")
    print(f"{Fore.RED}Error Log:\n{stderr.strip()}")

    print(f"\n{Fore.YELLOW}🤖 YOLO Mode Activating...")

    ctx = detect_project()
    agent = YoloAgent(ctx, cfg)
    max_attempts = 3
    attempt_history: list[tuple[str, str]] = []  # (fix_cmd, new_stderr) per failed attempt

    for attempt in range(1, max_attempts + 1):
        print(f"\n{Fore.MAGENTA}--- Attempt {attempt}/{max_attempts} ---")

        # 1. Check Auto-Interceptors First
        result = run_auto_intercept(stderr, ctx.declared_deps, dry_run=dry_run)

        if result is not None:
            print(f"{Fore.MAGENTA}✨ AUTO-INTERCEPT TRIGGERED")
        else:
            print(f"{Fore.YELLOW}🤖 Consulting the Brain...")
            # 2. Ask the LLM — pass full attempt history so it avoids repeating itself
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

        # 4a. DRY-RUN: show what would happen and stop here
        if dry_run:
            print(f"\n{Fore.YELLOW}--- DRY-RUN PREVIEW ---")
            print(f"{Fore.YELLOW}  Would apply : {Style.BRIGHT}{result.command}")
            print(f"{Fore.YELLOW}  Plan        : {Style.RESET_ALL}{result.plan}")
            print(f"{Fore.YELLOW}  Source      : {Style.RESET_ALL}{result.source}")
            print(f"{Fore.YELLOW}-----------------------")
            print(f"{Fore.YELLOW}No changes made. Remove --dry-run to apply the fix.")
            logger.flush("dry_run")
            sys.exit(0)

        # 4b. Execute Fix (using the bypassed skill or native replacer)
        print(f"{Fore.CYAN}🔧 Applying fix...")

        if result.command.startswith("python3 yolo_replace.py"):
            try:
                import re
                m = re.search(r"python3 yolo_replace.py\s+(\S+)\s+(\d+)\s+(.*)", result.command)
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
                    fix_code, _, fix_err = run_cmd(result.command)
            except Exception as e:
                fix_code, fix_err = 1, str(e)
        else:
            fix_code, _, fix_err = run_cmd(result.command)

        if fix_code != 0:
            print(f"{Fore.RED}⚠️ Fix failed: {fix_err.strip()}")
            fail_msg = f"Fix command itself failed: {fix_err}"
            logger.record_attempt(result, fix_code, None, fail_msg)
            attempt_history.append((result.command, fail_msg))
            stderr += f"\nFix failed: {fix_err}"
            continue

        # 5. Verify by re-running original command
        print(f"{Fore.GREEN}✅ Fix applied. Retrying original command...")
        exit_code, stdout, stderr = run_cmd(original_cmd)

        if exit_code == 0:
            print(stdout)
            logger.record_attempt(result, fix_code, 0, "")
            clear_snapshots()
            logger.flush("success", modified_files())
            print(f"{Fore.GREEN}✨ CODE WORKS")
            sys.exit(0)
        else:
            print(f"{Fore.RED}❌ Command failed again (Exit {exit_code})")
            print(f"{Fore.RED}New Error Log:\n{stderr.strip()}")
            logger.record_attempt(result, fix_code, exit_code, stderr)
            attempt_history.append((result.command, stderr))

    print(f"{Fore.RED}💀 Failed after {max_attempts} attempts.")

    restored = rollback_all()
    if restored:
        print(f"\n{Fore.YELLOW}↩ Rolling back changes:")
        for entry in restored:
            print(f"   {entry}")
    logger.flush("rolled_back", modified_files(), rolled_back=True)


if __name__ == "__main__":
    main()
