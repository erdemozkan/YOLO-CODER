#!/usr/bin/env python3
"""
YOLO Auto-Test Runner
Usage:
  python3 tests/run_tests.py                      # run all tests (live stream)
  python3 tests/run_tests.py --reset              # restore all test files from originals
  python3 tests/run_tests.py --id unit_syntax_colon
  python3 tests/run_tests.py --filter unit|llm|security|integration|rollback
  python3 tests/run_tests.py --quiet              # spinner only, no subprocess output
"""

import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT         = Path(__file__).parent.parent
TESTS_DIR    = ROOT / "tests"
ORIGINALS    = TESTS_DIR / "originals"
TEST_FILES   = TESTS_DIR / "test_files"
CASES_FILE   = TESTS_DIR / "test_cases.json"
HISTORY_FILE = Path.home() / ".yolo" / "history.jsonl"

# ── ANSI ─────────────────────────────────────────────────────────────────────
GREEN   = "\033[92m"
RED     = "\033[91m"
YELLOW  = "\033[93m"
CYAN    = "\033[96m"
MAGENTA = "\033[95m"
BLUE    = "\033[94m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
RESET   = "\033[0m"
CLEAR   = "\033[2K\033[1G"

def _c(color, text): return f"{color}{text}{RESET}"


# ── Fancy phase spinners ──────────────────────────────────────────────────────
PHASES = [
    ("Preparing",   ["▱▱▱▱▱", "▰▱▱▱▱", "▰▰▱▱▱", "▰▰▰▱▱", "▰▰▰▰▱", "▰▰▰▰▰"], CYAN),
    ("Running",     ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],   MAGENTA),
    ("Asserting",   ["◐", "◓", "◑", "◒"],                                     YELLOW),
    ("Cleaning up", ["·  ", " · ", "  ·", " · "],                             BLUE),
]


class PhaseSpinner:
    def __init__(self, test_id: str):
        self._test_id = test_id
        self._phase   = 0
        self._frame   = 0
        self._stop    = threading.Event()
        self._lock    = threading.Lock()
        self._thread  = threading.Thread(target=self._run, daemon=True)

    def _render(self):
        label, frames, color = PHASES[self._phase]
        frame = frames[self._frame % len(frames)]
        sys.stdout.write(
            f"\r  {_c(color, frame)}  "
            f"{DIM}{self._test_id}{RESET}  "
            f"{_c(color, label + '…')}"
            f"        "
        )
        sys.stdout.flush()

    def _run(self):
        while not self._stop.is_set():
            with self._lock:
                self._render()
                self._frame += 1
            time.sleep(0.09)

    def start(self):
        self._thread.start()

    def next_phase(self):
        with self._lock:
            self._phase = min(self._phase + 1, len(PHASES) - 1)
            self._frame = 0

    def stop(self):
        self._stop.set()
        self._thread.join()
        sys.stdout.write(CLEAR)
        sys.stdout.flush()


# ── Typewriter effect ─────────────────────────────────────────────────────────
def _typewrite(text: str, delay: float = 0.018):
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write("\n")
    sys.stdout.flush()


# ── Animated progress bar ─────────────────────────────────────────────────────
def _draw_bar(done: int, total: int, passed: int, failed: int):
    bar_len = 32
    filled  = int(bar_len * done / total) if total else 0
    pct     = int(100 * done / total) if total else 0
    bar     = _c(GREEN, "█" * filled) + _c(DIM, "░" * (bar_len - filled))
    counts  = f"{_c(GREEN, str(passed)+'p')}  {_c(RED, str(failed)+'f')}"
    sys.stdout.write(f"\r  [{bar}] {pct:3d}%  {done}/{total}  {counts}   ")
    sys.stdout.flush()


# ── Reset ─────────────────────────────────────────────────────────────────────
def reset_all():
    print(f"\n{BOLD}Restoring test files from originals…{RESET}\n")
    restored = 0
    for src in ORIGINALS.rglob("*"):
        if src.is_file():
            rel = src.relative_to(ORIGINALS)
            dst = TEST_FILES / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            sys.stdout.write(f"  {_c(GREEN, '✓')}  {rel}")
            sys.stdout.flush()
            time.sleep(0.04)
            sys.stdout.write("\n")
            restored += 1
    print(f"\n{_c(GREEN, f'{restored} file(s) restored.')}\n")


def reset_single(rel_path: str):
    src = ORIGINALS / rel_path
    dst = TEST_FILES / rel_path
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


