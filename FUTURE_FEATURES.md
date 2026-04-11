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
