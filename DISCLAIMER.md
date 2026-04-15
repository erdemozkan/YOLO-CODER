# Disclaimer for YOCO (You Only Launch Once Coder)

**YOCO is an experimental, open-source tool provided for free "as-is" without any warranties.**

Because YOCO is designed to automatically diagnose and apply fixes to your code and system configurations, it carries inherent risks. By using this software, you acknowledge and agree to the following terms:

### 1. Risk of Destruction
YOCO can, and occasionally will, modify, delete, or remove files. It may introduce new bugs, cause system crashes, or break existing functionality while attempting to fix an error.

### 2. Experimental Nature
The underlying AI models are probabilistic. They can "hallucinate" or generate commands that are technically valid but contextually destructive. YOCO does not have a "human" understanding of your specific business logic or data importance.

### 3. Recommended Environment
*   **Isolation:** We strongly recommend running YOCO only in **isolated/secure environments** such as Docker containers, sandboxed virtual machines, or temporary cloud instances.
*   **Backups:** Never run YOCO on your only copy of critical data. Always use a dedicated Git branch or work on a copy of your project files so you can easily revert changes if a fix goes wrong.

### 4. No Liability
The authors and contributors of YOCO are not responsible for any data loss, system instability, or "broken production" cases caused by the use of this tool. Use YOCO at your own risk.
