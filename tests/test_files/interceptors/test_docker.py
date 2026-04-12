"""
Interceptor unit tests — Docker errors (#15, #16, #17, #18)
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

def check(label, error_msg, expected_cmd_fragment):
    result = run_auto_intercept(error_msg, dry_run=True)
    if result is None:
        failures.append(f"{label}: interceptor returned None (no match)")
        print(f"{FAIL}  {label}: no match")
        return
    if expected_cmd_fragment not in result.command:
        failures.append(f"{label}: expected '{expected_cmd_fragment}' in '{result.command}'")
        print(f"{FAIL}  {label}: got '{result.command}'")
        return
    if result.source != "interceptor":
        failures.append(f"{label}: expected source='interceptor', got '{result.source}'")
        print(f"{FAIL}  {label}: source='{result.source}'")
        return
    print(f"{PASS}  {label}: {result.command}")


# --- #15a: Docker image not found (Unable to find image) ---
check(
    "#15a docker image not found",
    "Unable to find image 'alpine:latest' locally\ndocker: Error response from daemon: pull access denied for alpine.",
    "docker pull alpine:latest",
)

# --- #15b: Docker No such image ---
check(
    "#15b docker no such image",
    "docker: Error response from daemon: No such image: myapp:v1.2",
    "docker pull myapp:v1.2",
)

# --- #16: Docker port conflict ---
check(
    "#16 docker port conflict",
    "docker: Error response from daemon: driver failed programming external connectivity on endpoint myapp: "
    "Bind for 0.0.0.0:8080 failed: port is already allocated.",
    "8080",
)

# --- #17: Docker container name collision ---
check(
    "#17 docker container name conflict",
    'docker: Error response from daemon: Conflict. The container name "/myapp" is already in use by container '
    '"abc123def456". You have to remove (or rename) that container to be able to reuse that name.',
    "docker rm -f myapp",
)

# --- #18: Docker daemon not running ---
check(
    "#18 docker daemon not running",
    "Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?",
    "Docker",   # open -a Docker (macOS) or systemctl start docker (Linux)
)


print()
if failures:
    print(f"\033[91m{len(failures)} test(s) failed:\033[0m")
    for f in failures:
        print(f"  • {f}")
    sys.exit(1)
else:
    print(f"\033[92mAll Docker interceptor tests passed.\033[0m")
    sys.exit(0)
