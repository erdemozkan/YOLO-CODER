# unit/missing_json.py
# Tests: Interceptor #4 — FileNotFoundError: missing .json config file
# Expected fix: create unit_test_config.json with valid content

import json

with open("unit_test_config.json", "r") as f:
    config = json.load(f)

print("Config loaded:", config)
