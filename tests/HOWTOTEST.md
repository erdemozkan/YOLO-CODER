# Testing Guide

This document explains how to run, reset, and extend the YOCO test suite.

---

## How the test suite works

YOCO's tests are end-to-end: the runner invokes `yoco python3 <broken_file>` for real, then checks the outcome matches what was expected. Test files live in `test_files/` and are intentionally broken. YOCO fixes them during the run, which mutates them on disk.

Because of this, **test files are not pristine after a run.** Always reset before a fresh run.

---

## Running the tests

Run all tests from the project root:

```bash
python3 tests/run_tests.py
```

Run a specific category:

```bash
python3 tests/run_tests.py --filter unit
python3 tests/run_tests.py --filter llm
python3 tests/run_tests.py --filter integration
python3 tests/run_tests.py --filter security
python3 tests/run_tests.py --filter rollback
```

Run a single test by ID:

```bash
python3 tests/run_tests.py --id unit_syntax_colon
python3 tests/run_tests.py --id llm_division_zero
```

Quiet mode (spinner only, no subprocess output):

```bash
python3 tests/run_tests.py --quiet
```

---

## Resetting test files

Test files in `test_files/` are mutated by test runs. Restore them all to their original broken state before a fresh run:

```bash
python3 tests/run_tests.py --reset
```

This copies every file from `tests/originals/` back into `tests/test_files/`, overwriting whatever YOCO left behind.

**Always reset before running the full suite from scratch.**

---

## Test categories

| Category | What it tests | Speed | Requires Ollama? |
|---|---|---|---|
| `unit` | One interceptor per file — deterministic regex fixes | Fast | No |
| `llm` | Errors that fall through to the local LLM | Slow (~3–20s each) | Yes |
| `integration` | Multi-error files, stacked failures | Medium | Sometimes |
| `security` | `FixResult.is_valid()` against dangerous command patterns | Fast | No |
| `rollback` | Unfixable error exhausts 3 attempts, auto-rollback triggered | Slow | Yes |

LLM tests are marked `flaky: true` in `test_cases.json` because the model output is non-deterministic. If one fails, retry it in isolation before assuming a regression.

---

## Test file structure

```
tests/
  run_tests.py          ← test runner
  test_cases.json       ← test definitions (the source of truth)
  test_files/           ← live working copies (mutated by runs)
    unit/               ← one file per interceptor
    llm/                ← files that trigger the LLM path
    multifile/          ← easy / medium / hard multi-file scenarios
    integration/        ← stacked errors, boss fights
    security/           ← FixResult validation tests
    rollback/           ← unfixable scenarios
  originals/            ← pristine broken copies (never edit these)
    unit/
    llm/
    multifile/
    ...
```

`originals/` is the ground truth. The runner copies from here on `--reset`. Never modify files in `originals/` directly — that's the baseline.

---

## Adding a new test

### Step 1 — Write the broken file

Create a broken Python (or other) file in the appropriate `test_files/` subdirectory:

```python
# tests/test_files/unit/my_new_error.py
# Broken: uses an undefined variable
print(undefined_variable)
```

Choose the right subdirectory:
- `unit/` — one specific error, should be caught by an interceptor
- `llm/` — error that needs the LLM to fix
- `integration/` — multiple stacked errors
- `multifile/` — bug surfaces in one file but lives in another

### Step 2 — Copy it to originals/

```bash
cp tests/test_files/unit/my_new_error.py tests/originals/unit/my_new_error.py
```

This is critical. Without a copy in `originals/`, `--reset` cannot restore the file and the test becomes unrunnable after the first mutation.

### Step 3 — Add the test case to test_cases.json

Open `tests/test_cases.json` and add an entry in the appropriate section:

```json
{
  "id": "unit_my_new_error",
  "description": "Interceptor — NameError: undefined variable",
  "type": "yolo_run",
  "command": "python3 tests/test_files/unit/my_new_error.py",
  "expect_outcome": "success",
  "expect_source": "interceptor",
  "expect_attempts": 1,
  "expect_files_modified": ["tests/test_files/unit/my_new_error.py"],
  "reset_after": true,
  "cleanup_files": []
}
```

Key fields:

| Field | Description |
|---|---|
| `id` | Unique snake_case identifier — used with `--id` flag |
| `description` | Human-readable label shown in test output |
| `type` | `yolo_run` (invokes full YOCO pipeline) or `python_run` (runs file directly) |
| `command` | The command YOCO will wrap |
| `expect_outcome` | `success` or `rolled_back` |
| `expect_source` | `interceptor`, `memory`, or `llm` (omit if don't care) |
| `expect_attempts` | Exact attempt count (omit if using `expect_attempts_max`) |
| `expect_attempts_max` | Upper bound on attempts |
| `reset_after` | `true` restores the file from `originals/` after the test |
| `cleanup_files` | Extra files/dirs YOCO created during the fix that need to be deleted |
| `flaky` | `true` marks LLM tests that may fail non-deterministically |

### Step 4 — Run your new test

```bash
python3 tests/run_tests.py --id unit_my_new_error
```

### Step 5 — Reset and run the full suite

```bash
python3 tests/run_tests.py --reset
python3 tests/run_tests.py
```

---

## Common issues

**Test file is already fixed (exit 0 before YOCO runs)**
The file in `test_files/` was already mutated by a previous run. Run `--reset` first.

**LLM test keeps failing**
Check that Ollama is running: `ollama serve`. Then retry the test in isolation with `--id`. LLM output is non-deterministic — one failure is not necessarily a regression.

**`reset_after` is true but file wasn't restored**
The file might not exist in `originals/`. Check that you copied it there in Step 2.

**cleanup_files left behind**
If a test creates extra files (e.g. `config.json`, `logs/`) and the test runner crashes before cleanup, remove them manually before the next run.
