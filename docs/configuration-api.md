# Configuration and local API

## Configuration

Start from config/*.yaml.example. Real config/*.yaml, .harness/, .venv/ and workspace output are ignored by Git.

- model.yaml: one connection, id default.
- environment.yaml: models mapping keyed by id and a default_model.
- execution.yaml: workspace, interpreter and limits.

A same-id entry in environment.yaml overrides model.yaml. LLM_ENDPOINT, LLM_MODEL and LLM_API_KEY override corresponding single-model fields. $NAME and ${NAME} resolve credential environment variables; missing variables are explicit errors. Empty api_key means no authentication. --demo explicitly selects the scripted provider.

### Model fields

| Field | Default | Meaning |
| --- | --- | --- |
| provider | openai_compatible | openai_compatible or explicit fake |
| endpoint | empty | Chat Completions endpoint/base URL |
| model | nemotron | Deployment identifier; this is not a guarantee about model size |
| api_key | empty | Literal or environment reference; prefer references |
| temperature | 0.2 | 0–2 |
| timeout | 180 | Total time bound for each request attempt, seconds |
| connect_timeout | 10 | Connection timeout, seconds |
| max_retries | 2 | 0–5, only transient model requests |
| max_tokens | 4096 | Requested maximum output tokens |
| tool_mode | native | native, json or disabled |
| trust_env | true | Honor proxy/certificate environment |
| context_window | null | Optional confirmed model capacity, 1,024–10,000,000 tokens |

Capacity is display metadata. The app cannot enforce the model’s actual tokenizer limit. The local context character guard is separate. Retryable statuses are 408/429/500/502/503/504; backoff is bounded. Tool side effects are never automatically retried by the transport.

### Execution fields

| Field | Default | Meaning |
| --- | --- | --- |
| workspace_root | ./workspace | Workspace relative to app root, or absolute |
| python_executable | empty | Same Python as the server |
| timeout | 120 | Process timeout, seconds |
| max_steps | 24 | Maximum model/tool iterations |
| max_context_chars | 120000 | Serialized request + schemas character guard |
| max_output_chars | 16000 | Bounded process output |
| approval_mode | execution | execution, all or trusted |

execution approves process runs; all additionally approves writes; trusted automatically permits operations. The policy is configured by the user, not Skill text.

To remove a saved model, stop the server, back up environment.yaml, remove its models entry and select a remaining default_model. Remove an obsolete model.yaml fallback too if appropriate, then restart. There is no in-app delete button in this version.

## API conventions

The server binds only to localhost (default port 8765). All /api requests require the process’s X-Harness-Token from the served page and a same-origin request. It is a single-user local API, not an external authenticated service. Responses and pages are not cached.

Errors use {error:{code,message,stage,retryable,...}}. Validation errors never echo the submitted key. Connection errors may add http_status, request_id, checks and suggestions. Busy/conflicting operations use HTTP 409.

### Routes

| Method and route | Purpose |
| --- | --- |
| GET /health | Status and version |
| GET /api/config | Safe configuration; never returns API keys |
| POST /api/models/test | Test unsaved connection; one actual chat request, no persistence |
| POST /api/models/discover | Discover model identifiers via sibling /models |
| POST /api/models | Save/add/update a named model and make it default |
| POST /api/diagnostics/{id} | Chat + synthetic tool round-trip diagnostic |
| GET /api/workspace/tree | Files and root |
| GET /api/workspace/file?path=... | Full UTF-8 document, SHA256, BOM/EOL |
| POST /api/workspace/file | Save {path,content,expected_sha256}; stale hash conflicts |
| POST /api/workspace/open | Persist existing absolute directory {path} |
| GET /api/skills | Registered catalog and warnings |
| GET /api/skills/{id} | Skill instructions and resource names |
| POST /api/skills/refresh | Refresh catalog while idle |
| GET/POST /api/sessions | List/create conversations; create accepts {title} |
| GET /api/sessions/{id} | Messages and runs |
| POST /api/sessions/{id}/runs | Start asynchronous {prompt,model_id}; returns run_id |
| GET /api/runs/{id}?after=N | Status and up to 200 ordered events after sequence N |
| POST /api/runs/{id}/approval | {approval_id,approved} |
| POST /api/runs/{id}/cancel | Stop task and supervised process |

Model input includes id, endpoint, model, auth_mode (none/env/session/saved), api_key_env, session_api_key, tool_mode, temperature, timeout, connect_timeout, max_retries, max_tokens, trust_env and optional context_window. saved reuses the already configured credential for the same id; it is not a new storage mode.

Workspace edits, folder changes, connection changes/tests and Skill refresh are blocked during a running task. Task-local tools are sequential.

## Event and persistence contract

Events include run_started, context_usage, step, model_request, communication, model_retry, model_response, token_usage, reasoning, assistant, tool_requested, approval_required, approval_resolved, tool_started, tool_result, completed, error and cancelled.

Communication phases reflect HTTP transport observations; they do not prove remote compute activity. reasoning carries only endpoint-supplied text. token_usage is the most recent request’s reported usage, not a cumulative sum. Unknown metadata stays unknown.

Session messages store reasoning as private local metadata. It is stripped from subsequent wire messages, as is usage metadata, to preserve Chat Completions compatibility. Reasoning is not used as executable tool input.

SQLite WAL state and pre-edit snapshots live in .harness/. Persisted data may contain user text/source/tool output/reasoning. Events redact known model credentials. Restart marks unfinished tasks interrupted; missing native tool results are repaired with explicit unknown-outcome placeholders before continuation, not replayed.
