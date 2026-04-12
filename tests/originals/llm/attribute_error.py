# llm/attribute_error.py
# Tests: LLM fallback path — AttributeError: 'NoneType' object has no attribute
# No interceptor covers this. YOLO must consult the model.
# Expected fix: use `or ""` or ternary to guard against None before calling .strip()

def fetch_username():
    return None   # simulates a failed DB lookup

username = fetch_username()
print("Username:", username.strip())
