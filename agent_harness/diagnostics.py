import json
import secrets
from .runtime.model import ModelClient
from .runtime.context import json_action
from .errors import HarnessError

async def diagnose(config, model_factory=ModelClient):
    events = []
    async def emit(kind, data):
        events.append({"type":kind,"data":data})
    client = model_factory(config)
    if config.provider == "fake":
        return {"mode":"offline", "chat":"demo_only", "tools":"demo_only",
                "message":"Offline scripted provider. Real endpoint has not been tested.", "events":[]}
    await client.complete([{"role":"user","content":"Reply with OK."}], [], emit, tools=False)
    report = {"chat":"passed","tools":"not_tested","events":events}
    if config.tool_mode == "disabled":
        report["tools"] = "disabled"
        return report
    nonce = secrets.token_hex(8)
    schema = [{"type":"function","function":{"name":"echo_probe","description":"Echo a diagnostic string.",
        "parameters":{"type":"object","properties":{"value":{"type":"string"}},
                      "required":["value"],"additionalProperties":False}}}]
    prompt = "Call echo_probe with value " + nonce + ". Do not answer directly."
    messages = [{"role":"user","content":prompt}]
    if config.tool_mode == "json":
        messages.insert(0, {"role":"system","content":'Return one JSON object: {"action":"tool","name":"echo_probe","arguments":{"value":"..."}}. After TOOL_RESULT, return {"action":"final","content":"the echoed value"}.'})
    first = await client.complete(messages, schema, emit)
    if config.tool_mode == "json":
        _, calls = json_action(first)
    else:
        calls = first.get("tool_calls", [])
    if len(calls) != 1:
        report["tools"] = "not_observed"
        report["message"] = "Chat works but exactly one tool call was not observed. Check provider tool parser or explicit JSON mode."
        return report
    call = calls[0]
    try:
        args = json.loads(call["function"]["arguments"])
    except ValueError:
        args = None
    if call["function"]["name"] != "echo_probe" or args != {"value":nonce}:
        report["tools"] = "invalid_arguments"
        return report
    messages.append(first)
    if config.tool_mode == "json":
        messages.append({"role":"user","content":"TOOL_RESULT "+json.dumps(args)})
    else:
        messages.append({"role":"tool","tool_call_id":call["id"],"content":json.dumps(args)})
    second = await client.complete(messages, schema, emit)
    report["tools"] = "passed" if nonce in (second.get("content") or "") else "result_not_confirmed"
    report["message"] = "Synthetic echo probe only; no files or commands were executed."
    return report
