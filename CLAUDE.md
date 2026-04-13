# YOLO — Developer Guide

YOLO is an automated CLI repair tool. You run a broken command; YOLO catches the error, figures out a fix, applies it, and retries — all without you touching anything. It runs locally, uses a local LLM (Ollama), and never phones home.

---

## What it does

```
yoco python3 myapp.py
```

1. Runs the command.
2. If it fails, captures stderr.
3. Tries an interceptor (fast, deterministic regex rules) first.
4. If no interceptor matches, checks fix memory (past successful fixes).
5. If memory misses, calls the local LLM.
6. Applies the fix, retries the original command.
7. Repeats up to 3 attempts.

If it works, it snapshots the fix. If it doesn't, it rolls back. The user sees what changed and why.

---

## Architecture

```
yoco.py                  ← entry point, CLI flags, main loop
core/
  agent.py               ← LLM interaction, prompt construction, response parsing
  interceptors.py        ← 23 deterministic fix rules (no LLM involved)
  memory.py              ← fix memory: fingerprint errors, cache successful fixes
  snapshot.py            ← file snapshots before any change, rollback support
  history.py             ← append-only run log (~/.yolo/history.jsonl)
  config.py              ← loads critical_config.json + ~/.yolo/config.json
  schema.py              ← FixResult dataclass (the unit of work between layers)
  diff.py                ← shows what changed after a fix
  explain.py             ← deep-dive AI explanation of errors (--explain)
  project.py             ← detects project type (Python/Node/Rust/etc.)
  preflight.py           ← checks Ollama is running, model is available
  scanner.py             ← scans for related files (multi-file context)
  watcher.py             ← --watch mode: re-runs on file change
  logger.py              ← structured run logging
  utils.py               ← small shared helpers
yoco_replace.py          ← targeted single-line file patcher
skills/                  ← pluggable skill modules
tests/
  run_tests.py           ← test runner
  test_files/            ← working copies (mutated by tests)
  originals/             ← pristine copies (restore with --reset)
  tests.json             ← test case definitions
```

---

## The fix pipeline in detail

**Interceptors** (`core/interceptors.py`) are regex rules that fire before anything else. There are 23 of them covering Python imports, pip errors, permission errors, file-not-found, Node.js module errors, npm errors, TypeScript errors, Docker image/port/container/daemon errors, and Git errors. Each interceptor returns a `FixResult` with a shell command to run or a file patch to apply. Interceptors are O(1) — no LLM call, no disk I/O beyond the fix itself.

**Fix Memory** (`core/memory.py`) fingerprints each error by type and call site, normalized to strip line numbers and variable names. If the fingerprint matches a past successful fix, that fix is replayed directly. Stored in `~/.yolo/fix_memory.jsonl`. Minimum confidence: 1 prior success.

**LLM Agent** (`core/agent.py`) is the fallback. Sends the error + surrounding code context to the local model via OpenAI-compatible API (`http://localhost:11434/v1`). Default model: `yolo-coder` (fine-tuned Qwen2.5-Coder-7B). The prompt asks for a single bare bash command. Response is validated before execution — no arbitrary code eval without a safety check.

**Snapshot + Rollback** (`core/snapshot.py`) takes a snapshot of every file before touching it — only the first snapshot per file per session, so the pre-YOLO state is always preserved even across multiple fix attempts. Session is persisted to `~/.yolo/last_session.json` so `--rollback` works after the process exits.

---

## Key flags

```
yoco <command>              # fix mode
yoco --dry-run <command>    # show fix without applying
yoco --explain <command>    # run + deep-dive AI explanation
yoco --watch <command>      # re-run on file change
yoco --rollback             # interactive picker: undo last session
yoco --rollback <file>      # restore specific file
yoco --history              # browse past runs
yoco --history N            # show run N in detail
yoco --model <name>         # override model for this run
yoco --config               # print active config
```

---

## Models

YOLO expects an Ollama-compatible endpoint at `http://localhost:11434/v1`.

**Our fine-tuned models are available on Hugging Face:**

| Model | Notes |
|---|---|
| `erdemozkan/YOLO-1.5B-Qwen-Coder` | Default. Fine-tuned Qwen2.5-Coder-1.5B on 2,250 CLI error/fix pairs. Pull with: `ollama run hf.co/erdemozkan/YOLO-1.5B-Qwen-Coder` |
| `erdemozkan/YOLO-7B-Qwen-Coder` | Larger. Fine-tuned Qwen2.5-Coder-7B on the same dataset. Pull with: `ollama run hf.co/erdemozkan/YOLO-7B-Qwen-Coder` |
| `qwen2.5-coder:7b` | Vanilla base, no fine-tuning. |

Fine-tuning uses MLX LoRA on Apple Silicon. Training data is in `YOLO-MODEL-FILES/data/`. Dataset generator is `YOLO-MODEL-FILES/generate_dataset.py`. Format is ChatML with a system prompt telling the model to output a single bare bash command.

To switch models permanently:

```json
// ~/.yolo/config.json
{ "model": "yolo-7b" }
```

---

## Tests

```bash
python3 tests/run_tests.py              # run all tests
python3 tests/run_tests.py --reset      # restore test files from originals
python3 tests/run_tests.py unit         # run a specific category
```

Test files in `tests/test_files/` are live — YOLO mutates them during runs. The originals are in `tests/originals/`. Always `--reset` before a full test run. Test definitions live in `tests/tests.json`.

---

## Config

Config is layered: `critical_config.json` (repo-level, committed) < `~/.yolo/config.json` (user-level, not committed). User config wins on conflicts.

Fields that matter:

```json
{
  "model": "yolo-coder",
  "endpoint": "http://localhost:11434/v1",
  "max_attempts": 3,
  "dry_run": false,
  "log_runs": true
}
```

---

## State files

All runtime state lives in `~/.yolo/`:

```
~/.yolo/
  config.json          ← user config overrides
  fix_memory.jsonl     ← cached successful fixes
  last_session.json    ← snapshot of last run (for --rollback)
  history.jsonl        ← append-only run log (trimmed to 200 entries)
  logs/                ← structured run logs
```

To fully reset YOLO state: `rm -rf ~/.yolo/fix_memory.jsonl ~/.yolo/last_session.json`

---

## Adding an interceptor

Open `core/interceptors.py`. Each interceptor is a function that receives `(error_msg: str, command: str)` and returns a `FixResult | None`. Add yours to the `INTERCEPTORS` list at the bottom of the file. Order matters — first match wins.

```python
def intercept_my_error(error_msg: str, command: str) -> FixResult | None:
    if "my specific error string" not in error_msg:
        return None
    return FixResult(fix_command="the shell command to run", source="interceptor")

INTERCEPTORS = [
    ...
    intercept_my_error,
]
```

Interceptors should be specific. A rule that matches too broadly will shadow LLM fixes for errors it can't actually handle.

---

## What not to do

- Don't add LLM calls inside interceptors. Interceptors are the fast path.
- Don't modify `tests/originals/` — those are the ground truth. Modify `tests/test_files/` instead (or let YOLO do it).
- Don't persist state anywhere outside `~/.yolo/`. The repo directory should stay clean.
- Don't change the prompt in `agent.py` to be more verbose. The model is trained to produce a single command. Verbose output breaks the parser.
- Don't run the f16 GGUF (15GB) on a 16GB machine — it will kernel panic. Use the Q4_K_M quantized version.
