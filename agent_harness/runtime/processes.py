import asyncio
import os
import signal
import sys
import uuid
from pathlib import Path
from .paths import inside
from ..errors import HarnessError

def child_environment():
    env = {k: v for k, v in os.environ.items()
           if not any(s in k.upper() for s in ("API_KEY", "TOKEN", "SECRET", "PASSWORD"))
           and not k.upper().startswith("LLM_")}
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env

async def stop_tree(proc):
    if os.name == "nt" and proc.returncode is None:
        try:
            killer = await asyncio.create_subprocess_exec("taskkill", "/PID", str(proc.pid), "/T", "/F",
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                creationflags=0x08000000)
            try:
                await asyncio.wait_for(killer.wait(), 5)
            except asyncio.TimeoutError:
                killer.kill()
                await killer.wait()
        except OSError:
            pass
    elif os.name != "nt":
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if proc.returncode is None:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
    try:
        await asyncio.wait_for(proc.wait(), 3)
    except asyncio.TimeoutError:
        # A detached descendant may retain inherited pipes; execute closes them below.
        pass

class ProcessTools:
    def __init__(self, workspace, config, skills):
        self.workspace, self.config, self.skills = workspace, config, skills

    async def execute(self, argv, cwd=None):
        if not argv or any("\x00" in a for a in argv):
            raise HarnessError("invalid_command", "Provide a nonempty argv array.", "tool")
        cwd = inside(self.workspace, cwd or ".", True)
        if not cwd.is_dir():
            raise HarnessError("invalid_cwd", "cwd must be a workspace directory.", "tool")
        kwargs = {"start_new_session": True} if os.name != "nt" else {"creationflags": 0x08000000}
        try:
            proc = await asyncio.create_subprocess_exec(*argv, cwd=cwd, env=child_environment(),
                stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE, **kwargs)
        except (OSError, ValueError) as exc:
            raise HarnessError("process_start_failed", "Cannot start command. Check executable, interpreter and dependencies.", "tool") from exc
        limit = self.config.max_output_chars
        buffers = [bytearray(), bytearray()]
        truncated = [False, False]
        async def collect(stream, index):
            while True:
                data = await stream.read(4096)
                if not data:
                    return
                remaining = max(0, limit-len(buffers[index]))
                buffers[index].extend(data[:remaining])
                truncated[index] |= len(data) > remaining
        tasks = [asyncio.create_task(proc.wait()),
                 asyncio.create_task(collect(proc.stdout, 0)),
                 asyncio.create_task(collect(proc.stderr, 1))]
        completion = asyncio.gather(*tasks)
        timed_out, incomplete = False, False
        async def terminate():
            nonlocal incomplete
            await stop_tree(proc)
            try:
                await asyncio.wait_for(asyncio.shield(completion), 2)
            except asyncio.TimeoutError:
                incomplete = True
                completion.cancel()
                await asyncio.gather(completion, return_exceptions=True)
                # asyncio has no public Process.close(); close retained pipe handles.
                transport = getattr(proc, "_transport", None)
                if transport is not None:
                    transport.close()
        try:
            # The deadline covers process exit AND pipe EOF (including inherited pipes).
            await asyncio.wait_for(asyncio.shield(completion), self.config.timeout)
        except asyncio.TimeoutError:
            timed_out = True
            await terminate()
        except asyncio.CancelledError:
            await terminate()
            raise
        return {"exit_code": proc.returncode,
                "stdout": buffers[0].decode("utf-8", errors="replace"),
                "stderr": buffers[1].decode("utf-8", errors="replace"),
                "output_truncated": any(truncated) or incomplete,
                "output_incomplete": incomplete, "timed_out": timed_out,
                "ok": not timed_out and proc.returncode == 0}

    async def run_command(self, argv, cwd="."):
        return await self.execute(argv, cwd)

    def source(self, path, skill_id, suffix):
        p = self.skills.executable(skill_id, path, suffix) if skill_id else inside(self.workspace, path, True)
        if p.suffix != suffix or not p.is_file():
            raise HarnessError("invalid_script", f"Expected an existing {suffix} file.", "tool")
        return p

    async def run_python_script(self, path, args=None, skill_id=""):
        p = self.source(path, skill_id, ".py")
        return await self.execute([self.config.python(), "-u", str(p), *(args or [])])

    async def run_notebook(self, path, skill_id=""):
        p = self.source(path, skill_id, ".ipynb")
        output = inside(self.workspace, "notebook-results/"+uuid.uuid4().hex+".ipynb")
        output.parent.mkdir(parents=True, exist_ok=True)
        worker = Path(__file__).with_name("notebook_worker.py")
        result = await self.execute([self.config.python(), str(worker), str(p),
                                    str(output), str(self.workspace), str(int(self.config.timeout))])
        result["output_path"] = output.relative_to(self.workspace).as_posix() if output.exists() else None
        return result

