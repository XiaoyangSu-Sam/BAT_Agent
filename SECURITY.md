# Execution boundary
The server binds to 127.0.0.1. API calls require a per-process token; Host and Origin are checked.
Do not expose this server to a network or reverse proxy. This release is a single-user local tool.

File tools check resolved paths, protected directories and links, and use SHA256 to avoid stale overwrites.
These checks are not an OS sandbox. Approved scripts, commands and notebook kernels can access files and networks
available to the current account. Prefer an ordinary user account and a project copy for initial validation.

The project defaults to approval before every process execution. The footer lets the user set a policy for a
single conversation. Ask for approval prompts for file writes and execution. Approval for me permits agent file
edits and prompts before execution. Full access permits both and retains the usual tool and path rules.

An eligible execution approval can grant Allow all for the conversation, including later tasks and server
restarts. The sidebar can revoke it for later operations. Use Stop to cancel a running task. Changing the
conversation policy clears its grant. An explicit Ask for approval policy always prompts for protected tools.
Skill text and model output cannot change the policy. Rejected approvals stop the run.

API keys entered for a session remain in memory. Saved configuration stores only environment-variable references.
Model request headers are not logged. Known model credentials are redacted from run events and common credential
environment variables are omitted from child environments. This is not comprehensive data-loss prevention:
source text, user messages and tool output can contain other sensitive content and are persisted locally.

Stop/timeout attempts to terminate the current process tree. It is not a security boundary against processes
that deliberately detach or escape process supervision. Existing edits and script side effects are retained.
Backup JSON records support manual inspection; no automatic workspace rollback is provided.

There are no telemetry calls, external frontend CDNs, or hardcoded company URLs. Installing dependencies uses
your configured package source. Model requests go to the endpoint configured by the user.

## Publishing source

Keep real endpoints, model credentials, private Skills, workspace contents and conversation history local.
The ignore rules exclude local model YAML, environment files, common key files, logs, databases and Git bundles.
Examples must contain placeholders only. Ignore rules do not remove files already tracked by Git.

Before publishing, review staged files and Git author/committer identity, and scan the full history with a secret scanner.
Use a publishing identity and a no-reply email if you do not want personal details in public commits.
The release packaging script includes source and example configuration only; inspect any added source or documentation
for private values before packaging. Store audit reports and recovery backups outside the public repository.
