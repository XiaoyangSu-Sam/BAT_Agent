import asyncio
import json
import time
from .context import system_prompt, wire_messages, json_action
from .model import ModelClient
from ..errors import HarnessError

async def run_turn(run_id, session_id, messages, config, tools, skills, execution,
                   store, emit, approve, model_factory=ModelClient, execution_allowed=None):
    seen = set()
    client = model_factory(config)
    schemas = tools.schemas()
    for step in range(execution.max_steps):
        wire = [{"role":"system","content":system_prompt(skills, config.tool_mode)},
                *wire_messages(messages, config.tool_mode)]
        if config.tool_mode == "json":
            wire[0]["content"] += "\nTools:\n" + json.dumps(schemas)
        chars = len(json.dumps(wire)) + len(json.dumps(schemas))
        await emit("context_usage", {"model":config.model, "model_context_window":config.context_window,
                   "characters":chars, "character_limit":execution.max_context_chars})
        if chars > execution.max_context_chars:
            raise HarnessError("context_limit", "Context limit reached. Start a fresh session with a focused task.", "context")
        await emit("step", {"number":step+1, "limit":execution.max_steps})
        started = time.monotonic()
        outcome = "failed"
        await emit("model_wait_started", {"step":step+1, "started_at":time.time()})
        try:
            reply = await client.complete(wire, schemas, emit, tools=config.tool_mode!="disabled")
            outcome = "received"
        except asyncio.CancelledError:
            outcome = "cancelled"
            raise
        finally:
            elapsed_ms = max(0, round((time.monotonic()-started)*1000))
            await emit("model_wait_finished", {"step":step+1, "elapsed_ms":elapsed_ms, "outcome":outcome})
        if reply.get("_usage"):
            await emit("token_usage", {"model":config.model, "model_context_window":config.context_window, **reply["_usage"]})
        reasoning = reply.get("_reasoning")
        await emit("reasoning", {"content":reasoning, "available":bool(reasoning)})
        calls = reply.get("tool_calls", [])
        text = reply.get("content")
        if config.tool_mode == "json":
            text, calls = json_action(reply)
            reply = {"role":"assistant","content":text, "_reasoning":reasoning}
            if calls:
                reply["tool_calls"] = calls
        if config.tool_mode == "disabled" and calls:
            raise HarnessError("tools_disabled", "Provider returned tools while chat-only mode is enabled.", "model")
        # Local display metadata; wire_messages removes it from subsequent requests.
        reply["_model_elapsed_ms"] = elapsed_ms
        for call in calls:
            if call["id"] in seen:
                raise HarnessError("duplicate_tool_call", "Provider reused a tool call id; execution stopped to avoid replay.", "model")
            seen.add(call["id"])
        messages.append(reply)
        store.save_messages(session_id, messages)
        if text:
            await emit("assistant", {"content":text})
        if not calls:
            return
        for call in calls:
            name = call["function"]["name"]
            raw = call["function"]["arguments"]
            args = None
            try:
                try:
                    args = json.loads(raw)
                except (ValueError, TypeError) as exc:
                    raise HarnessError("invalid_tool_arguments", "Tool arguments are not valid JSON.", "tool") from exc
                entry = tools.validate(name, args)
                await emit("tool_requested", {"call_id":call["id"],"name":name,"arguments":args})
                kind = entry["kind"]
                needs = execution.approval_mode == "all" and kind != "read"
                needs |= execution.approval_mode == "execution" and kind == "execute"
                if kind == "execute" and execution_allowed is not None and execution_allowed():
                    needs = False
                if needs and not await approve(call["id"], name, args):
                    raise HarnessError("approval_denied", "The user declined this operation. Do not retry it without new authorization.", "tool")
                # Persist the start event before touching the filesystem/process.
                await emit("tool_started", {"call_id":call["id"],"name":name})
                result = await tools.call(name, args)
                output = {"ok":True,"result":result}
            except HarnessError as exc:
                output = {"ok":False,"error":exc.as_dict()}
            except (OSError, ValueError, TypeError):
                output = {"ok":False,"error":{"code":"tool_failed","stage":"tool",
                    "message":"Local operation failed. Check paths, permissions and arguments.","retryable":False}}
            messages.append({"role":"tool","tool_call_id":call["id"],
                             "content":json.dumps(output, ensure_ascii=False)})
            store.save_messages(session_id, messages)
            await emit("tool_result", {"call_id":call["id"],"name":name,**output})
            if not output["ok"] and output["error"]["code"] == "approval_denied":
                # A denial stops the run so the model cannot route around it using a different tool.
                raise HarnessError("approval_denied", "Operation declined; run stopped.", "approval")
    raise HarnessError("step_limit", "Maximum model steps reached. Review results before continuing.", "runtime")
