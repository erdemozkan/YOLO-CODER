# llm/index_error.py
# Tests: LLM fallback path — IndexError: list index out of range
# No interceptor covers this. YOLO must consult the model.
# Expected fix: bounds check or correct index.

items = ["apple", "banana"]
print("Third item:", items[1] if len(items) > 1 else None)
