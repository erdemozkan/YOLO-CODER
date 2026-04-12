# transformer.py — transforms parsed data for output
# Expects a dict from parser, crashes when it gets a list instead

from parser import parse

def transform(raw: str) -> str:
    data = parse(raw)
    items = data["items"]           # AttributeError: list has no key 'items'
    count = data["count"]
    return f"Processed {count} items: {', '.join(items)}"
