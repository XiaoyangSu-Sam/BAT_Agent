# Configuration and local API

## Configuration

Start from config/*.yaml.example. Real config/*.yaml, .harness/, .venv/ and workspace output are ignored by Git.

- model.yaml: one connection, id default.
- environment.yaml: models mapping keyed by id and a default_model.
- execution.yaml: workspace, interpreter and limits.

A same-id entry in environment.yaml overrides model.yaml. LLM_ENDPOINT, LLM_MODEL and LLM_API_KEY override corresponding single-model fields. $NAME and ${NAME} resolve credential environment variables; missing variables are explicit errors. Empty api_key means no authentication. --demo explicitly selects the scripted provider.

For an endpoint that requires no authentication, use `api_key: ""`. Omitting the field, leaving it blank (`api_key:`), or using `api_key: null` has the same effect: no Authorization header is sent. An explicit environment reference still requires a nonempty value; it does not silently fall back to no authentication. A nonempty `LLM_API_KEY` environment variable still overrides the single-model YAML setting.

### Model fields

If a working curl request uses a custom path, select **Exact request URL** on the connection page or set `endpoint_mode: exact` in YAML. This sends the request to the supplied path, preserving its trailing slash and without appending `/v1/chat/completions`. The default `auto` mode retains base-URL expansion for existing connections. Use the exact model identifier from the working request. Custom URLs still need to accept Chat Completions JSON and return its response format. Model discovery is optional; a `/models` route is not guessed for a custom path.

| Field | Default | Meaning |
| --- | --- | --- |
| provider | openai_compatible | openai_compatible or explicit fake |
| endpoint | empty | Chat Completions endpoint/base URL |
| endpoint_mode | auto | auto expands API base URLs; exact preserves the supplied request path |
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
| preserve_tool_reasoning | null | Auto for the canonical Nemotron 3.5 Super VL model ID. Set true or false to override native tool continuation per connection. |

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

The user may allow all execution for one conversation at a pending execution approval. This SQLite-backed override survives reload/restart and is checked before every execution tool. It does not bypass write approvals under all. Revoking restores the project policy for future operations; it does not cancel an already running process. New and other conversations keep their own settings.

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
| POST /api/models/{id}/check | Probe a saved connection with a short chat request using its own settings |
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
| GET/POST /api/sessions | List/create conversations; create accepts {title,approval_mode?} |
| GET /api/sessions/{id} | Messages and runs |
| POST /api/sessions/{id}/approval-mode | Set {approval_mode} for an idle conversation and clear its Allow all grant |
| POST /api/sessions/{id}/runs | Start asynchronous {prompt,model_id}; returns run_id |
| GET /api/runs/{id}?after=N | Status and up to 200 ordered events after sequence N |
| POST /api/runs/{id}/approval | {approval_id,approved,allow_all_execution:false}; true is valid only with approval of a pending execution tool |
| POST /api/sessions/{id}/execution-approval | {allow_all:false}; revokes the conversation override; cannot grant it |
| POST /api/runs/{id}/cancel | Stop task and supervised process |

Model input includes id, endpoint, endpoint_mode (auto/exact), model, auth_mode (none/env/session/saved), api_key_env, session_api_key, tool_mode, temperature, timeout, connect_timeout, max_retries, max_tokens, trust_env, optional context_window and optional preserve_tool_reasoning. The saved auth mode reuses the configured credential for the same id.

The saved-model check reports reply_status as complete or output_truncated. A truncated short probe with evidence of generated tokens establishes reachability. The unsaved connection test requires a complete text response.

Workspace edits, folder changes, connection changes/tests and Skill refresh are blocked during a running task. Task-local tools are sequential.

## Event and persistence contract

Events include run_started, context_usage, step, model_wait_started, model_wait_finished, model_request, communication, model_retry, model_response, token_usage, reasoning, assistant, tool_requested, approval_required, approval_policy_changed, approval_resolved, tool_started, tool_result, completed, error and cancelled. approval_required includes the tool kind. approval_policy_changed records granting the conversation execution override.

Session lists include approval_mode (null means inherit the project default), allow_all_execution (0/1), and updated (latest run creation time or session creation time). Modes are all for Ask for approval, execution for Approval for me, and trusted for Full access. An explicit all selection requires approval for each protected operation. The upgrade adds a nullable approval_mode column and preserves prior conversation grants. Lists are ordered newest first and retain the 200-session limit.

Communication phases reflect HTTP transport observations; they do not prove remote compute activity. reasoning carries only endpoint-supplied text. token_usage is the most recent request’s reported usage, not a cumulative sum. Unknown metadata stays unknown.

model_wait_started includes step and started_at (Unix seconds); model_wait_finished includes step, elapsed_ms (monotonic request duration including retries), and outcome (received/failed/cancelled). Successful replies retain _model_elapsed_ms in local session metadata. Tools and approval waits are outside that measurement.

Session messages store reasoning and model timing as private local metadata. It is stripped from subsequent wire messages, as is usage metadata, to preserve Chat Completions compatibility. Reasoning is not used as executable tool input.

SQLite WAL state and pre-edit snapshots live in .harness/. Persisted data may contain user text/source/tool output/reasoning. Events redact known model credentials. Restart marks unfinished tasks interrupted; missing native tool results are repaired with explicit unknown-outcome placeholders before continuation, not replayed.
