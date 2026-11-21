import json
import secrets
from .runtime.model import ModelClient
from .runtime.context import json_action, wire_messages
from .errors import HarnessError

async def diagnose(config, model_factory=ModelClient):
    events = []
    async def emit(kind, data):
        events.append({"type":kind,"data":data})
    client = model_factory(config)
    if config.provider == "fake":
        return {"mode":"offline", "chat":"demo_only", "tools":"demo_only",
                "message":"Offline scripted provider. Real endpoint has not been tested.", "events":[]}
    greeting = await client.complete([{"role":"user","content":"Reply with OK."}], [], emit, tools=False)
    if not greeting.get("content") or greeting.get("tool_calls"):
        raise HarnessError("invalid_model_response", "The chat probe did not return a text answer.", "model")
    report = {"chat":"passed","tools":"not_tested","events":events}
    if config.tool_mode == "disabled":
        report["tools"] = "disabled"
        return report
    nonce = secrets.token_hex(8)
    schema = [{"type":"function","function":{"name":"echo_probe","description":"Echo a diagnostic string.",
        "parameters":{"type":"object","properties":{"value":{"type":"string"}},
                      "required":["value"],"additionalProperties":False}}}]
    prompt = ("Call echo_probe with value " + nonce
              + ". Then report the result field returned by the tool. Do not answer directly.")
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
    # The second nonce appears only in the tool result, so an echo of the user's
    # prompt cannot make a broken round trip pass.
    result_nonce = secrets.token_hex(8)
    tool_result = json.dumps({"result": result_nonce})
    messages.append(first)
    if config.tool_mode == "json":
        messages.append({"role":"user","content":"TOOL_RESULT "+tool_result})
        outgoing = messages
    else:
        messages.append({"role":"tool","tool_call_id":call["id"],"content":tool_result})
        outgoing = wire_messages(messages, "native", continue_tool_reasoning=config.continues_tool_reasoning())
    second = await client.complete(outgoing, schema, emit)
    if config.tool_mode == "json":
        text, repeated_calls = json_action(second)
    else:
        text, repeated_calls = second.get("content"), second.get("tool_calls")
    report["tools"] = "passed" if not repeated_calls and result_nonce in (text or "") else "result_not_confirmed"
    report["message"] = "Synthetic echo probe only; no files or commands were executed."
    return report
