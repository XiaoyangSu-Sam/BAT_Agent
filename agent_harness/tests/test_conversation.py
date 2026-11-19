import asyncio
import json
import socket
import ssl
import httpx
import pytest
import yaml
from agent_harness.config import ModelConfig, Settings
from agent_harness.connection_help import network_error
from agent_harness.errors import HarnessError
from agent_harness.model_discovery import discover_models
from agent_harness.model_settings import ModelInput, connection_config, save_model
from agent_harness.runtime.model import ModelClient, validate_reply
from agent_harness.runtime.context import wire_messages
from agent_harness.runtime.tools import ToolRegistry

async def quiet(*args):
    pass

def test_reasoning_usage_and_protocol_metadata():
    data = {"choices":[{"message":{"content":"Answer", "reasoning_content":"Model supplied detail"}}],
            "usage":{"prompt_tokens":2000,"completion_tokens":100,"total_tokens":2100,"bad":"secret"}}
    reply = validate_reply(data)
    assert reply["_reasoning"] == "Model supplied detail"
    assert reply["_usage"] == {"prompt_tokens":2000,"completion_tokens":100,"total_tokens":2100}
    assert wire_messages([reply], "native") == [{"role":"assistant","content":"Answer"}]
    def handler(request):
        assert "_reasoning" not in json.loads(request.content)["messages"][0]
        data["choices"][0]["message"]["reasoning_content"]="private-key"
        return httpx.Response(200,json=data)
    cfg=ModelConfig(endpoint="http://test/v1",api_key="private-key")
    result=asyncio.run(ModelClient(cfg,httpx.MockTransport(handler)).complete([reply],[],quiet))
    assert "private-key" not in result["_reasoning"]
    assert "_reasoning" not in validate_reply({"choices":[{"message":{"content":"Simple"}}]})

@pytest.mark.parametrize("cause,expected", [
    (socket.gaierror(-2,"cannot resolve"),"dns_error"),
    (ConnectionRefusedError(10061,"refused"),"connection_refused"),
    (ssl.SSLCertVerificationError("certificate"),"tls_error")])
def test_network_causes(cause,expected):
    exc=httpx.ConnectError("connection failed")
    exc.__cause__=cause
    assert network_error(exc).code==expected

def test_forbidden_is_not_a_vpn_diagnosis():
    client=ModelClient(ModelConfig(endpoint="http://test",max_retries=0),
        httpx.MockTransport(lambda request:httpx.Response(403)))
    with pytest.raises(HarnessError) as error:
        asyncio.run(client.complete([],[],quiet))
    assert error.value.details["http_status"]==403
    assert any("does not prove" in text for text in error.value.details["suggestions"])

def test_model_discovery_and_empty_key():
    def handle(request):
        assert str(request.url)=="http://test/prefix/v1/models"
        assert "authorization" not in request.headers
        return httpx.Response(200,json={"data":[{"id":"a","context_length":32768},{"id":"b"},{"id":"c","max_model_len":"unknown"}]})
    result=asyncio.run(discover_models(ModelConfig(endpoint="http://test/prefix/v1/chat/completions"),
        httpx.MockTransport(handle)))
    assert result["models"]==[{"id":"a","context_window":32768},{"id":"b","context_window":None},{"id":"c","context_window":None}]

def test_saved_key_reuse_does_not_persist_secret(settings):
    save_model(settings,ModelInput(id="mine",endpoint="http://test",model="m",
        auth_mode="session",session_api_key="sensitive-session-key"))
    value=ModelInput(id="mine",endpoint="http://test",model="other",auth_mode="saved",context_window=32768)
    assert connection_config(value,settings).secret()=="sensitive-session-key"
    save_model(settings,value)
    source=(settings.root/"config/environment.yaml").read_text()
    assert "sensitive-session-key" not in source
    assert yaml.safe_load(source)["models"]["mine"]["context_window"]==32768
    assert Settings(settings.root).public()["setup_required"]

def test_skill_create_update_execute_and_path_checks(settings,skills):
    tools=ToolRegistry(settings,skills)
    def call(name,**args):
        return asyncio.run(tools.call(name,args))
    result=call("write_skill_file",skill_id="math-demo",path="SKILL.md",
        content="---\nname: Math demo\ndescription: Compute a result.\n---\nRun scripts/calc.py.")
    assert result["registered"] and result["scope"]=="skill"
    call("write_skill_file",skill_id="math-demo",path="scripts/calc.py",content="print(6*7)")
    resource=call("read_skill_resource",skill_id="math-demo",path="scripts/calc.py")
    with pytest.raises(HarnessError):
        call("write_skill_file",skill_id="math-demo",path="scripts/calc.py",content="stale")
    call("write_skill_file",skill_id="math-demo",path="scripts/calc.py",content="print(7*6)",expected_sha256=resource["sha256"])
    execution=call("run_python_script",skill_id="math-demo",path="scripts/calc.py")
    assert execution["exit_code"]==0 and "42" in execution["stdout"]
    for skill,path in [("../escape","SKILL.md"),("math-demo","scripts/../../escape.py"),("math-demo",".env")]:
        with pytest.raises(HarnessError):
            call("write_skill_file",skill_id=skill,path=path,content="bad")
    with pytest.raises(HarnessError):
        call("write_skill_file",skill_id="bad",path="SKILL.md",content="---\n[broken\n---\ntext")
    assert "bad" not in skills.skills
