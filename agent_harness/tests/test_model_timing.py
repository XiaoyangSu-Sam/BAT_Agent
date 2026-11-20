import asyncio
import json
from types import SimpleNamespace

import pytest
from agent_harness.errors import HarnessError
from agent_harness.runtime import turn
from agent_harness.runtime.context import wire_messages
from agent_harness.runtime.manager import RunManager
from agent_harness.store import Store


def test_model_timing_excludes_approval_and_survives_history(settings, skills, monkeypatch):
    clock = [10.0]
    monkeypatch.setattr(turn, "time", SimpleNamespace(monotonic=lambda: clock[0], time=lambda: 1000.0))
    (settings.workspace / "sample.py").write_text("print(42)")

    class Model:
        def __init__(self, config): self.calls = 0
        async def complete(self, messages, schemas, emit, tools=True):
            self.calls += 1
            clock[0] += 0.25
            if self.calls == 1:
                return {"role": "assistant", "content": None, "tool_calls": [{"id": "timed-call", "type": "function",
                    "function": {"name": "run_python_script", "arguments": json.dumps({"path": "sample.py"})}}]}
            assert all("_model_elapsed_ms" not in m for m in messages)
            return {"role": "assistant", "content": "Finished"}

    store = Store(settings.state_dir / "timing.sqlite3")
    manager = RunManager(settings, store, skills, Model)
    session = store.create_session()

    async def scenario():
        key = manager.start(session["id"], "Run sample")
        for _ in range(500):
            if key in manager.approvals: break
            await asyncio.sleep(0.01)
        assert key in manager.approvals
        clock[0] += 100  # User time must not be counted as model time.
        manager.decide(key, manager.approvals[key][0], True)
        await manager.tasks[key]
        result = store.run(key)
        assert result["status"] == "completed"
        finished = [e["data"] for e in result["events"] if e["type"] == "model_wait_finished"]
        assert [e["elapsed_ms"] for e in finished] == [250, 250]
        assert all(e["outcome"] == "received" for e in finished)
    asyncio.run(scenario())
    reopened = Store(settings.state_dir / "timing.sqlite3")
    messages = reopened.session(session["id"])["messages"]
    assert [m["_model_elapsed_ms"] for m in messages if m["role"] == "assistant"] == [250, 250]
    for mode in ("native", "json", "disabled"):
        assert all("_model_elapsed_ms" not in m for m in wire_messages(messages, mode))


@pytest.mark.parametrize("outcome", ["failed", "cancelled"])
def test_model_timing_finishes_on_failure_or_stop(settings, skills, outcome):
    async def scenario():
        entered = asyncio.Event()
        class Model:
            def __init__(self, config): pass
            async def complete(self, messages, schemas, emit, tools=True):
                entered.set()
                if outcome == "failed": raise HarnessError("test_failure", "Fixture failure", "model")
                await asyncio.Event().wait()
        store = Store(settings.state_dir / "stop-timing.sqlite3")
        manager = RunManager(settings, store, skills, Model)
        key = manager.start(store.create_session()["id"], "Request")
        await entered.wait()
        if outcome == "cancelled": await manager.cancel(key)
        await manager.tasks[key]
        result = store.run(key)
        assert result["status"] == outcome
        finished = [e["data"] for e in result["events"] if e["type"] == "model_wait_finished"]
        assert len(finished) == 1 and finished[0]["outcome"] == outcome
        assert finished[0]["elapsed_ms"] >= 0
    asyncio.run(scenario())
