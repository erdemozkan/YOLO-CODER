import os
from core.snapshot import take_snapshot

def replace_line(filepath: str, line_number: int, new_text: str):
    """
    Skill: Replaces a specific line in a file.
    Includes the 'COLON' heuristic for AI shortcuts.
    """
    try:
        if not os.path.exists(filepath):
            return f"❌ Error: File {filepath} not found."

        with open(filepath, 'r') as f:
            lines = f.readlines()

        line_idx = int(line_number) - 1
        if line_idx < 0 or line_idx >= len(lines):
            return f"❌ Error: Line number {line_number} is out of bounds (1-{len(lines)})."

        # Handle AI "COLON" shortcut heuristic
        if new_text.strip() == "COLON":
            original_line = lines[line_idx].rstrip('\n')
            # Calculate whitespace indent of original line
            indent = len(original_line) - len(original_line.lstrip())
            
            # Append colon and the correctly indented pass block
            new_text = original_line + ":\n" + (" " * (indent + 4)) + "pass\n"
        else:
            # Handle literal \n conversions from LLM output
            new_text = new_text.replace('\\n', '\n')
            
            # Ensure it ends with a newline
            if not new_text.endswith('\n'):
                new_text += '\n'

        take_snapshot(filepath)
        lines[line_idx] = new_text

        with open(filepath, 'w') as f:
            f.writelines(lines)
            
        return f"✅ Success: Modified line {line_number} in {filepath}"
    except Exception as e:
        return f"⚠️ Error modifying file: {str(e)}"
