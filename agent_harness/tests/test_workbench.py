import json
import re
import httpx
import pytest
from fastapi.testclient import TestClient
from agent_harness.server import create_app
from agent_harness.runtime.model import ModelClient

def client_for(root, factory=None):
    app = create_app(root, model_factory=factory)
    return TestClient(app, base_url="http://127.0.0.1", headers={"x-harness-token": app.state.token})

def test_first_run_and_existing_model_yaml(settings):
    with client_for(settings.root) as client:
        assert client.get("/api/config").json()["setup_required"]
        assert client.get("/static/editor.bundle.js").status_code == 200
        for asset in re.findall(r'(?:src|href)="(/static/[^\"]+)"', client.get("/").text):
            response = client.get(asset)
            assert response.status_code == 200, asset
            assert response.content, asset
    folder = settings.root / "config"
    folder.mkdir()
    (folder / "model.yaml").write_text("endpoint: http://model.test/v1\nmodel: test-model\napi_key: ''\n")
    with client_for(settings.root) as client:
        data = client.get("/api/config").json()
        assert not data["setup_required"]
        assert data["models"][0]["model"] == "test-model"

@pytest.mark.parametrize("key", ["", "example-test-key"])
def test_connection_uses_http_and_does_not_save_draft(settings, key):
    requests = []
    def handle(request):
        requests.append(request)
        body = json.loads(request.content)
        assert body["model"] == "custom-model"
        assert "tools" not in body
        assert request.headers.get("authorization") == ("Bearer "+key if key else None)
        return httpx.Response(200, json={"choices":[{"message":{"role":"assistant","content":"OK"}}]})
    factory = lambda cfg: ModelClient(cfg, transport=httpx.MockTransport(handle))
    value = {"id":"mine","endpoint":"http://model.test/v1","model":"custom-model",
             "auth_mode":"session" if key else "none","session_api_key":key}
    with client_for(settings.root, factory) as client:
        report = client.post("/api/models/test", json=value)
        assert report.status_code == 200 and report.json()["connected"]
        assert len(requests) == 1
        assert not (settings.root / "config/environment.yaml").exists()
        assert client.get("/api/config").json()["setup_required"]
        assert client.post("/api/models", json=value).status_code == 200
        assert not client.get("/api/config").json()["setup_required"]
    if key:
        assert key not in (settings.root / "config/environment.yaml").read_text()
        with client_for(settings.root) as client:
            assert client.get("/api/config").json()["setup_required"]

def test_custom_endpoint_404_is_fixed_by_exact_mode_and_survives_reload(settings):
    requests = []
    endpoint = "https://model.invalid/api/inference/"

    def handle(request):
        requests.append(str(request.url))
        body = json.loads(request.content)
        assert request.headers["content-type"] == "application/json"
        assert "authorization" not in request.headers
        assert body["model"] == "custom-model" and "tools" not in body
        if str(request.url) != endpoint:
            return httpx.Response(404)
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "OK"}}]})

    factory = lambda cfg: ModelClient(cfg, transport=httpx.MockTransport(handle))
    value = {"id": "custom", "endpoint": endpoint, "model": "custom-model", "auth_mode": "none"}
    with client_for(settings.root, factory) as client:
        rejected = client.post("/api/models/test", json=value)
        assert rejected.json()["error"]["http_status"] == 404
        value["endpoint_mode"] = "exact"
        report = client.post("/api/models/test", json=value)
        assert report.status_code == 200 and report.json()["connected"]
        assert report.json()["endpoint"] == endpoint
        assert client.post("/api/models", json=value).status_code == 200
    with client_for(settings.root, factory) as client:
        saved = client.get("/api/config").json()["models"][0]
        assert saved["endpoint_mode"] == "exact" and saved["endpoint"] == endpoint
        cfg = client.app.state.settings.model()
        assert cfg.url() == endpoint and cfg.api_key == ""
        assert client.post("/api/models/test", json=value).json()["connected"]
    assert requests == [endpoint.rstrip("/") + "/v1/chat/completions", endpoint, endpoint]


