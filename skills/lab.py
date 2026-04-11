import subprocess
import os


def run_in_sandbox(command: str):
    """
    SANDBOX BYPASSED: Executes the command directly in the current working directory.
    This maintains the 'skills' architecture but acts as a native passthrough.
    This feature is for development purposes only. Do not use this feature in production.
    """
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            cwd=os.getcwd(),  # Runs exactly where you type the command
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = process.communicate(timeout=15)
        return process.returncode, stdout, stderr
    except Exception as e:
        return 1, "", f"⚠️ EXECUTION ERROR: {str(e)}"
