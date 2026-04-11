# llm/key_error.py
# Tests: LLM fallback path — KeyError: missing dict key
# No interceptor covers this. YOLO must consult the model.
# Expected fix: use .get() or add the missing key.

config = {"host": "localhost", "timeout": 30}
print("Port:", config["port"])
