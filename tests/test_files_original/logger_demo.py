# logger_demo.py
import os
import time

# Define a directory that probably doesn't exist
folder = "logs"
filename = os.path.join(folder, "system_status.txt")

print(f"📝 Attempting to write system logs to '{filename}'...")

# This will CRASH if the 'logs' folder doesn't exist
with open(filename, "w") as f:
    f.write(f"System Check: OK at {time.ctime()}\n")

print(f"✅ Success! Log saved to {filename}")
