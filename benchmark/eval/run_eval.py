#!/usr/bin/env python3
"""
YOLO-Bench Evaluation Runner

Usage:
    # Run against a local Ollama model
    python3 run_eval.py --provider ollama --model hf.co/erdemozkan/YOLO-7B-Qwen-Coder

    # Run against GPT-4o
    python3 run_eval.py --provider openai --model gpt-4o

    # Run against Claude
    python3 run_eval.py --provider anthropic --model claude-sonnet-4-6

    # Run the full YOLO pipeline (interceptors → memory → LLM)
    python3 run_eval.py --provider yolo --model yolo-7b

    # Filter by category
    python3 run_eval.py --provider ollama --model yolo-7b --category python

    # Skip unverified examples
    python3 run_eval.py --provider ollama --model yolo-7b --verified-only
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
DATASET = ROOT.parent / "dataset" / "test_set.jsonl"
RESULTS_DIR = ROOT.parent / "results"

sys.path.insert(0, str(ROOT))
from metrics import score_prediction, aggregate_scores


def load_dataset(category: str | None = None, verified_only: bool = False,
                 dataset_path: Path | None = None) -> list[dict]:
    path = dataset_path or DATASET
    examples = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ex = json.loads(line)
            if verified_only and not ex.get("verified", False):
                continue
            if category and ex.get("category") != category:
                continue
            if ex.get("note") == "requires_file_patch":
                continue  # skip patch-only examples for command eval
            examples.append(ex)
    return examples


def get_provider(name: str):
    if name == "ollama":
        from models.ollama import predict
        return predict
    elif name == "openai":
        from models.openai_provider import predict
        return predict
    elif name == "anthropic":
        from models.anthropic_provider import predict
        return predict
    elif name == "yolo":
        from models.yolo_pipeline import predict
        return predict
    elif name == "yolo_openai":
        from models.yolo_pipeline_openai import predict
        return predict
    elif name == "yolo_anthropic":
        from models.yolo_pipeline_anthropic import predict
        return predict
    else:
        raise ValueError(f"Unknown provider: {name}")


def run_eval(provider_name: str, model: str, category: str | None,
             verified_only: bool, verbose: bool, attempts: int = 1,
             dataset_path: Path | None = None) -> dict:
    predict = get_provider(provider_name)
    examples = load_dataset(category=category, verified_only=verified_only,
                            dataset_path=dataset_path)

    if not examples:
        print("No examples matched the filters.")
        sys.exit(1)

    print(f"\n{'─'*60}")
    print(f"  YOLO-Bench Evaluation")
    print(f"  Provider : {provider_name}")
    print(f"  Model    : {model}")
    print(f"  Examples : {len(examples)}")
    print(f"{'─'*60}\n")

    results = []
    for i, ex in enumerate(examples, 1):
        error = ex["error"]
        expected_primary = ex["expected_fix"]
        alt_fixes = ex.get("alt_fixes", [])
        all_expected = [expected_primary] + alt_fixes

        predicted = predict(error, model=model, command=ex.get("command", ""), attempts=attempts)

        # Support multi-attempt providers that return a list of predictions.
        # Score each attempt, keep the best result.
        if isinstance(predicted, list):
            all_predictions = predicted
            best_scores = None
            best_pred   = all_predictions[0] if all_predictions else ""
            for p in all_predictions:
                s = score_prediction(p, all_expected)
                if best_scores is None or s["structural_match"] > best_scores["structural_match"] \
                        or (s["structural_match"] == best_scores["structural_match"]
                            and s["token_f1"] > best_scores["token_f1"]):
                    best_scores = s
                    best_pred   = p
            scores    = best_scores
            predicted = best_pred
        else:
            all_predictions = [predicted]
            scores = score_prediction(predicted, all_expected)

        result = {
            "id": ex["id"],
            "category": ex["category"],
            "error": error,
            "expected": expected_primary,
            "alt_fixes": alt_fixes,
            "predicted": predicted,
            "all_predictions": all_predictions,
            "scores": scores,
        }
        results.append(result)

        if scores["exact_match"]:
            status = "✓"
        elif scores["structural_match"]:
            status = "≈"
        elif scores["normalized_match"]:
            status = "~"
        else:
            status = "✗"

        attempts_str = f" ({len(all_predictions)} attempts)" if len(all_predictions) > 1 else ""
        if verbose or not scores["structural_match"]:
            print(f"[{i:3}/{len(examples)}] {status} {ex['id']}{attempts_str}")
            if not scores["structural_match"]:
                print(f"          expected : {expected_primary}")
                for j, p in enumerate(all_predictions, 1):
                    print(f"          attempt {j}: {p}")
        else:
            print(f"[{i:3}/{len(examples)}] {status} {ex['id']}{attempts_str}")

        time.sleep(0.1)  # avoid hammering local Ollama

    summary = aggregate_scores(results)

    # Print summary table
    print(f"\n{'─'*60}")
    print(f"  Results — {model}")
    print(f"{'─'*60}")
    print(f"  Exact match      : {summary['exact_match_pct']}%")
    print(f"  Normalized match : {summary['normalized_match_pct']}%")
    print(f"  Structural match : {summary['structural_match_pct']}%")
    print(f"  Avg token F1     : {summary['avg_token_f1']}")
    print(f"\n  By category:")
    for cat, s in sorted(summary["by_category"].items()):
        print(f"    {cat:<12} exact={s['exact_match']}%  struct={s['structural_match']}%  n={s['count']}")
    print(f"{'─'*60}\n")

    # Save results
    RESULTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_model = model.replace("/", "_").replace(":", "_")
    out_path = RESULTS_DIR / f"{ts}_{provider_name}_{safe_model}.json"
    with open(out_path, "w") as f:
        json.dump({
            "meta": {
                "provider": provider_name,
                "model": model,
                "timestamp": ts,
                "total_examples": len(examples),
                "filters": {"category": category, "verified_only": verified_only},
            },
            "summary": summary,
            "results": results,
        }, f, indent=2)
    print(f"  Results saved → {out_path.name}\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description="YOLO-Bench evaluation runner")
    parser.add_argument("--provider", required=True,
                        choices=["ollama", "openai", "anthropic", "yolo", "yolo_openai", "yolo_anthropic"],
                        help="LLM provider to use (yolo = full pipeline: interceptors → memory → LLM)")
    parser.add_argument("--model", required=True,
                        help="Model name (e.g. hf.co/erdemozkan/YOLO-7B-Qwen-Coder, gpt-4o)")
    parser.add_argument("--category", default=None,
                        help="Filter by category: python, pip, nodejs, npm, typescript, docker, git, shell")
    parser.add_argument("--verified-only", action="store_true",
                        help="Only run examples marked as verified=true")
    parser.add_argument("--verbose", action="store_true",
                        help="Print all predictions, not just failures")
    parser.add_argument("--attempts", type=int, default=1,
                        help="Number of LLM attempts per example (yolo provider only, default 1)")
    parser.add_argument("--dataset", default=None,
                        help="Path to dataset JSONL file (default: benchmark/dataset/test_set.jsonl)")
    args = parser.parse_args()

    run_eval(
        provider_name=args.provider,
        model=args.model,
        category=args.category,
        verified_only=args.verified_only,
        verbose=args.verbose,
        attempts=args.attempts,
        dataset_path=Path(args.dataset) if args.dataset else None,
    )


if __name__ == "__main__":
    main()
