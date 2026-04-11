import sys
import os

def replace_line(filepath, line_number, new_text):
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
            
        line_idx = int(line_number) - 1
        if line_idx < 0 or line_idx >= len(lines):
            print(f"Error: Line number {line_number} is out of bounds for {filepath}")
            sys.exit(1)
            
        # Handle AI "COLON" shortcut heuristic
        if new_text.strip() == "COLON":
            original_line = lines[line_idx].rstrip('\n')
            # Calculate whitespace indent of original line
            indent = len(original_line) - len(original_line.lstrip())
            
            # Append colon and the correctly indented pass block
            new_text = original_line + ":\n" + (" " * (indent + 4)) + "pass\n"
        else:
            # Optional: handle literal \n conversions from the CLI arguments
            new_text = new_text.replace('\\n', '\n')
            
            # Ensure it ends with a newline
            if not new_text.endswith('\n'):
                new_text += '\n'

        lines[line_idx] = new_text
        
        with open(filepath, 'w') as f:
            f.writelines(lines)
            
        print(f"Successfully modified line {line_number} in {filepath}")
        sys.exit(0)
    except Exception as e:
        print(f"Error modifying file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 yolo_replace.py <filepath> <line_number> <new_string>")
        sys.exit(1)
        
    replace_line(sys.argv[1], sys.argv[2], sys.argv[3])
