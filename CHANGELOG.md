# Changelog

## 0.7.0 — conversation workspace and execution approvals
- Made chat the main surface, with searchable conversation history on the left and an optional right file editor that can close, resize or expand.
- Added Approve once, Allow all for this conversation, and revocation. Conversation permission persists across restarts; other conversations and write approval rules stay separate.
- Added exact request URLs and normalized blank YAML API keys for services without authentication.
- Added an English file-by-file update guide and Copilot prompt, with existing-environment and local-data preservation requirements.
- Updated English documentation and rebuilt the editor's accessible label from source. Runtime dependencies are unchanged.

## 0.6.1 — existing environment updates
- Made checking and reusing an existing approved interpreter the default startup path.
- Added a manual source replacement checklist and updated the Copilot setup guide.
- Documented direct source startup when dependencies are already available, without an install or environment creation step.
- Added upper-version checks so incompatible existing dependencies do not report ready.

## 0.6.0 — installation and replacement
- Added verified source deployment with preview, backup, recovery and optional fresh local configuration.
- Preserved existing repository settings, Skills and workspace data during replacement.
- Added a local prerequisite checker and Copilot environment setup instructions.
- Simplified product documentation and bundled blank connection examples.
- Published a source integrity manifest for release and source ZIPs.

## 0.5.2 — internal preview and model timing
- Simplified the connection screen to BAT Agent, a small version label, basic features and From BAT Team.
- Removed endpoint URL and model-name examples from the connection inputs.
- Added a live model-wait timer and persisted response time for each model call, excluding tools and approval waits.
- Kept timing metadata out of provider messages and handled failure, cancellation and page reload.

## 0.5.1 — workspace access without a model
- Added an explicit entry to browse/edit local files and inspect Skills without model configuration.
- Clearly marked disconnected chat and kept the workspace accessible while connecting.
- Remembered workspace preview across page reloads in the current browser session.

## 0.5.0 — English workbench and model feedback
- English default UI with saved/discovered model dropdowns and optional credentials.
- Actionable connection diagnostics from actual HTTP phases, with cautious VPN/IP guidance.
- Asynchronous conversation, sanitized Markdown, model-provided reasoning toggle and an honest context usage ring.
- Guarded Skill authoring, SHA256 updates and immediate registration.
- Preserved connection settings when editing saved models; no session key persistence.
- Complete user, connection, Skill, API, migration and acceptance guides.

## 0.4.0 — conversational coding workbench
- Replaced the dashboard with file explorer/chat, central CodeMirror editor, optional registered Skills panel, and output/change views.
- Added first-run model connection page with optional API Key and a real Test connection request before entering.
- Added complete file editing, new files, workspace selection, stale-save conflict handling and automatic refresh after agent changes.
- Kept model switching, tool approvals, diagnostics and conversation persistence.
- Bundled editor assets locally and added backend/browser integration checks.

## 0.3.0 — initial release
- Python/FastAPI local UI, packaging with uv and pinned uv.lock.
- OpenAI-compatible Chat Completions with endpoint normalization and optional authentication.
- Explicit native / JSON / chat-only modes and a read-only tool roundtrip diagnostic.
- Sequential agent loop with schema validation, bounded steps/context and typed errors.
- Local file read/search/create/edit, SHA256 conflict handling, diffs and pre-edit snapshots.
- Script, argv command and optional Notebook execution, bounded output, timeouts and cancellation.
- Skill metadata discovery, instruction/resource loading and runtime refresh.
- Per-operation approvals, denial stops, SQLite history and conservative interruption handling.
- Offline scripted model with real local execution.
- Automated tests and browser smoke verification.
