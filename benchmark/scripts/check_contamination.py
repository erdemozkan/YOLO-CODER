#!/usr/bin/env python3
"""
Checks for overlap between the benchmark test set and training data.
Compares error messages using exact match and fuzzy fingerprinting.

Usage:
    python3 check_contamination.py --training-data /path/to/train.jsonl
"""

import argparse
import json
import re
import hashlib
from pathlib import Path

DATASET = Path(__file__).parent.parent / "dataset" / "test_set.jsonl"


def fingerprint(text: str) -> str:
    """Normalize and hash an error message for comparison."""
    t = text.lower().strip()
    t = re.sub(r"line \d+", "line N", t)
    t = re.sub(r"0x[0-9a-f]+", "0xADDR", t)
    t = re.sub(r"\b\d+\b", "N", t)
    t = re.sub(r"\s+", " ", t)
    return hashlib.md5(t.encode()).hexdigest()


def load_jsonl(path: str) -> list[dict]:
    examples = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))
    return examples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--training-data", required=True,
                        help="Path to training JSONL file")
    args = parser.parse_args()

    test_examples = load_jsonl(str(DATASET))
    train_examples = load_jsonl(args.training_data)

    print(f"Test set  : {len(test_examples)} examples")
    print(f"Train set : {len(train_examples)} examples\n")

    train_fps = {}
    for ex in train_examples:
        error_field = ex.get("error") or ex.get("input") or ex.get("user", "")
        fp = fingerprint(error_field)
        train_fps[fp] = ex

    contaminated = []
    for ex in test_examples:
        fp = fingerprint(ex.get("error", ""))
        if fp in train_fps:
            contaminated.append({
                "test_id": ex["id"],
                "test_error": ex["error"][:80],
                "train_match": str(train_fps[fp])[:80],
            })

    if contaminated:
        print(f"⚠️  {len(contaminated)} CONTAMINATED examples found:\n")
        for c in contaminated:
            print(f"  [{c['test_id']}] {c['test_error']}")
            print(f"   → train: {c['train_match']}\n")
    else:
        print(f"✓ No contamination detected. Test set is clean.")

    print(f"\nOverlap rate: {len(contaminated)}/{len(test_examples)} "
          f"({len(contaminated)/len(test_examples)*100:.1f}%)")


if __name__ == "__main__":
    main()
