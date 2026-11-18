"""Executed only as an approved child process; uses this interpreter's kernel."""
import json
import os
import sys
import tempfile
from pathlib import Path

def main():
    try:
        import nbformat
        from nbclient import NotebookClient
    except ImportError:
        print("Notebook dependencies missing. Install with: uv sync --extra notebook", file=sys.stderr)
        return 2
    source, output, workspace, timeout = sys.argv[1:]
    nb = nbformat.read(source, as_version=4)
    with tempfile.TemporaryDirectory(prefix="harness-kernel-") as temp:
        kernel = Path(temp) / "kernels/harness-local"
        kernel.mkdir(parents=True)
        kernel.joinpath("kernel.json").write_text(json.dumps({
            "argv":[sys.executable,"-m","ipykernel_launcher","-f","{connection_file}"],
            "display_name":"Harness local Python","language":"python"}), encoding="utf-8")
        os.environ["JUPYTER_PATH"] = temp + os.pathsep + os.environ.get("JUPYTER_PATH","")
        try:
            NotebookClient(nb, timeout=int(timeout), kernel_name="harness-local",
                           resources={"metadata":{"path":workspace}}).execute()
        finally:
            nbformat.write(nb, output)
    print("Executed notebook saved: " + str(Path(output).name))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
