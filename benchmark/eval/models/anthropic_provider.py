"""
Anthropic provider for YOLO-Bench (Claude 3.5 Sonnet, etc).
Requires ANTHROPIC_API_KEY in environment.
"""

import os
import anthropic


SYSTEM_PROMPT = (
    "You are a CLI repair tool. Output ONLY a single bare bash command to fix the error. "
    "No explanation. No markdown. No backticks. Just the command."
)


def predict(error: str, model: str = "claude-sonnet-4-6") -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=128,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": error}],
        )
        return resp.content[0].text.strip()
    except Exception as e:
        return f"ERROR: {e}"
