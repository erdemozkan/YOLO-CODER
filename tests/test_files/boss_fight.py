import os
import subprocess

print("🔥 Welcome to the YOLO Boss Fight 🔥")
print("-----------------------------------\n")

# --- TRAP 1: The Deep Ghost File ---
print("⚔️  Stage 1: The Nested Ghost")
# Throws FileNotFoundError: missing parent directory
with open("archives/2026/classified/ghost.txt", "w") as f:
    f.write("classified data")
print("✅ Stage 1 Clear: Deep nested file written successfully.\n")


# --- TRAP 2: The Titanium Wall ---
print("⚔️  Stage 2: The Titanium Wall")
# We setup a file and make it strictly read-only
if not os.path.exists("titanium.txt"):
    with open("titanium.txt", "w") as f:
        f.write("You cannot change me.")
    os.chmod("titanium.txt", 0o444)

# Throws PermissionError: [Errno 13] Permission denied
with open("titanium.txt", "w") as f:
    f.write("YOLO was here")
print("✅ Stage 2 Clear: Bypassed file permissions.\n")


# --- TRAP 3: The Unworthy Script ---
print("⚔️  Stage 3: The Unworthy Script")
# We create a bash script but intentionally strip its execution rights
if not os.path.exists("engine.sh"):
    with open("engine.sh", "w") as f:
        f.write("#!/bin/bash\necho 'Engine is running!'")
    os.chmod("engine.sh", 0o644)

# Throws PermissionError: [Errno 13] Permission denied: './engine.sh'
subprocess.run(["./engine.sh"], check=True)
print("✅ Stage 3 Clear: Script executed successfully.\n")

print("🎉🎉 BOSS FIGHT COMPLETE! YOLO-CODER IS WORKING! 🎉🎉")
