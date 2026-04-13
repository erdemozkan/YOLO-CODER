# unit/type_concat.py
# Tests: Interceptor #2 — TypeError: can only concatenate str (not "int") to str
# Expected fix: wrap error_count with str()

error_count = 5
message = "Total errors: " + str(error_count)
print(message)