def test_failed_connection_and_invalid_input_do_not_echo_key(settings):
    factory = lambda cfg: ModelClient(cfg, transport=httpx.MockTransport(
        lambda request: httpx.Response(401, text="private upstream details")))
    value = {"id":"mine","endpoint":"http://model.test/v1","model":"m",
             "auth_mode":"session","session_api_key":"DO_NOT_ECHO"}
    with client_for(settings.root, factory) as client:
        result = client.post("/api/models/test", json=value)
        assert result.status_code == 400 and result.json()["error"]["code"] == "authentication_failed"
        assert "DO_NOT_ECHO" not in result.text and "private upstream" not in result.text
        value["id"] = "invalid id"
        invalid = client.post("/api/models/test", json=value)
        assert invalid.status_code == 422 and "DO_NOT_ECHO" not in invalid.text
        assert not (settings.root / "config/environment.yaml").exists()

def test_saved_model_checks_use_the_selected_endpoint_and_credential(settings, monkeypatch):
    monkeypatch.setenv("SECOND_MODEL_KEY", "fixture-secondary-key")
    seen = []

    def handle(request):
        body = json.loads(request.content)
        assert "tools" not in body and body["max_tokens"] <= 256
        assert body["messages"] == [{"role": "user", "content": "Reply with OK."}]
        seen.append((str(request.url), body["model"], request.headers.get("authorization")))
        if body["model"] == "beta":
            return httpx.Response(503)
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "OK"}}]})

    factory = lambda cfg: ModelClient(cfg, transport=httpx.MockTransport(handle))
    with client_for(settings.root, factory) as client:
        alpha = {"id": "first", "endpoint": "https://alpha.invalid/v1", "model": "alpha", "create_only": True}
        beta = {"id": "second", "endpoint": "https://beta.invalid/custom", "endpoint_mode": "exact",
                "model": "beta", "auth_mode": "env", "api_key_env": "SECOND_MODEL_KEY", "create_only": True}
        assert client.post("/api/models", json=alpha).status_code == 200
        assert client.post("/api/models", json=beta).status_code == 200
        duplicate = client.post("/api/models", json={**beta, "id": "first"})
        assert duplicate.json()["error"]["code"] == "connection_exists"
        assert client.post("/api/models/first/check", json={}).json()["connected"]
        failed = client.post("/api/models/second/check", json={})
        assert failed.json()["error"]["http_status"] == 503
        assert "fixture-secondary-key" not in failed.text
    assert seen == [("https://alpha.invalid/v1/chat/completions", "alpha", None),
                    ("https://beta.invalid/custom", "beta", "Bearer fixture-secondary-key")]

def test_editor_reads_full_document_and_protects_conflicts(settings):
    source = "\r\n".join(f"# line {i} " + "x"*90 for i in range(600))+"\r\n"
    file = settings.workspace / "large.py"
    file.write_bytes(source.encode())
    with client_for(settings.root) as client:
        tree = client.get("/api/workspace/tree").json()
        assert "large.py" in tree["files"]
        read = client.get("/api/workspace/file", params={"path":"large.py"}).json()
        assert read["content"] == source and read["line_ending"] == "CRLF"
        saved = client.post("/api/workspace/file", json={"path":"large.py",
            "content": source+"print(42)\r\n", "expected_sha256":read["sha256"]})
        assert saved.status_code == 200
        assert file.read_bytes().endswith(b"print(42)\r\n")
        conflict = client.post("/api/workspace/file", json={"path":"large.py",
            "content":"stale", "expected_sha256":read["sha256"]})
        assert conflict.status_code == 409
        assert client.get("/api/workspace/file", params={"path":"../escape"}).status_code == 400
        assert client.post("/api/workspace/file", json={"path":".env", "content":"secret"}).status_code == 400
        created = client.post("/api/workspace/file", json={"path":"src/new.py", "content":"print(7)"})
        assert created.status_code == 200 and (settings.workspace/"src/new.py").exists()

def test_workspace_switch_skills_and_busy_editor(settings):
    alternate = settings.root / "another-project"
    alternate.mkdir()
    with client_for(settings.root) as client:
        assert client.get("/api/skills/local-coding").json()["skill_id"] == "local-coding"
        assert client.post("/api/workspace/open", json={"path":"relative"}).status_code == 400
        switched = client.post("/api/workspace/open", json={"path":str(alternate)})
        assert switched.status_code == 200
        assert switched.json()["workspace"] == str(alternate.resolve())
        app = client.app
        app.state.manager.busy = lambda: True
        assert client.post("/api/workspace/file", json={"path":"no.py", "content":""}).status_code == 409
        assert client.post("/api/workspace/open", json={"path":str(settings.workspace)}).status_code == 409
    with client_for(settings.root) as client:
        assert client.get("/api/config").json()["workspace"] == str(alternate.resolve())
