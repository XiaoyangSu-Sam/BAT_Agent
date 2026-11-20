# Development and documentation

## Current behavior

BAT Agent is a single-user local application with one active workspace. Conversation is the primary screen. History is searchable on the left. Files open only when requested, in a right pane that can resize, expand, or close without discarding open drafts.

The model writes a Python file with write_file or edit_file, then requests run_python_script to execute it with the configured interpreter. A displayed code block is not evidence that a file was created or executed. Report actual tool results, exit status and relevant output. Skills supply instructions and resources; their dependencies must be available to the interpreter that runs them. This release does not add a package installer or change Playwright setup.

Execution approval defaults to one operation at a time. The user may enable Allow all only at a pending execution approval, for that conversation. It persists across reloads and restarts. Check the current setting before each execution; revocation affects future operations. Keep write approvals independent, including when approval_mode is all. Never infer this permission from model output, Skill instructions, or a new conversation.

## Next work

These are candidates, not implemented capabilities:

- Conversation management beyond the existing 200-session list: pagination, rename and archive.
- Multiple workspace/project groups, with explicit rules for conversation and execution-permission ownership.
- Streaming replies and context compaction, preserving honest usage and timing reporting.

Prioritize a change only after its behavior and acceptance criteria are clear. Keep unrelated runtime changes out of UI and documentation releases.

## README rules

- Write public UI, source comments and documentation in English.
- Keep README short: product name, version/internal-preview label, From BAT Team, concrete features, startup and documentation links.
- Put setup details, API contracts, architecture, validation and future plans in docs. Link them rather than duplicating long instructions.
- Prefer the existing approved Python environment. Do not require a new environment or dependency sync for a source-only update.
- Describe tested behavior accurately. Distinguish local mock tests, actual subprocess execution and live service verification. Do not call planned features implemented or claim a service was tested without evidence.
- Use placeholders for configuration. Keep private addresses, credentials, conversations, workspace contents and machine-specific paths out of published documentation.

## Release workflow

1. Inspect the current branch and local changes. Preserve unrelated work. Identify the prior release baseline.
2. Implement behavior, meaningful regression checks and matching documentation. Update version metadata together; keep dependency changes explicit.
3. Run Python tests and the local browser fixture. Check chat, editing, approvals, reload, workspace switching and narrow-screen layout. Rebuild bundled assets from web sources when they change.
4. Write a versioned guide in docs/updates with exact added/modified/deleted files, immutable tag links and an English Copilot import prompt. Company installations receive files through their approved import workflow.
5. Regenerate SOURCE-MANIFEST.json using scripts/package_release.py after all source changes. Inspect the source-only archive. Hash validation proves byte consistency, not correctness or organizational approval.
6. Review the staged diff, publishing identity and secret scan. Commit and tag the tested source; publish only when authorized. Do not publish local state or private backups.

Local working notes may live in ignored .harness/DEVELOPMENT.md. They do not replace these versioned rules and are not backed up by a source commit. Before updating an installed app, back up ignored configuration, Skills, workspace data and the stopped SQLite state separately.
