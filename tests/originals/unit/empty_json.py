# unit/empty_json.py
# Tests: Interceptor #5 — JSONDecodeError: empty JSON file
# Setup: create_empty_file:unit_test_empty.json
# Expected fix: write valid JSON into unit_test_empty.json

import json

with open("unit_test_empty.json", "r") as f:
    config = json.load(f)

print("Config loaded:", config)
