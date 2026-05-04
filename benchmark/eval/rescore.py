#!/usr/bin/env python3
"""
Re-scores an existing result JSON with the current metrics (structural_match,
multi-answer alt_fixes) without re-running inference.

Usage:
    python3 rescore.py results/20260417_151954_ollama_yolo-7b.json
"""
import json, sys
from pathlib import Path

ROOT    = Path(__file__).parent
DATASET = ROOT.parent / "dataset" / "test_set.jsonl"
RESULTS = ROOT.parent / "results"

sys.path.insert(0, str(ROOT))
from metrics import score_prediction, aggregate_scores

# Load dataset for alt_fixes
dataset = {}
with open(DATASET) as f:
    for line in f:
        line = line.strip()
        if not line: continue
        ex = json.loads(line)
        dataset[ex["id"]] = ex

for path in sys.argv[1:]:
    data = json.load(open(path))
    for r in data["results"]:
        ex = dataset.get(r["id"], {})
        primary  = r["expected"]
        alt_fixes = ex.get("alt_fixes", [])
        r["alt_fixes"] = alt_fixes
        r["scores"] = score_prediction(r["predicted"], [primary] + alt_fixes)

    data["summary"] = aggregate_scores(data["results"])
    out = RESULTS / ("rescored_" + Path(path).name)
    with open(out, "w") as f:
        json.dump(data, f, indent=2)
    s = data["summary"]
    print(f"{Path(path).name}")
    print(f"  exact={s['exact_match_pct']}%  norm={s['normalized_match_pct']}%  struct={s['structural_match_pct']}%  f1={s['avg_token_f1']}")
    print(f"  → {out.name}")
