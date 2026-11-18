import asyncio
import pytest
from agent_harness.runtime.processes import ProcessTools

def test_notebook_real_execution(settings, skills):
    nbformat = pytest.importorskip("nbformat")
    pytest.importorskip("nbclient")
    notebook=nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(
        "from pathlib import Path\nPath('notebook-proof.txt').write_text(str(6*7))\nprint(6*7)")])
    source=settings.workspace/"sample.ipynb"
    nbformat.write(notebook,source)
    before=source.read_bytes()
    result=asyncio.run(ProcessTools(settings.workspace,settings.execution,skills).run_notebook("sample.ipynb"))
    assert result["ok"],result
    assert settings.workspace.joinpath("notebook-proof.txt").read_text()=="42"
    assert source.read_bytes()==before
    output=nbformat.read(settings.workspace/result["output_path"],as_version=4)
    assert "42" in output.cells[0].outputs[0].text
