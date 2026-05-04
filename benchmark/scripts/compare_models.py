#!/usr/bin/env python3
"""
Compares multiple eval result files and prints a leaderboard table.

Usage:
    python3 compare_models.py results/*.json
"""

import argparse
import json
from pathlib import Path


def load_result(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+", help="Result JSON files to compare")
    args = parser.parse_args()

    rows = []
    for path in args.files:
        data = load_result(path)
        meta = data["meta"]
        summary = data["summary"]
        rows.append({
            "model": meta["model"],
            "provider": meta["provider"],
            "n": summary["total_examples"],
            "exact": summary["exact_match_pct"],
            "normalized": summary["normalized_match_pct"],
            "f1": summary["avg_token_f1"],
        })

    rows.sort(key=lambda r: r["normalized"], reverse=True)

    col_w = max(len(r["model"]) for r in rows) + 2
    header = f"{'Model':<{col_w}} {'Provider':<12} {'N':>5} {'Exact%':>8} {'Norm%':>8} {'Avg F1':>8}"
    print(f"\n{'─' * len(header)}")
    print("  YOLO-Bench Leaderboard")
    print(f"{'─' * len(header)}")
    print(f"  {header}")
    print(f"  {'─' * (len(header) - 2)}")
    for i, r in enumerate(rows):
        medal = ["🥇", "🥈", "🥉"][i] if i < 3 else "  "
        print(f"{medal} {r['model']:<{col_w}} {r['provider']:<12} {r['n']:>5} "
              f"{r['exact']:>7.1f}% {r['normalized']:>7.1f}% {r['f1']:>8.3f}")
    print(f"{'─' * len(header)}\n")


if __name__ == "__main__":
    main()
