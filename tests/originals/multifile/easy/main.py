# main.py — entry point for easy multi-file test
# Imports math_helper and calls safe_divide with zero divisor

from math_helper import safe_divide, double

result = safe_divide(100, 0)
print(f"Result: {result}")
print(f"Doubled: {double(result)}")
