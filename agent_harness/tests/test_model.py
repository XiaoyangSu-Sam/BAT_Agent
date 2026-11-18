import asyncio
import json
import httpx
import pytest
from agent_harness.config import ModelConfig
from agent_harness.errors import HarnessError
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

def test_env_resolution(monkeypatch):
    monkeypatch.setenv("TEST_HARNESS_KEY","test-secret")
    assert ModelConfig(api_key="$TEST_HARNESS_KEY").secret() == "test-secret"
    assert ModelConfig(api_key="$"+"{TEST_HARNESS_KEY}").secret() == "test-secret"
    assert ModelConfig(api_key="").secret() == ""
    monkeypatch.delenv("TEST_HARNESS_KEY")
    with pytest.raises(HarnessError):
        ModelConfig(api_key="$TEST_HARNESS_KEY").secret()

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

def test_full_native_tool_roundtrip():
    requests=[]
    def handler(req):
        body=json.loads(req.content);requests.append(body)
        if len(requests)==1:
            return httpx.Response(200,json=response())
        if len(requests)==2:
            nonce=body["messages"][-1]["content"].split("value ")[1].split(".")[0]
            return httpx.Response(200,json=response(None,[{"id":"probe_1","type":"function",
                "function":{"name":"echo_probe","arguments":json.dumps({"value":nonce})}}]))
        assert body["messages"][-1]["role"]=="tool"
        assert body["messages"][-1]["tool_call_id"]=="probe_1"
        return httpx.Response(200,json=response(json.loads(body["messages"][-1]["content"])["value"]))
    cfg=ModelConfig(endpoint="http://host/v1")
    result=asyncio.run(diagnose(cfg,lambda c:ModelClient(c,httpx.MockTransport(handler))))
    assert result["chat"]=="passed" and result["tools"]=="passed"

def test_multimodel_precedence(settings):
    folder=settings.root/"config";folder.mkdir()
    folder.joinpath("model.yaml").write_text("model: single\nendpoint: http://single/v1")
    folder.joinpath("environment.yaml").write_text("default_model: default\nmodels:\n  default:\n    model: multi\n    endpoint: http://multi/v1")
    settings.reload()
    assert settings.model().model=="multi"
