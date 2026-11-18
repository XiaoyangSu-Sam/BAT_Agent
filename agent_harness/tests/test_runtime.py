import asyncio
import json
import time
from agent_harness.store import Store
from agent_harness.runtime.manager import RunManager
from agent_harness.runtime.context import repair_incomplete
from agent_harness.config import ModelConfig

async def wait_approval(manager, run_id):
    for _ in range(500):
        if run_id in manager.approvals:
            return manager.approvals[run_id][0]
        if manager.tasks[run_id].done():
            raise AssertionError(manager.store.run(run_id))
        await asyncio.sleep(.01)
    raise AssertionError("No approval appeared")

def test_real_demo_and_second_turn(settings, skills):
    store=Store(settings.state_dir/"runs.sqlite3")
    manager=RunManager(settings,store,skills)
    session=store.create_session()
    async def scenario():
        for _ in range(2):
            key=manager.start(session["id"],"demo")
            approval=await wait_approval(manager,key)
            assert not settings.workspace.joinpath("demo_result.json").exists() or _==1
            manager.decide(key,approval,True)
            await asyncio.wait_for(manager.tasks[key],10)
            assert store.run(key)["status"]=="completed",store.run(key)
            assert json.loads(settings.workspace.joinpath("demo_result.json").read_text())["sum"]==15
    asyncio.run(scenario())
    events=store.run(key if False else store.runs(session["id"])[0]["id"])["events"]
    assert any(e["type"]=="tool_result" and e["data"]["name"]=="run_python_script" for e in events)

def test_denial_stops_without_process(settings, skills):
    store=Store(settings.state_dir/"runs.sqlite3")
    manager=RunManager(settings,store,skills)
    async def scenario():
        key=manager.start(store.create_session()["id"],"demo")
        approval=await wait_approval(manager,key)
        manager.decide(key,approval,False)
        await manager.tasks[key]
        assert store.run(key)["status"]=="failed"
        assert store.run(key)["error"]["code"]=="approval_denied"
        assert not settings.workspace.joinpath("demo_result.json").exists()
    asyncio.run(scenario())

def test_cancel_approval_and_repair(settings, skills):
    store=Store(settings.state_dir/"runs.sqlite3")
    manager=RunManager(settings,store,skills)
    session=store.create_session()
    async def scenario():
        key=manager.start(session["id"],"demo")
        await wait_approval(manager,key)
        await manager.cancel(key)
        assert store.run(key)["status"]=="cancelled"
        fixed=repair_incomplete(store.session(session["id"])["messages"])
        assert "execution_unknown" in fixed[-1]["content"]
        assert not settings.workspace.joinpath("demo_result.json").exists()
    asyncio.run(scenario())

def test_immediate_cancel(settings, skills):
    store=Store(settings.state_dir/"runs.sqlite3")
    manager=RunManager(settings,store,skills)
    async def scenario():
        key=manager.start(store.create_session()["id"],"demo")
        await manager.cancel(key)
        assert store.run(key)["status"]=="cancelled"
    asyncio.run(scenario())

def test_step_limit(settings, skills):
    settings.execution.max_steps=1
    store=Store(settings.state_dir/"runs.sqlite3")
    manager=RunManager(settings,store,skills)
    async def scenario():
        key=manager.start(store.create_session()["id"],"demo")
        await manager.tasks[key]
        assert store.run(key)["error"]["code"]=="step_limit"
    asyncio.run(scenario())

def test_restart_marks_interrupted(settings):
    path=settings.state_dir/"runs.sqlite3"
    store=Store(path);session=store.create_session();key=store.create_run(session["id"],"model")
    store.status(key,"awaiting_approval")
    reopened=Store(path)
    assert reopened.run(key)["status"]=="interrupted"

def test_explicit_json_tool_protocol(settings, skills):
    class JsonModel:
        def __init__(self,config):
            self.n=0
        async def complete(self,messages,schemas,emit,tools=True):
            self.n+=1
            if self.n==1:
                content=json.dumps({"action":"tool","name":"write_file",
                                    "arguments":{"path":"json-mode.txt","content":"actual output"}})
            else:
                assert messages[-1]["role"]=="user" and messages[-1]["content"].startswith("TOOL_RESULT")
                content=json.dumps({"action":"final","content":"File created."})
            return {"role":"assistant","content":content}
    settings.models={"json":ModelConfig(endpoint="http://mock/v1",tool_mode="json")}
    settings.default_model="json"
    store=Store(settings.state_dir/"runs.sqlite3")
    manager=RunManager(settings,store,skills,JsonModel)
    async def scenario():
        key=manager.start(store.create_session()["id"],"write a file")
        await manager.tasks[key]
        assert store.run(key)["status"]=="completed",store.run(key)
        assert settings.workspace.joinpath("json-mode.txt").read_text()=="actual output"
    asyncio.run(scenario())
