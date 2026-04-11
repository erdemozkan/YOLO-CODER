# unit/name_error.py
# Tests: Interceptor #3 — NameError: name 'undefined_result' is not defined
# Expected fix: initialise undefined_result before use

result = undefined_result * 2
print("Result:", result)
