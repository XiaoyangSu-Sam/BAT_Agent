import asyncio
import uuid
from .context import repair_incomplete
from .model import ModelClient
from .turn import run_turn
from .tools import ToolRegistry
from ..errors import HarnessError, redact

def clean(value, secrets):
    if isinstance(value, str):
        return redact(value, secrets)
    if isinstance(value, dict):
        return {k:clean(v, secrets) for k,v in value.items()}
    if isinstance(value, list):
        return [clean(v, secrets) for v in value]
    return value

class RunManager:
    def __init__(self, settings, store, skills, model_factory=ModelClient):
        self.settings, self.store, self.skills = settings, store, skills
        self.model_factory = model_factory
        self.tasks, self.approvals = {}, {}

    def busy(self):
        return any(not t.done() for t in self.tasks.values())

    def start(self, session_id, prompt, model_id=None):
        if self.busy():
            raise HarnessError("workspace_busy", "One run is already using this workspace. Stop it or wait.", "runtime")
        model_id = model_id or self.settings.default_model
        config = self.settings.model(model_id)
        secrets = []
        if config.provider != "fake":
            config.url()
            secret = config.secret()
            # Snapshot credential and configuration for the whole run.
            config.api_key = secret
            secrets = [secret]
        session = self.store.session(session_id)
        messages = repair_incomplete(session["messages"])
        messages.append({"role":"user","content":prompt})
        self.store.save_messages(session_id, messages)
        key = self.store.create_run(session_id, model_id)
        execution = self.settings.execution.model_copy()
        if session["approval_mode"] is not None:
            execution.approval_mode = session["approval_mode"]
        self.tasks[key] = asyncio.create_task(
            self._run(key, session_id, messages, config, secrets, execution, session["approval_mode"] == "all"))
        return key

    async def _run(self, key, session_id, messages, config, secrets, execution, always_ask):
        async def emit(kind, data):
            self.store.event(key, kind, clean(data, secrets))
        async def approve(call_id, name, args):
            future = asyncio.get_running_loop().create_future()
            approval_id = uuid.uuid4().hex
            kind = tools.entries[name]["kind"]
            self.approvals[key] = (approval_id, future, kind, session_id)
            self.store.status(key, "awaiting_approval")
            await emit("approval_required", {"approval_id": approval_id, "call_id": call_id,
                                             "name": name, "arguments": args, "kind": kind,
                                             "can_allow_all": kind == "execute" and not always_ask})
            try:
                accepted = await asyncio.wait_for(future, 600)
                self.store.status(key, "running")
                await emit("approval_resolved", {"approved":accepted})
                return accepted
            except asyncio.TimeoutError as exc:
                raise HarnessError("approval_timeout", "Approval expired after 10 minutes.", "approval") from exc
            finally:
                self.approvals.pop(key, None)
        try:
            self.settings.workspace.mkdir(parents=True, exist_ok=True)
            await emit("run_started", {"provider":config.provider,"model":config.model,
                       "tool_mode":config.tool_mode,"workspace":str(self.settings.workspace)})
            tools = ToolRegistry(self.settings, self.skills)
            await run_turn(key, session_id, messages, config, tools, self.skills,
                           execution, self.store, emit, approve, self.model_factory,
                           execution_allowed=lambda: not always_ask and self.store.execution_allowed(session_id))
            self.store.status(key, "completed")
            await emit("completed", {})
        except asyncio.CancelledError:
            self.store.status(key, "cancelled")
            await emit("cancelled", {"message":"Stopped. Existing file changes are retained."})
        except HarnessError as exc:
            error = clean(exc.as_dict(), secrets)
            self.store.status(key, "failed", error)
            await emit("error", error)
        except Exception:
            error = {"code":"internal_error","stage":"runtime","message":"Unexpected runtime error.","retryable":False}
            self.store.status(key, "failed", error)
            await emit("error", error)
        finally:
            self.approvals.pop(key, None)

    def decide(self, key, approval_id, accepted, allow_all_execution=False):
        item = self.approvals.get(key)
        if not item or item[0] != approval_id or item[1].done():
            raise HarnessError("approval_expired", "This approval is no longer pending.", "approval")
        if allow_all_execution:
            if not accepted or item[2] != "execute" or self.store.session(item[3])["approval_mode"] == "all":
                raise HarnessError("invalid_approval_scope", "Allow all applies only to an approved execution request.", "approval")
            self.store.set_execution_approval(item[3], True)
            self.store.event(key, "approval_policy_changed", {"session_id":item[3], "allow_all_execution":True})
        item[1].set_result(accepted)

    async def cancel(self, key):
        task = self.tasks.get(key)
        if task and not task.done():
            self.store.status(key, "cancelling")
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                self.store.status(key, "cancelled")
                self.store.event(key, "cancelled", {"message":"Stopped before execution started."})

    async def close(self):
        for key in list(self.tasks):
            await self.cancel(key)
