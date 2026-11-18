import asyncio
import json
import random
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import httpx
from ..errors import HarnessError

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
        choice = data["choices"][0]
        if choice.get("finish_reason") == "length":
            raise HarnessError("output_truncated", "Model output reached max_tokens; no incomplete tools were executed.", "model")
        if choice.get("finish_reason") == "content_filter":
            raise HarnessError("model_refusal", "The provider filtered this response.", "model")
        message = choice["message"]
        content = message.get("content")
        calls = message.get("tool_calls") or []
        if content is not None and not isinstance(content, str):
            raise ValueError("content type")
        if not isinstance(calls, list) or len(calls) > 16:
            raise ValueError("tool call list")
        ids = set()
        for call in calls:
            ident = call["id"]
            f = call["function"]
            if (call.get("type") != "function" or not isinstance(ident, str) or not ident
                    or ident in ids or not isinstance(f["name"], str)
                    or not isinstance(f["arguments"], str)):
                raise ValueError("tool call structure")
            ids.add(ident)
        if not calls and not content:
            raise ValueError("empty response")
        result = {"role": "assistant", "content": content}
        if calls:
            result["tool_calls"] = calls
        return result
    except HarnessError:
        raise
    except (KeyError, IndexError, TypeError, ValueError) as exc:
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
        body = {"model": c.model, "messages": messages, "temperature": c.temperature,
                "max_tokens": c.max_tokens, "stream": False}
        if tools and schemas and c.tool_mode == "native":
            body.update(tools=schemas, tool_choice="auto")
        headers = {"Authorization": "Bearer " + secret} if secret else {}
        timeout = httpx.Timeout(c.timeout, connect=c.connect_timeout)
        async with httpx.AsyncClient(timeout=timeout, trust_env=c.trust_env,
                                     transport=self.transport, follow_redirects=False) as client:
            for attempt in range(c.max_retries + 1):
                started = time.monotonic()
                delay_header = None
                try:
                    await emit("model_request", {"attempt": attempt + 1, "model": c.model})
                    async with asyncio.timeout(c.timeout):
                        response = await client.post(c.url(), json=body, headers=headers)
                    status = response.status_code
                    if status >= 300:
                        delay_header = response.headers.get("Retry-After")
                        code = {401: "authentication_failed", 403: "access_denied",
                                404: "endpoint_not_found", 429: "rate_limited"}.get(status,
                                "server_error" if status >= 500 else "request_rejected")
                        raise HarnessError(code, f"Model endpoint returned HTTP {status}. Check endpoint/model/tool settings.",
                                           "model", status in (408, 429, 500, 502, 503, 504),
                                           http_status=status, request_id=response.headers.get("x-request-id", "")[:120])
                    result = validate_reply(response.json())
                    await emit("model_response", {"elapsed_ms": round((time.monotonic()-started)*1000),
                                                 "tool_calls": len(result.get("tool_calls", []))})
                    return result
                except HarnessError as exc:
                    error = exc
                except (httpx.TimeoutException, TimeoutError):
                    error = HarnessError("model_timeout", "Model request timed out.", "model", True)
                except httpx.RequestError:
                    error = HarnessError("network_error", "Connection failed. Check VPN, DNS, proxy and certificate settings.", "model", True)
                except (ValueError, UnicodeError):
                    error = HarnessError("invalid_json_response", "Endpoint returned non-JSON data.", "model")
                if not error.retryable or attempt >= c.max_retries:
                    raise error
                delay = retry_delay(delay_header, attempt)
                await emit("model_retry", {"delay_seconds": delay, "error": error.as_dict()})
                await asyncio.sleep(delay)
