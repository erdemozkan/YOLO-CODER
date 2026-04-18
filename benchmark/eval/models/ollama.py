"""
Ollama provider for YOLO-Bench.
Calls any model available via local Ollama instance.
"""

import requests


SYSTEM_PROMPT = (
    "You are a CLI repair tool. Output ONLY a single bare bash command to fix the error. "
    "No explanation. No markdown. No backticks. Just the command."
)


def predict(error: str, model: str = "yolo-7b",
            host: str = "localhost", port: int = 11434) -> str:
    """
    Send an error message to Ollama and return the predicted fix command.
    Uses the native /api/chat endpoint.
    """
    url = f"http://{host}:{port}/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": error},
        ],
        "options": {"temperature": 0.1},
        "stream": False,
    }
    try:
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except Exception as e:
        return f"ERROR: {e}"
