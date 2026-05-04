# YOLO-Bench

The first benchmark for **CLI error → fix command** evaluation.

Given a raw terminal error message, models must output a single bare shell command that resolves the error. No explanations, no markdown, just the fix.

## Dataset

**232 examples** across 15 categories, all independently sourced and verified (94% execution-verified):

| Category   | Count | Sources |
|------------|-------|---------|
| Python     | 45    | Manual, Stack Overflow |
| Shell      | 20    | Manual, Stack Overflow |
| Docker     | 20    | Manual, Stack Overflow |
| Git        | 25    | Manual, Stack Overflow |
| npm        | 15    | Stack Overflow |
| Node.js    | 15    | Manual, Stack Overflow |
| TypeScript | 15    | Stack Overflow |
| pip        | 15    | Stack Overflow |
| Cargo/Rust | 15    | Stack Overflow |
| SSH        | 10    | Manual, Stack Overflow |
| Database   | 10    | Manual, Stack Overflow |
| venv/conda | 10    | Stack Overflow |
| Cloud (AWS/GCP) | 6 | Manual |
| Make/CMake | 7     | Manual, Stack Overflow |
| Yarn       | 4     | Stack Overflow |

All examples are **verified** (fix actually resolves the error) and **zero-overlap** with YOLO fine-tuning training data.

## Scoring

Three metrics reported per model:

- **Exact match %** — predicted command matches expected exactly (after strip)
- **Normalized match %** — match after lowercasing, collapsing whitespace, stripping quotes
- **Avg token F1** — token-level overlap, gives partial credit for nearly-correct commands

## Running an Evaluation

### Against a local Ollama model

```bash
cd eval
python3 run_eval.py --provider ollama --model hf.co/erdemozkan/YOLO-7B-Qwen-Coder
python3 run_eval.py --provider ollama --model hf.co/erdemozkan/YOLO-1.5B-Qwen-Coder
```

### Against frontier models

```bash
export OPENAI_API_KEY=sk-...
python3 run_eval.py --provider openai --model gpt-4o

export ANTHROPIC_API_KEY=sk-ant-...
python3 run_eval.py --provider anthropic --model claude-sonnet-4-6
```

### Filter by category

```bash
python3 run_eval.py --provider ollama --model yolo-7b --category git
python3 run_eval.py --provider ollama --model yolo-7b --verified-only
```

### Compare multiple models

```bash
python3 scripts/compare_models.py results/*.json
```

## Checking for Contamination

```bash
python3 scripts/check_contamination.py --training-data /path/to/your/train.jsonl
```

## File Structure

```
benchmark/
  dataset/
    test_set.jsonl         ← 50 test cases
  eval/
    run_eval.py            ← main evaluation runner
    metrics.py             ← exact match, normalized match, token F1
    models/
      ollama.py            ← Ollama provider
      openai_provider.py   ← OpenAI / GPT provider
      anthropic_provider.py← Anthropic / Claude provider
  scripts/
    check_contamination.py ← verify zero overlap with training data
    compare_models.py      ← leaderboard table from result files
  results/                 ← saved JSON results per run
```

## Example Output

```
────────────────────────────────────────────────────────────
  YOLO-Bench Leaderboard
────────────────────────────────────────────────────────────
  Model                      Provider      N    Exact%    Norm%   Avg F1
  ─────────────────────────────────────────────────────────────────────
🥇 YOLO-7B-Qwen-Coder        ollama       48     78.0%    83.0%    0.891
🥈 gpt-4o                    openai       48     72.0%    79.0%    0.856
🥉 YOLO-1.5B-Qwen-Coder      ollama       48     68.0%    74.0%    0.821
```
