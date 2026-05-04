"""
OpenAI provider for YOLO-Bench (GPT-4o, GPT-4-turbo, etc).
Requires OPENAI_API_KEY in environment.
"""

import os
from openai import OpenAI


SYSTEM_PROMPT = (
    "You are a CLI repair tool. Output ONLY a single bare bash command to fix the error. "
    "No explanation. No markdown. No backticks. Just the command."
)


def predict(error: str, model: str = "gpt-4o",
            command: str = "", **_kwargs) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    user_content = (
        f"[Linux] $ {command}\nError:\n{error}\nFIX:" if command
        else f"Error:\n{error}\nFIX:"
    )

    client = OpenAI(api_key=api_key)
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.1,
            max_tokens=128,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"ERROR: {e}"
