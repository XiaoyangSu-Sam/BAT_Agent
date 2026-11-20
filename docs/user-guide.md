# User guide — BAT Agent 0.5

## Explore before connecting

On the connection page choose **Open workspace without a model**. Files, editing, folder selection and registered Skills are available immediately. The page clearly shows that no model is connected. Connect to chat opens settings later without discarding an unsent prompt. Reload preserves this choice for the current browser session. This is not fake/demo mode and makes no model requests.

## Your workspace

The left sidebar shows the current workspace and searchable conversation history. Chat uses the main area. The top-left menu toggles the sidebar. Change folder opens an existing workspace by its full path; this is a single active workspace, not a multi-project manager.

Click Files to open the right coding pane. Choose a file from its explorer or use New file. Drag the divider to resize the pane, use Expand to give it the full main area, and Split view to return. Close coding space hides the pane completely and keeps unsaved drafts in memory. Reloading the page does not preserve unsaved drafts. Tool reads and newly created files do not automatically open the editor or interrupt chat. On a narrow screen, the coding pane covers the main area until closed.

Skills opens registered Skills in a side panel. Activity and output below chat is collapsed by default; expand it for results, changes and events.

The editor supports tabs, syntax highlighting, line numbers, folding, search, undo and Ctrl+S. A dot means unsaved changes. Files must be UTF-8 text and at most 1 MB. Binary/protected files are rejected. If the file changed on disk, the app preserves your draft and reports a conflict. Reload from disk explicitly discards that draft after confirmation.

## Conversation

Type a question or task, then Send or Ctrl+Enter. Examples:

- Explain the current project before changing it.
- Read the current file, fix the bug and run the relevant checks.
- Create a reusable Skill with a Python script that processes this input.

Current file adds the file path as context; the agent reads it when needed. Adding a Skill tells the agent to read its instructions. Neither action silently executes a script.

Save unsaved editor changes before starting an agent task. While a task is running the editor is read-only. Only one task can use the workspace at a time. Stop cancels the task and attempts to terminate its subprocess tree; file changes already made remain.

Use the model dropdown for a saved, usable connection. Use New conversation to start with fresh context. History is local and survives page reload and server restart. An interrupted task is marked interrupted on restart, never automatically replayed.

## Responses and model reasoning

Answers use paragraphs, headings, lists, tables and code blocks. Copy copies a code block as text; it does not run the code. HTML is sanitized, remote images are not loaded, and links are limited to HTTP(S) and mailto.

Show model reasoning is a display preference. It reveals a collapsible panel only when the endpoint returns a separate reasoning_content or reasoning string. It does not enable hidden server features, request private thoughts or invent a trace. If the endpoint omits this information, the app says so. Reasoning is stored locally with the conversation and can be present in exported activity.

This release sends asynchronous tasks and polls ordered events approximately every 700 ms. You can use the page while waiting. Each complete model reply is displayed after it arrives; there is no token streaming. Reasoning likewise appears after the complete reply.

Each model call shows **Thinking · seconds** while pending and **Model time · seconds** when the reply arrives. The saved time remains after reload. This is measured request time, including network, service queue/generation and retries; tools and approval waits are excluded. The service does not report its internal reasoning time separately. Failed or stopped requests are labelled accordingly. Older conversations without recorded timing do not receive invented values.

## Communication status

- Sending: submitting a request to the model.
- Request sent; waiting for the server: the request body was sent. This does not prove the model is actively generating; the service may queue or load a model.
- Response headers/body received: data arrived from the service.
- A named tool: reading, writing or running a local operation.
- Waiting for your approval: no protected operation starts until you approve.
- Ready / Failed / Stopped: the current task’s outcome.

Fast transitions may appear together in one polling batch. Activity retains their ordered record. There is no permanent background connection monitor.

## Context circle

Click the circle near the composer for details.

When the endpoint reports input and output token usage and the model’s context capacity is known, the ring shows the last request’s input + output divided by capacity. Capacity comes from a confirmed setting or supported model-list metadata. This is not cumulative cost or billing usage.

When either value is unavailable the circle shows a dash. The details may still show reported input tokens and the separate local character guard. Characters are not model tokens. Capacity differs across deployments even when they share a model alias; do not guess it.

At 80% and above the circle changes color. Starting a new conversation reduces carried history. This release does not automatically summarize or compact context. A configured local input limit stops an oversized task with an explicit error.

## Approvals, output and history

By default, Python/commands/notebooks require approval. Review the actual arguments, then choose Approve once, Decline, or Allow all for this conversation. Declining stops the task. Allow all accepts this execution and subsequent execution tools in the same conversation, including later tasks and after page reload or server restart. It does not change other conversations or bypass file-write approvals under the all policy.

The sidebar shows when execution is allowed. Require approval again restores the project's configured policy for subsequent operations; it does not stop a process already running. Use Stop for the current task. A project configured as trusted still permits execution automatically after a conversation override is cleared. New conversations inherit the project policy and have no Allow all override.

Expand Activity and output to see actual stdout, stderr and exit codes. Changes shows file diffs. Activity shows request phases, tool parameters/results, errors and usage. Export downloads the selected run’s event JSON. It may contain source code, business data and model reasoning.

File path guards are not an operating-system sandbox. Approved programs run with the current user’s permissions. See SECURITY.md for the exact boundaries.
