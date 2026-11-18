import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from pydantic import BaseModel, Field
from .config import Settings
from .errors import HarnessError
from .store import Store
from .runtime.skills import SkillRegistry
from .runtime.manager import RunManager
from .model_settings import ModelInput, save_model
from .diagnostics import diagnose

class Prompt(BaseModel):
    prompt: str = Field(min_length=1, max_length=50000)
    model_id: str | None = None

class Decision(BaseModel):
    approval_id: str
    approved: bool

class SessionInput(BaseModel):
    title: str = "New task"

def create_app(root=None, model_factory=None):
    settings = Settings(root or os.getenv("AGENT_HARNESS_ROOT", "."))
    store = Store(settings.state_dir / "runs.sqlite3")
    skills = SkillRegistry(settings.root / "skills")
    kwargs = {"model_factory":model_factory} if model_factory else {}
    manager = RunManager(settings, store, skills, **kwargs)
    token = secrets.token_urlsafe(32)
    static = Path(__file__).parent / "static"

    @asynccontextmanager
    async def lifespan(app):
        yield
        await manager.close()

    app = FastAPI(title="Agent Harness Baseline", version="0.3.0", lifespan=lifespan)
    app.state.manager, app.state.store, app.state.settings = manager, store, settings
    app.state.token = token

    @app.middleware("http")
    async def local_boundary(request, call_next):
        host = urlsplit("http://"+request.headers.get("host", "")).hostname
        if host not in ("127.0.0.1","localhost","::1"):
            return JSONResponse({"error":{"code":"invalid_host","message":"Localhost only."}}, status_code=403)
        if request.url.path.startswith("/api/"):
            if not secrets.compare_digest(request.headers.get("x-harness-token", ""), token):
                return JSONResponse({"error":{"code":"invalid_token","message":"Reload the local page."}}, status_code=403)
            origin = request.headers.get("origin")
            if origin and origin != f"{request.url.scheme}://{request.headers.get('host')}":
                return JSONResponse({"error":{"code":"invalid_origin","message":"Same-origin requests only."}}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.exception_handler(HarnessError)
    async def error_handler(request, error):
        return JSONResponse({"error":error.as_dict()}, status_code=409 if error.code in (
            "workspace_busy","approval_expired") else 400)

    @app.exception_handler(KeyError)
    async def not_found(request, error):
        return JSONResponse({"error":{"code":"not_found","message":"Session or run does not exist."}}, status_code=404)

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return (static / "index.html").read_text(encoding="utf-8").replace("__HARNESS_TOKEN__", token)

    @app.get("/static/{name}")
    async def asset(name: str):
        if name not in ("app.js","ui.js","style.css"):
            return JSONResponse({}, status_code=404)
        return FileResponse(static / name)

    @app.get("/health")
    async def health():
        return {"status":"ok","version":"0.3.0"}

    @app.get("/api/config")
    async def config():
        return settings.public()

    @app.post("/api/models")
    async def model(value: ModelInput):
        if manager.busy():
            raise HarnessError("workspace_busy", "Wait for the active run before editing model settings.")
        save_model(settings, value)
        return settings.public()

    @app.post("/api/diagnostics/{model_id}")
    async def diagnostics(model_id: str):
        if manager.busy():
            raise HarnessError("workspace_busy", "Wait for the active run before running diagnostics.")
        return await diagnose(settings.model(model_id), **kwargs)

    @app.get("/api/skills")
    async def skill_list():
        return skills.list_skills()

    @app.post("/api/skills/refresh")
    async def refresh():
        if manager.busy():
            raise HarnessError("workspace_busy", "Wait for the run before refreshing skills.")
        skills.refresh()
        return skills.list_skills()

    @app.get("/api/sessions")
    async def sessions():
        return store.sessions()

    @app.post("/api/sessions")
    async def new_session(value: SessionInput):
        return store.create_session(value.title)

    @app.get("/api/sessions/{session_id}")
    async def session(session_id: str):
        return {**store.session(session_id), "runs":store.runs(session_id)}

    @app.post("/api/sessions/{session_id}/runs")
    async def run(session_id: str, value: Prompt):
        return {"run_id":manager.start(session_id, value.prompt, value.model_id)}

    @app.get("/api/runs/{run_id}")
    async def run_status(run_id: str, after: int=0):
        return store.run(run_id, max(0, after))

    @app.post("/api/runs/{run_id}/approval")
    async def approval(run_id: str, value: Decision):
        manager.decide(run_id, value.approval_id, value.approved)
        return {"accepted":True}

    @app.post("/api/runs/{run_id}/cancel")
    async def cancel(run_id: str):
        store.run(run_id)
        await manager.cancel(run_id)
        return {"status":store.run(run_id)["status"]}

    return app
