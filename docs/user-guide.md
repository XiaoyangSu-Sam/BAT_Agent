# User guide — BAT Agent 0.5

## Explore before connecting

On the connection page choose **Open workspace without a model**. Files, editing, folder selection and registered Skills are available immediately. The page clearly shows that no model is connected. Connect to chat opens settings later without discarding an unsent prompt. Reload preserves this choice for the current browser session. This is not fake/demo mode and makes no model requests.

## Your workspace

The left explorer lists the active workspace. Open a file to read or edit it in the center. Use the explorer’s New file button for a new path, or Open workspace to select an existing folder by its full path on this computer.

Drag the divider between files and conversation to give chat more room. Drag the vertical divider to widen the sidebar. The Skills icon opens registered Skills on the right.

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

By default, Python/commands/notebooks require approval. Review the actual arguments, then approve or decline. Declining stops the task. File writes use the configured approval policy; the default allows them without a separate approval.

Output shows actual stdout, stderr and exit codes. Changes shows file diffs. Activity shows request phases, tool parameters/results, errors and usage. Export downloads the selected run’s event JSON. It may contain source code, business data and model reasoning.

File path guards are not an operating-system sandbox. Approved programs run with the current user’s permissions. See SECURITY.md for the exact boundaries.
