"""
Ollama provider for YOLO-Bench.
Calls any model available via local Ollama instance.
"""

import requests


SYSTEM_PROMPT = (
    "You are a CLI repair tool. Output ONLY a single bare bash command to fix the error. "
    "No explanation. No markdown. No backticks."
)


def predict(error: str, model: str = "yolo-7b",
            host: str = "localhost", port: int = 11434,
            command: str = "", **_kwargs) -> str:
    """
    Send an error message to Ollama and return the predicted fix command.
    Uses the native /api/chat endpoint.
    User message format matches training data: [OS] $ cmd\nError:\n...\nFIX:
    """
    # Aligned with training format
    user_content = (
        f"[Linux] $ {command}\nError:\n{error}\nFIX:" if command
        else f"Error:\n{error}\nFIX:"
    )

    # ── old_working ───────────────────────────────────────────────────────────
    # user_content = f"Command: {command}\nError: {error}" if command else error
    # ── end old_working ───────────────────────────────────────────────────────

    url = f"http://{host}:{port}/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "options": {"temperature": 0.1, "think": False},
        "stream": False,
    }
    try:
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        text = resp.json()["message"]["content"].strip()
        # Strip Qwen3 thinking tags: <think>...</think>
        if "<think>" in text and "</think>" in text:
            text = text[text.rfind("</think>") + len("</think>"):].strip()
        return text
    except Exception as e:
        return f"ERROR: {e}"
