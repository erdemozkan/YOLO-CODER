"""
Interceptor unit tests — Node.js errors (#12, #13, #14)
Runs run_auto_intercept() directly with simulated stderr.
Exits 0 if all pass, 1 if any fail.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from core.interceptors import run_auto_intercept

PASS = "\033[92m✅\033[0m"
FAIL = "\033[91m❌\033[0m"

failures = []

def check(label, error_msg, expected_cmd_fragment, expected_source="interceptor"):
    result = run_auto_intercept(error_msg, dry_run=True)
    if result is None:
        failures.append(f"{label}: interceptor returned None (no match)")
        print(f"{FAIL}  {label}: no match")
        return
    if expected_cmd_fragment not in result.command:
        failures.append(f"{label}: expected '{expected_cmd_fragment}' in '{result.command}'")
        print(f"{FAIL}  {label}: got '{result.command}'")
        return
    if result.source != expected_source:
        failures.append(f"{label}: expected source='{expected_source}', got '{result.source}'")
        print(f"{FAIL}  {label}: source='{result.source}'")
        return
    print(f"{PASS}  {label}: {result.command}")


# --- #12: Cannot find module (local relative path) ---
check(
    "#12a node missing local module",
    "Error: Cannot find module './missing_helper'\n    at Object.<anonymous> (/app/index.js:3:17)",
    "touch",
)

# --- #12b: Cannot find module (npm package) ---
check(
    "#12b node missing npm package",
    "Error: Cannot find module 'express'\n    at Function.Module._resolveFilename (node:internal/modules/cjs/loader:1048:15)",
    "npm install express",
)

# --- #12c: scoped npm package ---
check(
    "#12c node missing scoped package",
    "Error: Cannot find module '@babel/core'\n    at Function.Module._resolveFilename",
    "npm install @babel/core",
)

# --- #13a: npm ERR! ENOENT (node_modules missing) ---
check(
    "#13a npm ENOENT node_modules missing",
    "npm ERR! code ENOENT\nnpm ERR! ENOENT: no such file or directory, open '/app/package.json'\nnpm ERR! ENOENT This is related to npm not being able to find a file.",
    "npm install",
)

# --- #13b: npm ERR! ERESOLVE peer dep conflict ---
check(
    "#13b npm ERESOLVE peer dep conflict",
    "npm ERR! code ERESOLVE\nnpm ERR! ERESOLVE unable to resolve dependency tree\nnpm ERR! While resolving: myapp@1.0.0\nnpm ERR! peer dep issue",
    "--legacy-peer-deps",
)

# --- #14a: TS2304 Cannot find name ---
check(
    "#14a TS2304 cannot find name",
    "src/server.ts(12,18): error TS2304: Cannot find name 'process'.",
    "@types/node",
)

# --- #14b: TS2339 Property does not exist ---
check(
    "#14b TS2339 property missing on type",
    "src/app.ts(5,10): error TS2339: Property 'userId' does not exist on type 'Request'.",
    "TS2339",
)


print()
if failures:
    print(f"\033[91m{len(failures)} test(s) failed:\033[0m")
    for f in failures:
        print(f"  • {f}")
    sys.exit(1)
else:
    print(f"\033[92mAll Node.js interceptor tests passed.\033[0m")
    sys.exit(0)
