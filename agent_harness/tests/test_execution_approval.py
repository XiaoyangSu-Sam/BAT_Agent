import asyncio
import json
import sqlite3
import uuid

import pytest

from agent_harness.errors import HarnessError
from agent_harness.runtime.manager import RunManager
from agent_harness.store import Store
from agent_harness.tests.test_runtime import wait_approval
from agent_harness.tests.test_workbench import client_for


class TwoExecutions:
    def __init__(self, config):
        self.calls = 0

    async def complete(self, messages, schemas, emit, tools=True):
        self.calls += 1
        if self.calls > 2:
            return {"role": "assistant", "content": "Both scripts finished."}
        return {"role": "assistant", "content": None, "tool_calls": [{
            "id": uuid.uuid4().hex, "type": "function", "function": {
                "name": "run_python_script", "arguments": json.dumps({"path": "counter.py"})}}]}


def test_allow_all_persists_only_for_selected_conversation_and_can_be_revoked(settings, skills):
    (settings.workspace / "counter.py").write_text(
        "from pathlib import Path\np=Path('counter.txt')\np.write_text((p.read_text() if p.exists() else '')+'x')\n")
    store = Store(settings.state_dir / "runs.sqlite3")
    manager = RunManager(settings, store, skills, TwoExecutions)
    session = store.create_session()

    async def scenario():
        first = manager.start(session["id"], "Run twice")
        approval = await wait_approval(manager, first)
        with pytest.raises(HarnessError):
            manager.decide(first, "expired-id", True, True)
        assert not store.execution_allowed(session["id"])
        manager.decide(first, approval, True, True)
        await asyncio.wait_for(manager.tasks[first], 10)
        assert store.run(first)["status"] == "completed"
        assert len([e for e in store.run(first)["events"] if e["type"] == "approval_required"]) == 1
        assert store.execution_allowed(session["id"])
        assert (settings.workspace / "counter.txt").read_text() == "xx"

        reopened = Store(store.path)
        resumed = RunManager(settings, reopened, skills, TwoExecutions)
        second = resumed.start(session["id"], "Run twice again")
        await asyncio.wait_for(resumed.tasks[second], 10)
        assert reopened.run(second)["status"] == "completed"
        assert not any(e["type"] == "approval_required" for e in reopened.run(second)["events"])
        assert (settings.workspace / "counter.txt").read_text() == "xxxx"

        other = reopened.create_session()
        third = resumed.start(other["id"], "A separate conversation")
        other_approval = await wait_approval(resumed, third)
        resumed.decide(third, other_approval, False)
        await resumed.tasks[third]
        assert not reopened.execution_allowed(other["id"])

        reopened.set_execution_approval(session["id"], False)
        fourth = resumed.start(session["id"], "Approval is required again")
        restored_approval = await wait_approval(resumed, fourth)
        resumed.decide(fourth, restored_approval, False)
        await resumed.tasks[fourth]
        assert reopened.run(fourth)["error"]["code"] == "approval_denied"
        assert (settings.workspace / "counter.txt").read_text() == "xxxx"

    asyncio.run(scenario())


def test_allow_execution_does_not_approve_file_writes_under_all_policy(settings, skills):
    settings.execution.approval_mode = "all"
    store = Store(settings.state_dir / "runs.sqlite3")
    manager = RunManager(settings, store, skills)
    session = store.create_session()
    store.set_execution_approval(session["id"], True)

    async def scenario():
        run = manager.start(session["id"], "demo")
        approval = await wait_approval(manager, run)
        event = next(e for e in store.run(run)["events"] if e["type"] == "approval_required")
        assert event["data"]["kind"] == "write"
        with pytest.raises(HarnessError) as error:
            manager.decide(run, approval, True, True)
        assert error.value.code == "invalid_approval_scope"
        manager.decide(run, approval, False)
        await manager.tasks[run]
        assert not (settings.workspace / "demo_hello.py").exists()

    asyncio.run(scenario())


def test_migration_keeps_existing_messages_and_defaults_to_manual_approval(tmp_path):
    path = tmp_path / "old.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY,title TEXT NOT NULL,created REAL NOT NULL,messages TEXT NOT NULL)")
        db.execute("INSERT INTO sessions VALUES (?,?,?,?)", ("existing", "Keep this chat", 1, '[{"role":"user","content":"Hello"}]'))
    store = Store(path)
    assert store.session("existing")["messages"][0]["content"] == "Hello"
    assert not store.execution_allowed("existing")
    created = store.create_session("New chat")
    assert not store.execution_allowed(created["id"])
    store.set_execution_approval("existing", True)
    assert Store(path).execution_allowed("existing")


def test_reset_endpoint_cannot_grant_permissions_without_pending_approval(settings):
    with client_for(settings.root) as client:
        session = client.post("/api/sessions", json={"title": "Chat"}).json()
        path = f'/api/sessions/{session["id"]}/execution-approval'
        assert client.post(path, json={"allow_all": True}).status_code == 400
        client.app.state.store.set_execution_approval(session["id"], True)
        assert client.post(path, json={"allow_all": False}).json()["allow_all_execution"] is False
        assert not client.app.state.store.execution_allowed(session["id"])
