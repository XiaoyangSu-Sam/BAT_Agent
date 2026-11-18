# Execution boundary
The server binds to 127.0.0.1. API calls require a per-process token; Host and Origin are checked.
Do not expose this server to a network or reverse proxy. This release is a single-user local tool.

File tools check resolved paths, protected directories and links, and use SHA256 to avoid stale overwrites.
These checks are not an OS sandbox. Approved scripts, commands and notebook kernels can access files and networks
available to the current account. Prefer an ordinary user account and a project copy for initial validation.

Default policy asks before every process execution. The trusted mode is an explicit configuration choice.
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
