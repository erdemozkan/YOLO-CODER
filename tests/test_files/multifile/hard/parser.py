# parser.py — parses raw input into structured data
# BUG: returns a list instead of a dict — breaks transformer downstream

def parse(raw: str) -> dict:
    parts = raw.strip().split(",")
    return parts  # BUG: should be: return {"items": parts, "count": len(parts)}
