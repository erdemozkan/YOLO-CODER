# unit/missing_dir.py
# Tests: Interceptor #9 — FileNotFoundError: missing parent directory
# Expected fix: mkdir -p unit_test_output/reports

with open("unit_test_output/reports/summary.txt", "w") as f:
    f.write("Test report generated successfully.")

print("Report written.")
