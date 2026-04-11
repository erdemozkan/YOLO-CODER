import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# INVALID COMMAND PHRASES
# Commands that look like output text but are not executable bash.
# Matched case-insensitively against the full stripped command.
# ---------------------------------------------------------------------------
_INVALID_COMMAND_PHRASES = {
    "", "n/a", "none", "unknown", "no fix", "no command", "no solution",
    "i don't know", "i do not know", "not sure", "error", "null",
    "undefined", "not applicable", "cannot fix", "unable to fix",
}

# ---------------------------------------------------------------------------
# EXPLANATION PREFIXES
# Prose prefixes that indicate the model returned an explanation instead of
# a command. Matched case-insensitively against the start of the command.
# ---------------------------------------------------------------------------
_EXPLANATION_PREFIXES = (
    "the ", "to ", "you ", "this ", "it ", "we ", "please ",
    "sorry", "unfortunately", "i ", "based on", "in order to",
    "first ", "then ", "next ", "finally ", "note:", "warning:",
    "you need", "you should", "you can", "you must",
)

# ---------------------------------------------------------------------------
# DANGEROUS DESTRUCTION PATTERNS
# Substrings that indicate irreversible data destruction.
# Matched as substrings (case-sensitive) — intentionally strict.
# ---------------------------------------------------------------------------
_DANGEROUS_DESTRUCTION = (
    "rm -rf /",
    "rm -rf ~/",
    "rm -rf $HOME",
    "rm -rf ${HOME}",
    "rm -rf *",           # wipes entire cwd
    "rm -fr /",
    "rm -fr ~/",
    "rm -rf .",           # wipes cwd
    "rm -fr .",
    "mkfs",               # format filesystem
    "dd if=/dev/zero",    # overwrite disk
    "dd if=/dev/urandom", # overwrite disk with random
    "> /dev/sda",
    "> /dev/disk",
    "shred /dev/",
    "wipefs",
)

# Source files that must never be deleted or overwritten by a fix command.
_PROTECTED_PATH_PREFIXES = (
    "tests/",
    "core/",
    "skills/",
    "yolo.py",
    "yolo_replace.py",
)

# ---------------------------------------------------------------------------
# FORK BOMBS AND RESOURCE EXHAUSTION
# ---------------------------------------------------------------------------
_DANGEROUS_RESOURCE = (
    ":(){:|:&};:",        # classic bash fork bomb
    ":(){ :|:& };:",      # spaced variant
    "while true; do",     # infinite loop (without break)
    "for((;;))",          # C-style infinite loop
)

# ---------------------------------------------------------------------------
# SHELL INJECTION PATTERNS
# Patterns that suggest the model is injecting shell metacharacters or
# trying to chain unintended commands via subshell expansion.
# ---------------------------------------------------------------------------
_SHELL_INJECTION = (
    "`curl",              # backtick + curl = remote code exec
    "`wget",
    "$(curl",             # subshell + curl = remote code exec
    "$(wget",
    "| bash",             # pipe to bash
    "| sh",               # pipe to sh
    "| python -",         # pipe to python stdin
    "| python3 -",
    ";rm ",               # chained rm after another command
    "; rm ",              # chained rm (space after semicolon)
    "&& rm -",            # chained rm after success
    "eval $(",            # eval of subshell output
    "eval `",             # eval of backtick output
)

# ---------------------------------------------------------------------------
# CREDENTIAL AND SECRET EXFILTRATION PATTERNS
# Patterns that suggest sending secrets to remote endpoints.
# ---------------------------------------------------------------------------
_EXFILTRATION = (
    "curl.*password",
    "curl.*secret",
    "curl.*token",
    "curl.*api_key",
    "wget.*password",
    "wget.*secret",
    "id_rsa",             # SSH private key (any access)
    "id_ed25519",         # SSH private key (ed25519)
    ".pem",               # certificate/key file
    "cat /etc/shadow",    # password hash dump
    "cat /etc/passwd",
)

