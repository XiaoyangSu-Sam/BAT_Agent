# Development and documentation

## Current behavior

BAT Agent is a single-user local application with one active workspace. Conversation is the primary screen. History is searchable on the left. Files open only when requested, in a right pane that can resize, expand, or close without discarding open drafts.

The model writes a Python file with write_file or edit_file, then requests run_python_script to execute it with the configured interpreter. A displayed code block is not evidence that a file was created or executed. Report actual tool results, exit status and relevant output. Skills supply instructions and resources; their dependencies must be available to the interpreter that runs them. This release does not add a package installer or change Playwright setup.

New conversations inherit the project approval policy. An explicit selection applies only to that conversation and clears its earlier Allow all grant. A pending execution approval can grant Allow all when the policy permits it. The grant persists across reloads and restarts. Keep approval decisions in the runtime and outside model output or Skill instructions.

## Next work

1. **Plan Mode next.** Ordinary chat already asks the model to identify the goal, constraints and success checks for multi-step work. Add an explicit mode that exposes only read tools. Return a short plan with decisions, open questions and acceptance criteria. A user action switches from planning to execution, where the selected approval policy applies. Test the restriction at the runtime boundary for both native and JSON tools.
2. **Conversation compaction after that.** Start with compaction on demand within one conversation. Preserve the original transcript, retain recent complete turns and tool call/result pairs, and summarize decisions, constraints, changed files, test evidence and open work. Define and test when an automatic threshold should offer compaction. Store the summary with provenance and support rebuilding it from the transcript. Keep permission state and secrets outside the summary. Measure long-chat recovery and token use before enabling automation.

Compaction keeps an individual conversation useful as it grows. Cross-conversation memory is a separate feature with its own scope and controls.

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
