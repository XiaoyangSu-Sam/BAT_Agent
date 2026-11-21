import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from pydantic import BaseModel, Field
from fastapi.exceptions import RequestValidationError
from .config import ApprovalMode, Settings
from . import __version__
from .errors import HarnessError
from .store import Store
from .runtime.skills import SkillRegistry
from .runtime.manager import RunManager
from .model_settings import ModelInput, save_model, connection_config
from .diagnostics import diagnose
from .model_discovery import discover_models
from .runtime.model import ModelClient
from .runtime.files import FileTools
from .workspace import read_document, save_document, open_workspace

class Prompt(BaseModel):
    prompt: str = Field(min_length=1, max_length=50000)
    model_id: str | None = None

class Decision(BaseModel):
    approval_id: str
    approved: bool
    allow_all_execution: bool = False

class ExecutionApprovalInput(BaseModel):
    allow_all: bool

class SessionInput(BaseModel):
    title: str = "New task"
    approval_mode: ApprovalMode | None = None

class ApprovalModeInput(BaseModel):
    approval_mode: ApprovalMode

class DocumentInput(BaseModel):
    path: str = Field(min_length=1, max_length=4096)
    content: str = Field(max_length=1_000_000)
    expected_sha256: str = ""

class WorkspaceInput(BaseModel):
    path: str = Field(min_length=1, max_length=4096)

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

    app = FastAPI(title="BAT Agent", version=__version__, lifespan=lifespan)
    app.state.manager, app.state.store, app.state.settings = manager, store, settings
    app.state.token = token

    def require_idle():
        if manager.busy():
            raise HarnessError("workspace_busy", "Wait for the active conversation task, or stop it first.")

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        # Do not echo an invalid request body that may contain an API key.
        return JSONResponse({"error": {"code": "invalid_input", "message": "; ".join(
            ".".join(str(p) for p in e["loc"][1:]) + ": " + e["msg"] for e in error.errors())}}, status_code=422)

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
            "workspace_busy","approval_expired","file_conflict") else 400)

    @app.exception_handler(KeyError)
    async def not_found(request, error):
        return JSONResponse({"error":{"code":"not_found","message":"Session or run does not exist."}}, status_code=404)

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return (static / "index.html").read_text(encoding="utf-8").replace("__HARNESS_TOKEN__", token).replace("__VERSION__", __version__)

    @app.get("/static/{name}")
    async def asset(name: str):
        if name not in ("app.js","ui.js","style.css","chat-layout.css","layout.js","editor.bundle.js","connection.js","workspace.js","markdown.bundle.js"):
            return JSONResponse({}, status_code=404)
        return FileResponse(static / name)

    @app.get("/health")
    async def health():
        return {"status":"ok","version":__version__}

    @app.get("/api/config")
    async def config():
        return settings.public()

    async def check_connection(cfg, *, brief=False):
        if cfg.provider == "fake":
            return {"connected": False, "model": cfg.model, "message": "Offline demo"}
        cfg.secret()
        cfg.max_retries, cfg.timeout = 0, min(cfg.timeout, 30)
        if brief:
            cfg.max_tokens = min(cfg.max_tokens, 256)
        checks = [{"phase":"validated", "message":"Endpoint and credentials are configured"}]
        async def observe(kind, data):
            if kind == "communication":
                checks.append(data)
        started = time.monotonic()
        client = (model_factory or ModelClient)(cfg)
        reply_status = "complete"
        verification = "Valid model reply received"
        try:
            reply = await client.complete([{"role": "user", "content": "Reply with OK."}], [], observe, tools=False)
        except HarnessError as error:
            if not (brief and error.code == "output_truncated" and error.details.get("generated_output")):
                raise
            reply_status = "output_truncated"
            verification = "Endpoint responded. The short probe reached its token limit."
        else:
            if not reply.get("content") or reply.get("tool_calls"):
                raise HarnessError("invalid_model_response", "The endpoint did not return a text response.", "model")
        return {"connected": True, "model": cfg.model, "endpoint": cfg.url(),
                "elapsed_ms": round((time.monotonic()-started)*1000), "message": verification,
                "reply_status": reply_status, "checks": checks + [{"phase": "verified", "message": verification}]}

    @app.post("/api/models/test")
    async def test_connection(value: ModelInput):
        require_idle()
        return await check_connection(connection_config(value, settings))

    @app.post("/api/models/{model_id}/check")
    async def check_saved_model(model_id: str):
        require_idle()
        return await check_connection(settings.model(model_id), brief=True)

    @app.post("/api/models/discover")
    async def model_list(value: ModelInput):
        require_idle()
        return await discover_models(connection_config(value, settings))

    @app.get("/api/workspace/tree")
    async def tree():
        settings.workspace.mkdir(parents=True, exist_ok=True)
        return {"root": str(settings.workspace), **FileTools(settings.workspace, settings.state_dir).list_files()}

    @app.get("/api/workspace/file")
    async def document(path: str):
        return read_document(settings, path)

    @app.post("/api/workspace/file")
    async def save_document_route(value: DocumentInput):
        require_idle()
        return save_document(settings, value.path, value.content, value.expected_sha256)

    @app.post("/api/workspace/open")
    async def open_folder(value: WorkspaceInput):
        require_idle()
        return open_workspace(settings, value.path)

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

    @app.get("/api/skills/{skill_id}")
    async def skill_detail(skill_id: str):
        return skills.read_skill(skill_id)

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
        return store.create_session(value.title, value.approval_mode)

    @app.get("/api/sessions/{session_id}")
    async def session(session_id: str):
        return {**store.session(session_id), "runs":store.runs(session_id)}

    @app.post("/api/sessions/{session_id}/approval-mode")
    async def set_approval_mode(session_id: str, value: ApprovalModeInput):
        require_idle()
        store.set_approval_mode(session_id, value.approval_mode)
        return {"approval_mode": value.approval_mode, "allow_all_execution": False}

    @app.post("/api/sessions/{session_id}/execution-approval")
    async def execution_approval(session_id: str, value: ExecutionApprovalInput):
        # Enabling requires an actual pending execution approval. This endpoint revokes it.
        if value.allow_all:
            raise HarnessError("invalid_approval_scope", "Use Allow all on a pending execution request.", "approval")
        store.set_execution_approval(session_id, False)
        return {"session_id":session_id, "allow_all_execution":False}

    @app.post("/api/sessions/{session_id}/runs")
    async def run(session_id: str, value: Prompt):
        return {"run_id":manager.start(session_id, value.prompt, value.model_id)}

    @app.get("/api/runs/{run_id}")
    async def run_status(run_id: str, after: int=0):
        return store.run(run_id, max(0, after))

    @app.post("/api/runs/{run_id}/approval")
    async def approval(run_id: str, value: Decision):
        manager.decide(run_id, value.approval_id, value.approved, value.allow_all_execution)
        return {"accepted":True}

    @app.post("/api/runs/{run_id}/cancel")
    async def cancel(run_id: str):
        store.run(run_id)
        await manager.cancel(run_id)
        return {"status":store.run(run_id)["status"]}

    return app