# ---------------------------------------------------------------------------
# PRIVILEGE ESCALATION PATTERNS
# Commands that attempt to gain elevated privileges unexpectedly.
# ---------------------------------------------------------------------------
_PRIVILEGE_ESCALATION = (
    "sudo rm",
    "sudo chmod 777 /",
    "sudo chown root",
    "sudo passwd",
    "sudo visudo",
    "chmod 777 /",
    "chmod 777 ~",
    "chown root /",
    "su -c",
)

# ---------------------------------------------------------------------------
# NETWORK EXFILTRATION (outside of known-safe pip/npm operations)
# Raw curl/wget to arbitrary hosts without a package manager context.
# Note: pip install / npm install are explicitly allowed — they're common
# legitimate fix commands. Only flag bare curl/wget to non-package-registry
# domains that look like data sending (POST, -d, --data).
# ---------------------------------------------------------------------------
_NETWORK_EXFIL = (
    "curl -X POST",
    "curl --data",
    "curl -d ",
    "wget --post-data",
    "wget --post-file",
)


def _contains_any(cmd: str, patterns: tuple) -> bool:
    """Case-insensitive substring check against a tuple of patterns."""
    cmd_lower = cmd.lower()
    return any(p.lower() in cmd_lower for p in patterns)


@dataclass
class FixResult:
    """
    Unified return type for both agent.ask() and run_auto_intercept().
    Replaces the anonymous (summary, plan, command) / (command, summary, plan)
    tuples that previously had inconsistent field ordering across the codebase.
    """
    command: str
    summary: str
    plan: str
    source: str    # "interceptor" | "llm" | "fallback"

    def is_valid(self) -> tuple[bool, str]:
        """
        Returns (is_safe, reason).
        is_safe — True if the command looks executable and non-dangerous.
        reason  — human-readable explanation when is_safe is False.

        Checks in priority order:
          1. Empty / known non-command phrases
          2. Prose explanation prefixes (model returned text, not a command)
          3. Irreversible data destruction
          4. Fork bombs / resource exhaustion
          5. Shell injection patterns
          6. Credential exfiltration
          7. Privilege escalation
          8. Network data exfiltration
        """
        cmd = self.command.strip()

        if cmd.lower() in _INVALID_COMMAND_PHRASES:
            return False, f"Command is empty or a known non-command phrase: '{cmd}'"

        if cmd.lower().startswith(_EXPLANATION_PREFIXES):
            return False, "Command looks like prose explanation, not a bash command."

        if _contains_any(cmd, _DANGEROUS_DESTRUCTION):
            return False, "Command contains a destructive pattern (rm -rf, mkfs, dd)."

        # Block rm on protected source paths
        if re.search(r"\brm\b", cmd):
            for protected in _PROTECTED_PATH_PREFIXES:
                if protected in cmd:
                    return False, f"Command attempts to delete a protected path ({protected})."

        if _contains_any(cmd, _DANGEROUS_RESOURCE):
            return False, "Command contains a resource exhaustion pattern (fork bomb, infinite loop)."

        if _contains_any(cmd, _SHELL_INJECTION):
            return False, "Command contains a shell injection pattern (pipe to bash, eval, subshell curl)."

        if _contains_any(cmd, _EXFILTRATION):
            return False, "Command contains a credential/secret exfiltration pattern."

        if _contains_any(cmd, _PRIVILEGE_ESCALATION):
            return False, "Command contains an unexpected privilege escalation (sudo rm, chmod 777 /)."

        if _contains_any(cmd, _NETWORK_EXFIL):
            return False, "Command contains a suspicious outbound data transfer (POST request)."

        return True, ""

    @classmethod
    def fallback(cls, reason: str = "AI failed to generate a fix command.") -> "FixResult":
        """Convenience constructor for the empty/failed case."""
        return cls(command="", summary="AI Error", plan=reason, source="fallback")
