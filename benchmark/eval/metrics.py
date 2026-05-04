"""
Scoring metrics for YOLO-Bench evaluation.

Three tiers:
  exact_match      — character-perfect after whitespace strip
  normalized_match — lowercase, quote-normalized, whitespace-collapsed
  structural_match — flag-order-independent, quote-normalized, compound-command-aware
  token_f1         — partial credit

All scoring functions accept a single expected string or a list of alternates.
A prediction is correct if it matches ANY of the expected answers.
"""

import re
import shlex


# ── Helpers ───────────────────────────────────────────────────────────────────

def _base_clean(s: str) -> str:
    """Strip outer whitespace, backticks, collapse internal whitespace."""
    s = s.strip().strip('`')
    s = re.sub(r'\s+', ' ', s)
    return s


def _normalize(s: str) -> str:
    """Lowercase + base clean + normalize quotes to single."""
    s = _base_clean(s).lower()
    s = s.replace('"', "'")
    return s


def _split_compound(cmd: str) -> list[str]:
    """Split on && into ordered segments."""
    return [seg.strip() for seg in re.split(r'\s*&&\s*', cmd.strip())]


def _parse_segment(seg: str) -> tuple[tuple, frozenset, tuple]:
    """
    Parse one command segment into (head, flags, tail).

    head  — executable + subcommands, i.e. all tokens before the first flag
    flags — frozenset of flag tokens (order-independent)
    tail  — non-flag tokens that appear after the first flag (positional args)

    Handles:
      --flag=value  treated as one flag token
      -f value      -f goes to flags; 'value' goes to tail
      -ti:8080      kept as-is (colon-joined shorthand like lsof uses)
    """
    try:
        tokens = shlex.split(seg)
    except ValueError:
        tokens = seg.split()

    head: list[str] = []
    flags: set[str] = set()
    tail: list[str] = []
    past_first_flag = False

    for t in tokens:
        is_flag = t.startswith('-') and len(t) > 1 and not re.match(r'^-\d', t)
        if is_flag:
            past_first_flag = True
            flags.add(t.lower())
        elif not past_first_flag:
            head.append(t)
        else:
            tail.append(t)

    return tuple(head), frozenset(flags), tuple(tail)


# ── Metric functions ──────────────────────────────────────────────────────────

def exact_match(predicted: str, expected: str) -> bool:
    """Character-perfect match after outer whitespace strip."""
    return _base_clean(predicted) == _base_clean(expected)


def normalized_match(predicted: str, expected: str) -> bool:
    """Lowercase, single-quote, whitespace-collapsed match."""
    return _normalize(predicted) == _normalize(expected)


def structural_match(predicted: str, expected: str) -> bool:
    """
    Flag-order-independent match.

    Rules:
      - Compound commands (&&) must have the same number of segments in the same order.
      - Within each segment: executable + subcommands must match exactly (after normalize),
        flags must match as a SET (order irrelevant), trailing positional args must match
        in order.
      - Quotes normalized (' == ").
    """
    pred_segs = _split_compound(_normalize(predicted))
    exp_segs  = _split_compound(_normalize(expected))

    if len(pred_segs) != len(exp_segs):
        return False

    for ps, es in zip(pred_segs, exp_segs):
        ph, pf, pt = _parse_segment(ps)
        eh, ef, et = _parse_segment(es)
        if ph != eh or pf != ef or pt != et:
            return False

    return True


def token_f1(predicted: str, expected: str) -> float:
    """Token-level F1 for partial credit."""
    pred_tokens = set(_normalize(predicted).split())
    exp_tokens  = set(_normalize(expected).split())
    if not exp_tokens:
        return 0.0
    overlap   = pred_tokens & exp_tokens
    precision = len(overlap) / len(pred_tokens) if pred_tokens else 0.0
    recall    = len(overlap) / len(exp_tokens)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


# ── Multi-answer scoring ──────────────────────────────────────────────────────

def score_prediction(predicted: str, expected: str | list[str]) -> dict:
    """
    Score a prediction against one or more valid expected answers.
    Returns True for a metric if ANY expected answer matches.
    token_f1 is the max across all expected answers.
    """
    if isinstance(expected, str):
        expected = [expected]

    # Filter out empty strings
    expected = [e for e in expected if e and e.strip()]
    if not expected:
        return {"exact_match": False, "normalized_match": False,
                "structural_match": False, "token_f1": 0.0}

    em = any(exact_match(predicted, e)      for e in expected)
    nm = any(normalized_match(predicted, e) for e in expected)
    sm = any(structural_match(predicted, e) for e in expected)
    tf = max(token_f1(predicted, e)         for e in expected)

    return {
        "exact_match":      em,
        "normalized_match": nm,
        "structural_match": sm,
        "token_f1":         round(tf, 3),
    }


# ── Aggregation ───────────────────────────────────────────────────────────────

def aggregate_scores(results: list[dict]) -> dict:
    total = len(results)
    if total == 0:
        return {}

    exact      = sum(1 for r in results if r["scores"]["exact_match"])
    normalized = sum(1 for r in results if r["scores"]["normalized_match"])
    structural = sum(1 for r in results if r["scores"]["structural_match"])
    avg_f1     = sum(r["scores"]["token_f1"] for r in results) / total

    by_category: dict[str, dict] = {}
    for r in results:
        cat = r.get("category", "unknown")
        if cat not in by_category:
            by_category[cat] = {"total": 0, "exact": 0, "normalized": 0,
                                 "structural": 0, "f1_sum": 0.0}
        by_category[cat]["total"]      += 1
        by_category[cat]["exact"]      += int(r["scores"]["exact_match"])
        by_category[cat]["normalized"] += int(r["scores"]["normalized_match"])
        by_category[cat]["structural"] += int(r["scores"]["structural_match"])
        by_category[cat]["f1_sum"]     += r["scores"]["token_f1"]

    category_summary = {}
    for cat, s in by_category.items():
        n = s["total"]
        category_summary[cat] = {
            "exact_match":      round(s["exact"]      / n * 100, 1),
            "normalized_match": round(s["normalized"]  / n * 100, 1),
            "structural_match": round(s["structural"]  / n * 100, 1),
            "avg_token_f1":     round(s["f1_sum"]      / n, 3),
            "count": n,
        }

    return {
        "total_examples":       total,
        "exact_match_pct":      round(exact      / total * 100, 1),
        "normalized_match_pct": round(normalized / total * 100, 1),
        "structural_match_pct": round(structural / total * 100, 1),
        "avg_token_f1":         round(avg_f1, 3),
        "by_category":          category_summary,
    }
