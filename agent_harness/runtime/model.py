import asyncio
import json
import random
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import httpx
from ..errors import HarnessError, redact
from ..connection_help import network_error, status_error, trace_observation

def retry_delay(value, attempt):
    try:
        delay = float(value)
    except (ValueError, TypeError):
        try:
            delay = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
        except (ValueError, TypeError, OverflowError):
            delay = 2 ** attempt + random.random() * 0.25
    return min(30, max(0, delay))

def validate_reply(data):
    try:
        choices = data["choices"]
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ValueError("choices")
        choice = choices[0]
        finish = choice.get("finish_reason")
        if finish == "content_filter":
            raise HarnessError("model_refusal", "The provider filtered this response.", "model")
        message = choice["message"]
        if not isinstance(message, dict) or message.get("role", "assistant") != "assistant":
            raise ValueError("assistant message")
        if message.get("refusal"):
            raise HarnessError("model_refusal", "The provider declined this response.", "model")
        content = message.get("content")
        if content is not None and not isinstance(content, str):
            raise ValueError("content type")
        reasoning = next((message[k] for k in ("reasoning_content", "reasoning")
                          if isinstance(message.get(k), str) and message[k]), None)
        usage = data.get("usage")
        clean_usage = {k: usage[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens")
                       if isinstance(usage, dict) and type(usage.get(k)) is int and usage[k] >= 0}
        calls = message.get("tool_calls")
        if calls is None:
            calls = []
        if not isinstance(calls, list) or len(calls) > 16:
            raise ValueError("tool call list")
        if finish == "length":
            raise HarnessError(
                "output_truncated",
                "The model reached its output token limit before finishing. Reasoning can use this budget.",
                "model", generated_output=not calls and bool(content or reasoning or clean_usage.get("completion_tokens")),
                suggestions=["Increase Max output tokens in model settings, or try a smaller task."])
        if finish == "tool_calls" and not calls:
            raise ValueError("missing tool calls")
        ids = set()
        normalized_calls = []
        for call in calls:
            if not isinstance(call, dict) or not isinstance(call.get("function"), dict):
                raise ValueError("tool call object")
            ident = call["id"]
            f = call["function"]
            if (call.get("type") != "function" or not isinstance(ident, str) or not ident
                    or ident in ids or not isinstance(f["name"], str) or not f["name"]
                    or not isinstance(f["arguments"], str) or not isinstance(json.loads(f["arguments"]), dict)):
                raise ValueError("tool call structure")
            ids.add(ident)
            normalized_calls.append({"id": ident, "type": "function",
                                     "function": {"name": f["name"], "arguments": f["arguments"]}})
        if not calls and not (content and content.strip()):
            raise ValueError("empty response")
        result = {"role": "assistant", "content": content}
        if calls:
            result["tool_calls"] = normalized_calls
        if reasoning:
            result["_reasoning"] = reasoning[:100000]
        if clean_usage:
            result["_usage"] = clean_usage
        return result
    except HarnessError:
        raise
    except (KeyError, IndexError, TypeError, ValueError, RecursionError) as exc:
        raise HarnessError("invalid_model_response", "The endpoint returned an invalid Chat Completions response.", "model") from exc

class ModelClient:
    def __init__(self, config, transport=None):
        self.config, self.transport = config, transport

    async def complete(self, messages, schemas, emit, tools=True):
        c = self.config
        if c.provider == "fake":
            from .fake import reply
            return reply(messages, tools)
        secret = c.secret()
        body = {"model": c.model, "messages": [{k:v for k,v in m.items() if not k.startswith("_")} for m in messages], "temperature": c.temperature,
                "max_tokens": c.max_tokens, "stream": False}
        if tools and schemas and c.tool_mode == "native":
            body.update(tools=schemas, tool_choice="auto")
        headers = {"Accept": "application/json"}
        if secret:
            headers["Authorization"] = "Bearer " + secret
        timeout = httpx.Timeout(c.timeout, connect=c.connect_timeout)
        observations = []
        async def trace(name, info):
            observation = trace_observation(name)
            if observation:
                observations.append(observation)
                await emit("communication", observation)
        async with httpx.AsyncClient(timeout=timeout, trust_env=c.trust_env,
                                     transport=self.transport, follow_redirects=False) as client:
            for attempt in range(c.max_retries + 1):
                observations.clear()
                started = time.monotonic()
                delay_header = None
                try:
                    await emit("model_request", {"attempt": attempt + 1, "model": c.model})
                    async with asyncio.timeout(c.timeout):
                        async with client.stream("POST", c.url(), json=body, headers=headers,
                                                 extensions={"trace": trace}) as response:
                            status = response.status_code
                            if status >= 300:
                                delay_header = response.headers.get("Retry-After")
                                raise status_error(response)
                            content_type = response.headers.get("Content-Type", "").partition(";")[0].strip().lower()
                            if content_type == "text/event-stream":
                                raise HarnessError("unexpected_stream",
                                    "The endpoint returned an event stream for a non-streaming request.",
                                    "response", suggestions=["Check that the endpoint or gateway honors stream: false."])
                            await response.aread()
                    result = validate_reply(response.json())
                    if result.get("_reasoning"):
                        result["_reasoning"] = redact(result["_reasoning"], [secret])
                    receipt = {"elapsed_ms": round((time.monotonic()-started)*1000),
                               "http_status": status, "tool_calls": len(result.get("tool_calls", []))}
                    if request_id := response.headers.get("x-request-id"):
                        receipt["request_id"] = redact(request_id[:120], [secret])
                    await emit("model_response", receipt)
                    return result
                except HarnessError as exc:
                    error = exc
                except (httpx.RequestError, TimeoutError) as exc:
                    error = network_error(exc)
                except (ValueError, UnicodeError, RecursionError):
                    error = HarnessError("invalid_json_response", "Endpoint returned non-JSON data.", "model")
                error.details["checks"] = observations[-12:]
                if "request_id" in error.details:
                    error.details["request_id"] = redact(error.details["request_id"], [secret])
                if not error.retryable or attempt >= c.max_retries:
                    raise error
                delay = retry_delay(delay_header, attempt)
                await emit("model_retry", {"delay_seconds": delay, "error": error.as_dict()})
                await asyncio.sleep(delay)
