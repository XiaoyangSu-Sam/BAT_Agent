import json
import time
from fastapi.testclient import TestClient
from agent_harness.server import create_app

def test_api_and_real_demo(settings, monkeypatch):
    monkeypatch.setenv("AGENT_HARNESS_MODEL_PROVIDER","fake")
    app=create_app(settings.root)
    with TestClient(app,base_url="http://127.0.0.1") as client:
        assert client.get("/api/config").status_code==403
        client.headers["x-harness-token"]=app.state.token
        assert client.get("/health").json()["status"]=="ok"
        html=client.get("/").text
        from agent_harness import __version__
        assert "BAT Agent" in html and "From BAT Team" in html
        assert __version__ in html and "__VERSION__" not in html and "__HARNESS_TOKEN__" not in html
        assert client.get("/static/app.js").status_code==200
        assert client.get("/api/config").json()["models"][0]["provider"]=="fake"
        s=client.post("/api/sessions",json={"title":"integration"}).json()["id"]
        key=client.post(f"/api/sessions/{s}/runs",json={"prompt":"demo"}).json()["run_id"]
        for _ in range(400):
            data=client.get("/api/runs/"+key).json()
            if data["status"]=="awaiting_approval":
                event=next(e for e in data["events"] if e["type"]=="approval_required")
                assert not settings.workspace.joinpath("demo_result.json").exists()
                payload={"approval_id":event["data"]["approval_id"],"approved":True}
                assert client.post(f"/api/runs/{key}/approval",json=payload).status_code==200
                assert client.post(f"/api/runs/{key}/approval",json=payload).status_code==409
            if data["status"] in ("completed","failed"):
                break
            time.sleep(.025)
        assert data["status"]=="completed",data
        assert json.loads(settings.workspace.joinpath("demo_result.json").read_text())["sum"]==15
        assert client.post("/api/skills/refresh",json={}).status_code==200

def test_api_host_origin_and_secrets(settings):
    app=create_app(settings.root)
    with TestClient(app,base_url="http://127.0.0.1") as client:
        client.headers["x-harness-token"]=app.state.token
        assert client.get("/api/config",headers={"host":"evil.example"}).status_code==403
        assert client.post("/api/sessions",json={},headers={"origin":"https://evil.example"}).status_code==403
        value={"id":"internal","endpoint":"http://internal/v1","model":"nemotron",
               "auth_mode":"session","session_api_key":"TEST_DO_NOT_PERSIST"}
        response=client.post("/api/models",json=value)
        assert response.status_code==200,response.text
        assert "TEST_DO_NOT_PERSIST" not in response.text
        assert "TEST_DO_NOT_PERSIST" not in settings.root.joinpath("config/environment.yaml").read_text()
        assert client.get("/api/sessions/nonexistent").status_code==404
