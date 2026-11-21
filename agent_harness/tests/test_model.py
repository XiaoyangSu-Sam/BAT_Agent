import asyncio
import json
import httpx
import pytest
from pydantic import ValidationError
from agent_harness.config import ModelConfig
from agent_harness.errors import HarnessError
from agent_harness.model_discovery import discover_models
from agent_harness.runtime.model import ModelClient, validate_reply
from agent_harness.diagnostics import diagnose

async def quiet(*args):
    pass

def response(content="ok", calls=None):
    return {"choices":[{"finish_reason":"tool_calls" if calls else "stop",
                       "message":{"role":"assistant","content":content,**({"tool_calls":calls} if calls else {})}}]}

@pytest.mark.parametrize("url,expected", [
    ("http://host:8080/v1", "http://host:8080/v1/chat/completions"),
    ("http://host:8080/v1/chat/completions","http://host:8080/v1/chat/completions"),
    ("https://host/proxy/v1/","https://host/proxy/v1/chat/completions")])
def test_endpoint(url, expected):
    assert ModelConfig(endpoint=url).url() == expected

@pytest.mark.parametrize("url", [
    "https://model.invalid/api/infer", "https://model.invalid/api/infer/",
    "https://model.invalid/v1", "https://model.invalid/v1/chat/completions/"])
def test_exact_endpoint_preserves_request_path(url):
    assert ModelConfig(endpoint=url, endpoint_mode="exact").url() == url


def test_custom_endpoint_does_not_guess_model_list():
    def unexpected_request(request):
        pytest.fail("Model discovery must not send a request to a guessed custom route")

    cfg = ModelConfig(endpoint="https://model.invalid/api/infer", endpoint_mode="exact")
    with pytest.raises(HarnessError) as exc:
        asyncio.run(discover_models(cfg, httpx.MockTransport(unexpected_request)))
    assert exc.value.code == "model_list_unavailable"


def test_env_resolution(monkeypatch):
    monkeypatch.setenv("TEST_HARNESS_KEY","test-secret")
    assert ModelConfig(api_key="$TEST_HARNESS_KEY").secret() == "test-secret"
    assert ModelConfig(api_key="$"+"{TEST_HARNESS_KEY}").secret() == "test-secret"
    assert ModelConfig(api_key="").secret() == ""
    monkeypatch.delenv("TEST_HARNESS_KEY")
    with pytest.raises(HarnessError):
        ModelConfig(api_key="$TEST_HARNESS_KEY").secret()

@pytest.mark.parametrize("key_line", ['', 'api_key:', 'api_key: null', 'api_key: ""'])
@pytest.mark.parametrize("filename", ["model.yaml", "environment.yaml"])
def test_yaml_without_credentials_sends_no_authentication(settings, key_line, filename):
    folder = settings.root / "config"
    folder.mkdir()
    content = "endpoint: http://model.invalid/v1\nmodel: test-model\n" + key_line + "\n"
    if filename == "environment.yaml":
        content = "default_model: test\nmodels:\n  test:\n" + "".join(
            "    " + line + "\n" for line in content.splitlines())
    folder.joinpath(filename).write_text(content, encoding="utf-8")
    settings.reload()
    cfg = settings.model()
    assert cfg.secret() == ""
    assert settings.public()["models"][0]["ready"] is True
    assert settings.public()["models"][0]["credential_configured"] is False
    requests = []

    def handler(req):
        requests.append((req.method, req.url.path))
        assert "authorization" not in req.headers
        if req.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "test-model"}]})
        return httpx.Response(200, json=response())

    transport = httpx.MockTransport(handler)
    result = asyncio.run(ModelClient(cfg, transport).complete(
        [{"role": "user", "content": "hi"}], [], quiet))
    assert result["content"] == "ok"
    discovered = asyncio.run(discover_models(cfg, transport))
    assert discovered["models"][0]["id"] == "test-model"
    assert requests == [("POST", "/v1/chat/completions"), ("GET", "/v1/models")]


@pytest.mark.parametrize("value", [False, 0, [], {}])
def test_invalid_credential_types_are_rejected(value):
    with pytest.raises(ValidationError):
        ModelConfig(api_key=value)


@pytest.mark.parametrize("credential", ["test-secret", "$TEST_HARNESS_KEY"])
def test_configured_credentials_are_still_sent(monkeypatch, credential):
    monkeypatch.setenv("TEST_HARNESS_KEY", "test-secret")

    def handler(req):
        assert req.headers["authorization"] == "Bearer test-secret"
        return httpx.Response(200, json=response())

    client = ModelClient(ModelConfig(endpoint="http://model.invalid/v1", api_key=credential),
                         httpx.MockTransport(handler))
    assert asyncio.run(client.complete([], [], quiet))["content"] == "ok"


def test_retry_only_model_request():
    count=0
    def handler(req):
        nonlocal count
        count+=1
        if count==1:
            return httpx.Response(503,headers={"Retry-After":"0"})
        assert "authorization" not in req.headers
        return httpx.Response(200,json=response("success"))
    client=ModelClient(ModelConfig(endpoint="http://host/v1",max_retries=1),httpx.MockTransport(handler))
    value=asyncio.run(client.complete([{"role":"user","content":"hi"}],[],quiet))
    assert value["content"]=="success" and count==2

