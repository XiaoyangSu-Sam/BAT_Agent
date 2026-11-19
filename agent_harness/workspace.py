"""Full-document editor operations, sharing the agent's file and conflict rules."""
import os
import tempfile
from pathlib import Path
import yaml
from .config import read_yaml
from .errors import HarnessError
from .runtime.files import FileTools
from .runtime.paths import inside, text_file, digest


def read_document(settings, path):
    target = inside(settings.workspace, path, True)
    data, content = text_file(target)
    return {"path": target.relative_to(settings.workspace).as_posix(),
            "content": content, "sha256": digest(data), "bytes": len(data),
            "bom": data.startswith(b'\xef\xbb\xbf'),
            "line_ending": "CRLF" if b'\r\n' in data and b'\n' not in data.replace(b'\r\n', b'') else "LF"}


def save_document(settings, path, content, expected_sha256):
    result = FileTools(settings.workspace, settings.state_dir).write_file(path, content, expected_sha256)
    return {**read_document(settings, path), "change_id": result["change_id"]}


def open_workspace(settings, path):
    target = Path(path).expanduser()
    if not target.is_absolute() or not target.is_dir():
        raise HarnessError("invalid_workspace", "Enter the absolute path of an existing folder.", "configuration")
    target = target.resolve()
    file = settings.root / "config/execution.yaml"
    values = read_yaml(file)
    values["workspace_root"] = str(target)
    file.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=file.parent, delete=False) as out:
        yaml.safe_dump(values, out, sort_keys=False)
        temp = out.name
    try:
        os.replace(temp, file)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    settings.execution.workspace_root = str(target)
    return settings.public()
