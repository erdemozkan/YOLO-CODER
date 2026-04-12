# llm/division_zero.py
# Tests: LLM fallback path — ZeroDivisionError
# No interceptor covers this. YOLO must consult the model.
# Expected fix: guard divisor against zero.

def calculate(a, b):
    return a / b

result = calculate(100, 0)
print("Result:", result)
