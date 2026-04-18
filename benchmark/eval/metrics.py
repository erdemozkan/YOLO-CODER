"""
Scoring metrics for YOLO-Bench evaluation.
"""

import re


def exact_match(predicted: str, expected: str) -> bool:
    """Strict exact match after stripping whitespace."""
    return predicted.strip() == expected.strip()


def normalized_match(predicted: str, expected: str) -> bool:
    """
    Normalized match: collapse whitespace, lowercase, strip backticks/quotes.
    More forgiving than exact match for equivalent commands.
    """
    def normalize(s: str) -> str:
        s = s.strip().lower()
        s = s.strip('`\'"')
        s = re.sub(r'\s+', ' ', s)
        return s
    return normalize(predicted) == normalize(expected)


def token_overlap(predicted: str, expected: str) -> float:
    """
    Token-level F1 overlap score (0.0 - 1.0).
    Useful for partial credit on long commands.
    """
    pred_tokens = set(predicted.strip().split())
    exp_tokens = set(expected.strip().split())
    if not exp_tokens:
        return 0.0
    overlap = pred_tokens & exp_tokens
    precision = len(overlap) / len(pred_tokens) if pred_tokens else 0.0
    recall = len(overlap) / len(exp_tokens)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def score_prediction(predicted: str, expected: str) -> dict:
    """Return all metrics for a single prediction."""
    return {
        "exact_match": exact_match(predicted, expected),
        "normalized_match": normalized_match(predicted, expected),
        "token_f1": round(token_overlap(predicted, expected), 3),
    }


def aggregate_scores(results: list[dict]) -> dict:
    """Aggregate scores across all examples."""
    total = len(results)
    if total == 0:
        return {}

    exact = sum(1 for r in results if r["scores"]["exact_match"])
    normalized = sum(1 for r in results if r["scores"]["normalized_match"])
    avg_f1 = sum(r["scores"]["token_f1"] for r in results) / total

    by_category: dict[str, dict] = {}
    for r in results:
        cat = r.get("category", "unknown")
        if cat not in by_category:
            by_category[cat] = {"total": 0, "exact": 0, "normalized": 0, "f1_sum": 0.0}
        by_category[cat]["total"] += 1
        by_category[cat]["exact"] += int(r["scores"]["exact_match"])
        by_category[cat]["normalized"] += int(r["scores"]["normalized_match"])
        by_category[cat]["f1_sum"] += r["scores"]["token_f1"]

    category_summary = {}
    for cat, s in by_category.items():
        category_summary[cat] = {
            "exact_match": round(s["exact"] / s["total"] * 100, 1),
            "normalized_match": round(s["normalized"] / s["total"] * 100, 1),
            "avg_token_f1": round(s["f1_sum"] / s["total"], 3),
            "count": s["total"],
        }

    return {
        "total_examples": total,
        "exact_match_pct": round(exact / total * 100, 1),
        "normalized_match_pct": round(normalized / total * 100, 1),
        "avg_token_f1": round(avg_f1, 3),
        "by_category": category_summary,
    }
