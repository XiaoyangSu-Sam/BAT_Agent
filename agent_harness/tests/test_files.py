import asyncio
import pytest
from agent_harness.errors import HarnessError
from agent_harness.runtime.files import FileTools
from agent_harness.runtime.tools import ToolRegistry
from agent_harness.runtime.processes import ProcessTools

def test_create_edit_and_conflict(settings):
    tools = FileTools(settings.workspace, settings.state_dir)
    first = tools.write_file("nested/main.py", "print(1)\n")
    read = tools.read_file("nested/main.py")
    assert read["content"] == "print(1)" and read["sha256"] == first["sha256"]
    edited = tools.edit_file("nested/main.py","print(1)","print(2)",read["sha256"])
    assert "+print(2)" in edited["diff"]
    with pytest.raises(HarnessError, match="File changed"):
        tools.write_file("nested/main.py", "lost changes", read["sha256"])
    assert settings.workspace.joinpath("nested/main.py").read_text() == "print(2)\n"
    assert len(list(settings.state_dir.joinpath("changes").glob("*.json"))) == 2

@pytest.mark.parametrize("path", ["../escape.py", ".git/config", ".env", ".env.local", "private.key"])
def test_paths_denied(settings, path):
    with pytest.raises(HarnessError):
        FileTools(settings.workspace, settings.state_dir).write_file(path,"bad")
    assert not settings.root.joinpath("escape.py").exists()

def test_links_denied(settings, tmp_path):
    target = tmp_path / "outside.txt"
    target.write_text("outside")
    link = settings.workspace / "link.txt"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("OS does not grant symlink creation")
    with pytest.raises(HarnessError):
        FileTools(settings.workspace, settings.state_dir).read_file("link.txt")

def test_search_and_unique_edit(settings):
    tools = FileTools(settings.workspace, settings.state_dir)
    created = tools.write_file("x.txt","same\nsame\nneedle\n")
    assert tools.search_files("needle")["matches"][0]["line"] == 3
    with pytest.raises(HarnessError, match="exactly once"):
        tools.edit_file("x.txt","same","x",created["sha256"])
    assert "x.txt" in tools.list_files()["files"]

def test_skill_resource_and_execution_paths(settings, skills):
    root = settings.root / "skills/local-coding"
    root.joinpath("scripts").mkdir()
    root.joinpath("scripts/check.py").write_text("print(6 * 7)")
    assert skills.read_skill("local-coding")["skill_id"] == "local-coding"
    assert "print" in skills.read_skill_resource("local-coding","scripts/check.py")["content"]
    with pytest.raises(HarnessError):
        skills.read_skill_resource("local-coding","../../../../outside")
    with pytest.raises(HarnessError):
        skills.executable("local-coding","SKILL.md",".py")
    result = asyncio.run(ProcessTools(settings.workspace, settings.execution, skills).run_python_script(
        "scripts/check.py", skill_id="local-coding"))
    assert result["exit_code"] == 0 and "42" in result["stdout"]

def test_tool_schema_rejects_unknown_fields(settings, skills):
    registry = ToolRegistry(settings, skills)
    with pytest.raises(HarnessError):
        registry.validate("write_file",{"path":"x","content":"x","arbitrary":True})
    with pytest.raises(HarnessError):
        registry.validate("run_command",{"argv":"python"})
    with pytest.raises(HarnessError):
        registry.validate("invented",{})

def test_process_output_limit_and_failure(settings, skills):
    settings.execution.max_output_chars = 1000
    p = ProcessTools(settings.workspace,settings.execution,skills)
    settings.workspace.joinpath("fail.py").write_text("import sys\nprint('x'*100000)\nprint('problem',file=sys.stderr)\nsys.exit(7)")
    result = asyncio.run(p.run_python_script("fail.py"))
    assert result["exit_code"] == 7 and not result["ok"]
    assert len(result["stdout"]) <= 1000 and result["output_truncated"]
    assert "problem" in result["stderr"]

def test_timeout(settings, skills):
    settings.execution.timeout = 0.1
    settings.workspace.joinpath("slow.py").write_text("import time\ntime.sleep(30)")
    result = asyncio.run(ProcessTools(settings.workspace,settings.execution,skills).run_python_script("slow.py"))
    assert result["timed_out"] and not result["ok"]

def test_credential_not_in_child(settings, skills, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "DO_NOT_LEAK")
    settings.workspace.joinpath("env.py").write_text("import os\nprint(os.environ.get('LLM_API_KEY','absent'))")
    result = asyncio.run(ProcessTools(settings.workspace,settings.execution,skills).run_python_script("env.py"))
    assert result["stdout"].strip() == "absent"


def test_multiline_edit_preserves_windows_newlines(settings):
    tools = FileTools(settings.workspace, settings.state_dir)
    path = settings.workspace / "windows.py"
    path.write_bytes(b"first\r\nsecond\r\nthird\r\n")
    read = tools.read_file("windows.py", 1, 2)
    tools.edit_file("windows.py", read["content"], "changed\nsecond", read["sha256"])
    assert path.read_bytes() == b"changed\r\nsecond\r\nthird\r\n"

def test_cancel_running_process_tree(settings, skills):
    settings.workspace.joinpath("child.py").write_text(
        "from pathlib import Path\nimport time\n"
        "Path('child-ready').write_text('ready')\n"
        "time.sleep(1)\nPath('child-survived').write_text('bad')\n")
    settings.workspace.joinpath("parent.py").write_text(
        "import subprocess, sys, time\n"
        "subprocess.Popen([sys.executable, 'child.py'])\ntime.sleep(30)\n")
    async def scenario():
        task = asyncio.create_task(
            ProcessTools(settings.workspace, settings.execution, skills).run_python_script("parent.py"))
        try:
            for _ in range(500):
                if settings.workspace.joinpath("child-ready").exists():
                    break
                if task.done():
                    raise AssertionError(await task)
                await asyncio.sleep(.01)
            else:
                raise AssertionError("Child did not start")
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 10)
            await asyncio.sleep(1.2)
            assert not settings.workspace.joinpath("child-survived").exists()
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
    asyncio.run(scenario())
