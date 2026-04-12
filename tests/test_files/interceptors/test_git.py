"""
Interceptor unit tests — Git errors (#19, #20, #21, #22, #23)
Runs run_auto_intercept() directly with simulated stderr.
Exits 0 if all pass, 1 if any fail.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from core.interceptors import run_auto_intercept

PASS = "\033[92m✅\033[0m"
FAIL = "\033[91m❌\033[0m"

failures = []

def check(label, error_msg, expected_cmd_fragment):
    result = run_auto_intercept(error_msg, dry_run=True)
    if result is None:
        failures.append(f"{label}: interceptor returned None (no match)")
        print(f"{FAIL}  {label}: no match")
        return
    if expected_cmd_fragment not in result.command:
        failures.append(f"{label}: expected '{expected_cmd_fragment}' in '{result.command}'")
        print(f"{FAIL}  {label}: got '{result.command}'")
        return
    if result.source != "interceptor":
        failures.append(f"{label}: expected source='interceptor', got '{result.source}'")
        print(f"{FAIL}  {label}: source='{result.source}'")
        return
    print(f"{PASS}  {label}: {result.command}")


# --- #19: Git merge conflict ---
check(
    "#19 git merge conflict",
    "Auto-merging src/app.py\nCONFLICT (content): Merge conflict in src/app.py\n"
    "Automatic merge failed; fix conflicts and then commit the result.",
    "git merge --abort",
)

# --- #20: Git detached HEAD ---
check(
    "#20 git detached HEAD",
    "HEAD detached at a1b2c3d\nnothing to commit, working tree clean",
    "git checkout",
)

# --- #21: Git push rejected (non-fast-forward) ---
check(
    "#21 git push rejected non-fast-forward",
    "To github.com:user/repo.git\n"
    " ! [rejected]        main -> main (non-fast-forward)\n"
    "error: failed to push some refs to 'github.com:user/repo.git'\n"
    "hint: Updates were rejected because the tip of your current branch is behind\n"
    "hint: its remote counterpart. Integrate the remote changes (e.g.\n"
    "hint: 'git pull ...') before pushing again.",
    "git pull --rebase",
)

# --- #21b: fetch first variant ---
check(
    "#21b git push rejected fetch first",
    "To github.com:user/repo.git\n"
    " ! [rejected]        main -> main (fetch first)\n"
    "error: failed to push some refs",
    "git pull --rebase",
)

# --- #22: Git nothing to commit / up-to-date ---
check(
    "#22 git everything up-to-date",
    "Everything up-to-date",
    "already up-to-date",
)

# --- #23: Git not a repository ---
check(
    "#23 git not a repository",
    "fatal: not a git repository (or any of the parent directories): .git",
    "git init",
)


print()
if failures:
    print(f"\033[91m{len(failures)} test(s) failed:\033[0m")
    for f in failures:
        print(f"  • {f}")
    sys.exit(1)
else:
    print(f"\033[92mAll Git interceptor tests passed.\033[0m")
    sys.exit(0)