# ── History helpers ───────────────────────────────────────────────────────────
def _last_history_record():
    if not HISTORY_FILE.exists():
        return None
    for line in reversed(HISTORY_FILE.read_text().strip().splitlines()):
        line = line.strip()
        if line:
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def _history_len():
    if not HISTORY_FILE.exists():
        return 0
    return sum(1 for ln in HISTORY_FILE.read_text().splitlines() if ln.strip())


# ── Setup / cleanup ───────────────────────────────────────────────────────────
def _do_setup(action: str):
    if action.startswith("create_empty_file:"):
        path = ROOT / action.split(":", 1)[1].strip()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")
    elif action.startswith("pip_uninstall:"):
        pkg = action.split(":", 1)[1].strip()
        subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", pkg],
                       capture_output=True)
    else:
        print(f"  {_c(YELLOW, 'WARN')} unknown setup action: {action!r}")


def _do_cleanup(files: list):
    for entry in files:
        path = ROOT / entry
        if entry.endswith("/"):
            if path.exists(): shutil.rmtree(path)
        else:
            if path.exists(): path.unlink()


# ── Live-stream subprocess ────────────────────────────────────────────────────
def _stream_proc(cmd, cwd, timeout=120):
    proc = subprocess.Popen(
        cmd, cwd=cwd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    try:
        for line in proc.stdout:
            print(f"  {DIM}│{RESET}  {line.rstrip()}")
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill(); proc.wait()
    return proc.returncode


# ── Verdict banner ────────────────────────────────────────────────────────────
def _verdict(ok: bool, elapsed: float, failures: list):
    time.sleep(0.12)
    if ok:
        print(f"\n  {_c(GREEN, BOLD + '  ✔  PASS' + RESET)}  {DIM}({elapsed:.1f}s){RESET}")
    else:
        for f in failures:
            print(f"  {_c(RED, '  ✗')} {f}")
        print(f"  {_c(RED, BOLD + '  ✘  FAIL' + RESET)}  {DIM}({elapsed:.1f}s){RESET}")


# ── Run a single test ─────────────────────────────────────────────────────────
def run_test(tc: dict, live: bool = True) -> str:
    tid   = tc["id"]
    desc  = tc.get("description", tid)
    ttype = tc.get("type", "yolo_run")
    short = desc[:54] + "…" if len(desc) > 55 else desc

    # ── Header ───────────────────────────────────────────────────────────────
    print(f"\n  {DIM}{'╌'*58}{RESET}")
    _typewrite(f"  {_c(BOLD+CYAN, tid)}  {DIM}{short}{RESET}", delay=0.018)

    # ── Setup phase ──────────────────────────────────────────────────────────
    spinner = PhaseSpinner(tid)
    spinner.start()
    time.sleep(0.35)

    setup = tc.get("setup", "")
    if setup:
        _do_setup(setup)

    history_before = _history_len()

    raw_cmd = tc["command"]
    if ttype == "yolo_run":
        cmd = [sys.executable, str(ROOT / "yolo.py")] + raw_cmd.split()
    elif ttype == "python_run":
        cmd = [sys.executable] + raw_cmd.split()[1:]
    else:
        spinner.stop()
        print(f"  {_c(YELLOW, 'SKIP')} unknown type {ttype!r}")
        return "SKIP"

    # ── Running phase ─────────────────────────────────────────────────────────
    spinner.next_phase()
    start = time.time()

    if live:
        spinner.stop()
        print(f"  {DIM}{'╌'*58}{RESET}")
        returncode = _stream_proc(cmd, str(ROOT))
        print(f"  {DIM}{'╌'*58}{RESET}")
    else:
        proc = subprocess.run(
            cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=120
        )
        returncode = proc.returncode
        spinner.next_phase()
        time.sleep(0.4)

    elapsed = time.time() - start

    # ── Asserting ─────────────────────────────────────────────────────────────
    if not live:
        spinner.next_phase()
        time.sleep(0.3)

    failures = []

    if ttype == "python_run":
        expect_exit = tc.get("expect_exit_code", 0)
        if returncode != expect_exit:
            failures.append(f"exit code {returncode} ≠ expected {expect_exit}")

    else:
        history_after = _history_len()
        rec = _last_history_record() if history_after > history_before else None

        expect_outcome = tc.get("expect_outcome")
        if expect_outcome and rec and rec.get("outcome") != expect_outcome:
            failures.append(f"outcome {rec.get('outcome')!r} ≠ expected {expect_outcome!r}")

        expect_source = tc.get("expect_source")
        if expect_source and rec:
            attempts = rec.get("attempts", [])
            if attempts:
                actual = attempts[-1].get("source")
                if actual != expect_source:
                    failures.append(f"source {actual!r} ≠ expected {expect_source!r}")

        expect_att = tc.get("expect_attempts")
        if expect_att is not None and rec:
            actual_att = len(rec.get("attempts", []))
            if actual_att != expect_att:
                failures.append(f"attempts {actual_att} ≠ expected {expect_att}")

        expect_att_max = tc.get("expect_attempts_max")
        if expect_att_max is not None and rec:
            actual_att = len(rec.get("attempts", []))
            if actual_att > expect_att_max:
                failures.append(f"attempts {actual_att} > max {expect_att_max}")

        if not rec and returncode not in (0,):
            failures.append("no history record written and process failed")

    # ── Cleanup phase ─────────────────────────────────────────────────────────
    if not live:
        spinner.next_phase()
        time.sleep(0.25)
        spinner.stop()

    if tc.get("reset_after"):
        parts = raw_cmd.split()
        if len(parts) >= 2:
            orig_rel = parts[-1].replace("tests/test_files/", "")
            reset_single(orig_rel)

    _do_cleanup(tc.get("cleanup_files", []))

    # ── Verdict ───────────────────────────────────────────────────────────────
    _verdict(not failures, elapsed, failures)
    return "PASS" if not failures else "FAIL"


# ── Intro banner ──────────────────────────────────────────────────────────────
def _intro(total: int):
    W = 60
    print()
    print(f"  {DIM}╔{'═'*(W-4)}╗{RESET}")
    title = f"  YOLO Test Runner  ·  {total} test(s)"
    print(f"  {DIM}║{RESET}{BOLD}{title:<{W-4}}{RESET}{DIM}║{RESET}")
    print(f"  {DIM}╚{'═'*(W-4)}╝{RESET}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]

    if "--reset" in args:
        reset_all()
        return

    cases = json.loads(CASES_FILE.read_text())

    single_id = args[args.index("--id") + 1]     if "--id"     in args else None
    filter_px = args[args.index("--filter") + 1] if "--filter" in args else None
    quiet     = "--quiet" in args or "-q" in args
    live      = not quiet

    if single_id:
        selected = [c for c in cases if c.get("id") == single_id]
        if not selected:
            print(f"{RED}No test with id {single_id!r}{RESET}")
            sys.exit(1)
    elif filter_px:
        selected = [c for c in cases if c.get("id", "").startswith(filter_px)]
        if not selected:
            print(f"{RED}No tests matching filter {filter_px!r}{RESET}")
            sys.exit(1)
    else:
        selected = cases

    selected = [c for c in selected if "id" in c]
    total    = len(selected)

    _intro(total)

    passed = failed = skipped = 0
    results = []

    for i, tc in enumerate(selected, 1):
        flaky  = tc.get("flaky", False)
        status = run_test(tc, live=live)

        if status == "FAIL" and flaky:
            print(f"\n  {_c(YELLOW, '  ↺  retrying flaky test…')}")
            time.sleep(0.4)
            status = run_test(tc, live=live)

        results.append((tc["id"], tc.get("description", tc["id"]), status))
        if status == "PASS":   passed  += 1
        elif status == "FAIL": failed  += 1
        else:                  skipped += 1

        print()
        _draw_bar(i, total, passed, failed)
        sys.stdout.write("\n")
        sys.stdout.flush()

        if i < total:
            time.sleep(0.5)

    # ── Summary ───────────────────────────────────────────────────────────────
    W = 60
    print(f"\n  {DIM}╔{'═'*(W-4)}╗{RESET}")
    print(f"  {DIM}║{RESET}{BOLD}  Summary{'':<{W-12}}{RESET}{DIM}║{RESET}")
    print(f"  {DIM}╠{'═'*(W-4)}╣{RESET}")

    for tid, desc, status in results:
        icon  = _c(GREEN, "PASS") if status == "PASS" else \
                _c(RED,   "FAIL") if status == "FAIL" else \
                _c(YELLOW, "SKIP")
        short = desc[:36] + "…" if len(desc) > 37 else desc
        row   = f"  {icon}  {DIM}{tid:<26}{RESET}  {short}"
        print(f"  {DIM}║{RESET}{row}")
        time.sleep(0.06)

    print(f"  {DIM}╠{'═'*(W-4)}╣{RESET}")
    total_line = (
        f"  {_c(GREEN, f'{passed} passed')}  "
        f"{_c(RED, f'{failed} failed')}  "
        f"{_c(YELLOW, f'{skipped} skipped')}  "
        f"{DIM}of {total}{RESET}"
    )
    print(f"  {DIM}║{RESET}{total_line}")
    print(f"  {DIM}╚{'═'*(W-4)}╝{RESET}\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
