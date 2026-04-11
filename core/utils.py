import re


def sanitize_output(raw_text: str):
    """
    Cleans the AI output by removing Markdown code blocks and
    common hallucinated prefixes like 'FIX: COMMAND:'.
    """
    # 1. Remove Markdown code blocks (e.g., ```python ... ``` or ```bash ... ```)
    # This regex looks for backticks followed by an optional language identifier
    clean_text = re.sub(r"```[a-z]*\n?", "", raw_text)
    clean_text = clean_text.replace("```", "")

    # 2. List of prefixes to strip
    # We use these because fine-tuned models often keep 'explaining' the fix
    # despite system instructions to be concise.
    prefixes_to_strip = [
        "FIX: COMMAND:",
        "FIX: COMMAND",
        "COMMAND:",
        "FIX:",
        "RESULT:",
        "SUGGESTION:",
    ]

    # 3. Aggressively strip prefixes regardless of case
    temp_text = clean_text.strip()
    for prefix in prefixes_to_strip:
        if temp_text.upper().startswith(prefix):
            # Remove the prefix length and any following whitespace
            temp_text = temp_text[len(prefix) :].lstrip()
            # Stop after the first matching prefix is removed
            break

    return temp_text.strip()


def format_traceback(error_msg: str):
    """
    Optional helper: Truncates long tracebacks to keep the context
    window small for the local model.
    """
    lines = error_msg.splitlines()
    if len(lines) > 20:
        return "\n".join(lines[:10] + ["... [Traceback Truncated] ..."] + lines[-10:])
    return error_msg
