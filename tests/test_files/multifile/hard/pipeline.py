# pipeline.py — entry point for hard multi-file test
# Error traces through pipeline → transformer → parser
# LLM must understand all 3 files to identify the root cause in parser.py

from transformer import transform

inputs = [
    "apple,banana,cherry",
    "red,green,blue",
    "one,two,three,four",
]

for raw in inputs:
    result = transform(raw)
    print(result)
