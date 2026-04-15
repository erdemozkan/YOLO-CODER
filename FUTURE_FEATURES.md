# YOLO — Future Features

A living list of features, architectural directions, and ideas that are
intentionally deferred. Each entry includes the reasoning behind deferral
so future decisions have context.

---

## 1. YOLO Server / YOLO CI Mode with Docker-First Sandbox

**What it is:**
A dedicated server or CI-runner variant of YOLO where Docker is a
first-class, required dependency — not an optional add-on. The architecture
would be designed around container isolation from the ground up rather than
retrofitted onto the current in-process model.

**Why deferred:**
The current YOLO architecture has interceptors that write files directly
in-process (interceptors 1–6), making Docker isolation impossible to retrofit
cleanly without a full rewrite of the execution layer. The pip/npm environment
problem (installs happen inside the container, not the user's real env) also
has no clean solution in the current design. Docker startup latency
(1.5–4s per fix on macOS) is a UX killer for a local dev tool.

**What it would require:**
- Refactor all interceptors to emit pure shell commands instead of doing
  in-process file writes — Docker can only sandbox subprocess calls, not
  Python code running in the same process.
- A warm container pool to eliminate per-fix startup overhead.
- Per-project Docker image selection (Python version matching, Node version,
  Rust toolchain, etc.).
- A write-back protocol: run fix in container → validate result → atomically
  apply to real project.
- A separate `yolo-server` or `yolo-ci` entry point that requires Docker
  and refuses to run without it — no graceful degradation in server mode.

**When it makes sense:**
- YOLO used in CI/CD pipelines where isolation is a hard requirement.
- Multi-user environments (shared dev servers) where one user's fix command
  should not affect others.
- When the model grows large enough to generate complex multi-file fixes
  that justify the container overhead.

---

*Add new items below with the same structure: what it is, why deferred, what it would require, when it makes sense.*

---

## 2. PyPI Publishing — `pip install yoco`

**What it is:**
Publishing the `yoco` package to the Python Package Index so users can install
it globally with `pip install yoco` without cloning the repo first.

**Why deferred:**
Requires a PyPI account, an API token, and a stable versioned release on GitHub
before the tarball URL and SHA256 can be locked in. The package name `yoco`
also needs to be claimed on PyPI before someone else does.

**What it would require:**
- A published GitHub release tag (e.g. `v0.0.2`) so the source tarball exists.
- `pip install build twine` on the maintainer's machine.
- `python3 -m build` to generate `dist/yoco-0.0.2.tar.gz` and the wheel.
- `twine upload dist/*` with a valid PyPI API token.
- After first publish, subsequent releases are just bump version → build → upload.

**When it makes sense:**
As soon as the first stable GitHub release is tagged. Should happen alongside
or immediately after completing the Homebrew formula.

---

## 3. Lean Terminal UI

**What it is:**
A rich, interactive terminal dashboard that runs while YOCO is working — showing
live error output, which brain is active (interceptor / memory / LLM), fix
confidence, file diff preview, and a spinner with real progress instead of
raw subprocess output streaming to stdout.

**Why deferred:**
The current streaming output model (subprocess stdout piped directly to terminal)
is simple and transparent but not pretty. Building a proper TUI requires either
`textual` or `curses`, which adds a non-trivial dependency and makes piped/CI
usage harder (TUIs break in non-TTY environments). The fix pipeline also needs
to emit structured events rather than raw print statements for the TUI to consume.

**What it would require:**
- Refactor the fix pipeline to emit structured events (started, interceptor_match,
  llm_called, fix_applied, retrying, rolled_back) instead of printing directly.
- A TUI layer (Textual recommended) that subscribes to those events and renders
  them in panes: error panel, fix panel, file diff panel, status bar.
- Graceful fallback to plain stdout when not running in a TTY (CI, pipes, tests).
- The existing `YoloSpinner` class would be replaced by the TUI's status bar.

**When it makes sense:**
After the core fix pipeline is stable and the event model is well-defined.
Good candidate for a contributor project — the interface is clean and isolated.

---

## 4. YOCO Web — Browser-Based Interface

**What it is:**
A local web application (similar to Claude Code's web UI) that lets users interact
with YOCO through a browser instead of the terminal. Paste an error, see the fix,
accept or reject it, browse history, manage fix memory — all in a clean web UI.

**Why deferred:**
YOCO's core value is zero-friction — one command in the terminal. A web UI adds
a server process, a browser tab, and a port to manage. It's more useful for
teams and non-terminal users than for the solo dev workflow YOCO is optimised for.
Also requires a WebSocket or SSE layer to stream fix progress in real time.

**What it would require:**
- A lightweight local server (`fastapi` + `uvicorn` recommended) that wraps the
  fix pipeline and exposes it over HTTP/WebSocket.
- A frontend (plain HTML + JS or a small React app) with: error input, fix output,
  file diff viewer, history browser, fix memory manager, config editor.
- A `yoco --web` flag that starts the server and opens the browser automatically.
- Authentication (even just a local token) so the server can't be reached by
  other processes on the machine.
- The same graceful shutdown behaviour as `--watch` mode (Ctrl+C kills server).

**When it makes sense:**
- When YOCO is used in team environments where not everyone is comfortable in
  the terminal.
- As a companion to the VS Code extension (share the same local server).
- After the lean TUI is built, since both require the structured event model.

---

## 5. Audit Mode — `yoco --audit`

**What it is:**
A subcommand that scans an entire codebase statically — without running anything — and produces a report of likely errors, bad patterns, and fixable issues across all files. Think `yoco --audit ./src` outputting a prioritised list of problems with suggested fixes, similar to how a linter works but powered by the LLM rather than static rules.

**Why deferred:**
YOCO's current design is reactive — it waits for a command to fail, then fixes it. Proactive auditing requires a fundamentally different mode: iterating over files, building context, and generating fixes without a triggering error. This is more expensive (many LLM calls), slower, and risks hallucinating problems that don't exist. The scanner infrastructure (`core/scanner.py`) is a starting point but not sufficient.

**What it would require:**
- A file walker that respects `.gitignore` and collects all source files in the project.
- A batching strategy to send files to the LLM in chunks with enough context per batch.
- A structured output format from the LLM: file, line, issue type, suggested fix command.
- A deduplication pass (the same pattern may appear in many files).
- An interactive review mode: show issues one by one, let user accept/skip/apply.
- Respect for `max_attempts` and a total token budget to avoid runaway costs on large repos.

**When it makes sense:**
- When onboarding a legacy codebase — run once to get a health report.
- As a pre-commit hook: `yoco --audit --changed-only` to check only staged files.
- After the LLM agent is stable enough that false-positive rate is acceptably low.

---

## 6. Benchmark — YOCO vs Frontier Models at Code Fixing

**What it is:**
A public, reproducible benchmark that measures YOCO's fine-tuned models against frontier models (GPT-4o, Claude Sonnet, Gemini Pro, Llama 3, etc.) on the task of CLI error fixing. Metrics: fix success rate, fix latency, token efficiency, and false-positive rate (fixes that "work" but introduce new bugs).

**Why deferred:**
A credible benchmark requires a held-out test set that was never used in training, a standardised evaluation harness, and compute to run all models at scale. The current `tests/test_cases.json` suite is not held-out — it was used to validate the pipeline during development, not as a blind evaluation set. Running frontier model APIs also costs money and requires API keys, which contradicts the local-only philosophy for users but is fine for a one-time benchmark by the maintainer.

**What it would require:**
- A held-out evaluation set of 200+ error/fix pairs not present in the training data.
- An automated harness that runs each model on every case, applies the fix, and re-runs the original command to verify the fix actually worked (not just syntactically valid).
- Adapters for each frontier model's API (OpenAI, Anthropic, Google, together.ai for open weights).
- A results dashboard — markdown table at minimum, ideally a live leaderboard page.
- A reproducibility guarantee: pinned model versions, fixed random seeds, public test set.

**When it makes sense:**
- Before a major version release (v1.0) to establish credibility and justify the fine-tuning investment.
- Whenever a new model version is trained — use the benchmark to verify it's actually better.
- As a community contribution target: others can add new models to the harness via PR.
