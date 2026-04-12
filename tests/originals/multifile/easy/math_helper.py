# math_helper.py — imported by main.py
# BUG: divides by zero unconditionally when divisor is 0

def safe_divide(a, b):
    return a / b  # BUG: should be: return a / b if b != 0 else 0


def double(x):
    return x * 2