@pytest.mark.parametrize("status,code",[(401,"authentication_failed"),(403,"access_denied"),(404,"endpoint_not_found"),(429,"rate_limited"),(500,"server_error")])
def test_http_errors(status,code):
    client=ModelClient(ModelConfig(endpoint="http://host",max_retries=0),httpx.MockTransport(
        lambda req:httpx.Response(status,text="secret provider details")))
    with pytest.raises(HarnessError) as exc:
        asyncio.run(client.complete([],[],quiet))
    assert exc.value.code==code
    assert "secret provider" not in str(exc.value)

def test_invalid_response():
    with pytest.raises(HarnessError):
        validate_reply({"choices":[]})
    data=response()
    data["choices"][0]["finish_reason"]="length"
    with pytest.raises(HarnessError) as exc:
        validate_reply(data)
    assert exc.value.code=="output_truncated"

@pytest.mark.parametrize("echo_tool_result,expected", [(True, "passed"), (False, "result_not_confirmed")])
def test_full_native_tool_roundtrip(echo_tool_result, expected):
    requests=[]
    nonce = None
    def handler(req):
        nonlocal nonce
        body=json.loads(req.content);requests.append(body)
        assert body["stream"] is False
        assert req.headers["accept"] == "application/json"
        if len(requests)==1:
            return httpx.Response(200,json=response())
        if len(requests)==2:
            nonce=body["messages"][-1]["content"].split("value ")[1].split(".")[0]
            reply = response(None, [{"id": "probe_1", "type": "function",
                "function": {"name": "echo_probe", "arguments": json.dumps({"value": nonce})}}])
            reply["choices"][0]["message"]["reasoning"] = "Use the diagnostic tool."
            return httpx.Response(200, json=reply)
        assert body["messages"][-1]["role"]=="tool"
        assert body["messages"][-1]["tool_call_id"]=="probe_1"
        assert body["messages"][-2]["reasoning_content"] == "Use the diagnostic tool."
        result = json.loads(body["messages"][-1]["content"])["result"]
        assert result != nonce
        return httpx.Response(200, json=response(result if echo_tool_result else nonce))
    cfg=ModelConfig(endpoint="http://host/v1", model="nvidia/nemotron-3.5-super-vl-120b-a12b")
    result=asyncio.run(diagnose(cfg,lambda c:ModelClient(c,httpx.MockTransport(handler))))
    assert result["chat"]=="passed" and result["tools"]==expected


def test_unexpected_sse_body_is_not_read_or_dispatched():
    class UnexpectedStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            pytest.fail("A non-streaming request must stop at the SSE headers")
            yield b""

    def handle(request):
        assert request.headers["accept"] == "application/json"
        return httpx.Response(200, headers={"Content-Type": "text/event-stream; charset=utf-8"},
                              stream=UnexpectedStream())

    client = ModelClient(ModelConfig(endpoint="https://model.invalid/v1"), httpx.MockTransport(handle))
    with pytest.raises(HarnessError) as exc:
        asyncio.run(client.complete([{"role": "user", "content": "hello"}], [], quiet))
    assert exc.value.code == "unexpected_stream"


@pytest.mark.parametrize("payload", [
    {"choices": [None]},
    {"choices": [{"message": []}]},
    {"choices": [{"finish_reason": "tool_calls", "message": {"content": "missing call"}}]},
    response(None, [{"id": "partial", "type": "function",
                     "function": {"name": "example", "arguments": '{"path":'}}]),
])
def test_malformed_reply_becomes_a_protocol_error(payload):
    with pytest.raises(HarnessError) as exc:
        validate_reply(payload)
    assert exc.value.code == "invalid_model_response"


def test_redirect_does_not_forward_credentials():
    urls = []

    def handle(request):
        urls.append(str(request.url))
        assert request.headers["authorization"] == "Bearer fixture-secret"
        return httpx.Response(307, headers={"location": "https://other.invalid/v1/chat/completions"})

    cfg = ModelConfig(endpoint="https://model.invalid/v1", api_key="fixture-secret")
    with pytest.raises(HarnessError) as exc:
        asyncio.run(ModelClient(cfg, httpx.MockTransport(handle)).complete([], [], quiet))
    assert exc.value.code == "endpoint_redirect"
    assert urls == ["https://model.invalid/v1/chat/completions"]


@pytest.mark.parametrize("timeout_type,stage", [(httpx.ConnectTimeout, "network"), (httpx.ReadTimeout, "response")])
def test_transport_reports_connect_and_read_timeout_separately(timeout_type, stage):
    def handle(request):
        raise timeout_type("fixture timeout", request=request)

    cfg = ModelConfig(endpoint="https://model.invalid/v1", max_retries=0)
    with pytest.raises(HarnessError) as exc:
        asyncio.run(ModelClient(cfg, httpx.MockTransport(handle)).complete([], [], quiet))
    assert exc.value.code == "model_timeout"
    assert exc.value.stage == stage and exc.value.retryable

def test_multimodel_precedence(settings):
    folder=settings.root/"config";folder.mkdir()
    folder.joinpath("model.yaml").write_text("model: single\nendpoint: http://single/v1")
    folder.joinpath("environment.yaml").write_text("default_model: default\nmodels:\n  default:\n    model: multi\n    endpoint: http://multi/v1")
    settings.reload()
    assert settings.model().model=="multi"
