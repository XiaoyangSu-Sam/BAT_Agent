import hashlib
import os
from pathlib import Path
from ..errors import HarnessError

SKIP = {".git", ".venv", "node_modules", "__pycache__", ".harness", ".pytest_cache"}
def sensitive(path):
    return any(p in SKIP or p.lower().startswith(".env") or
               p.lower().endswith((".pem", ".key", ".pfx")) for p in Path(path).parts)

def inside(root, name, must_exist=False):
    root = Path(root).resolve()
    raw = Path(name)
    candidate = raw if raw.is_absolute() else root / raw
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root) or sensitive(resolved.relative_to(root)):
        raise HarnessError("path_denied", "Path is outside the workspace or is a protected path.", "tool")
    # Reject links/junctions even if they lead back inside the workspace.
    for part in [candidate, *candidate.parents]:
        if part == root or not part.is_relative_to(root):
            break
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise HarnessError("path_denied", "Links and junctions are not accepted by file tools.", "tool")
    if must_exist and not resolved.exists():
        raise HarnessError("file_not_found", "Requested file does not exist.", "tool")
    return resolved

def text_file(path):
    if not path.is_file():
        raise HarnessError("not_a_file", "Expected a regular file.", "tool")
    if path.stat().st_size > 1_000_000:
        raise HarnessError("file_too_large", "File exceeds the 1 MB text-tool limit.", "tool")
    try:
        data = path.read_bytes()
        value = data.decode("utf-8-sig")
        if "\x00" in value:
            raise ValueError("binary")
        return data, value
    except (UnicodeError, ValueError) as exc:
        raise HarnessError("not_text", "File tools accept UTF-8 text only.", "tool") from exc

def digest(data):
    return hashlib.sha256(data).hexdigest()

def walk(root):
    count = 0
    for base, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not sensitive(d) and not Path(base, d).is_symlink()
                         and not (hasattr(Path(base,d), "is_junction") and Path(base,d).is_junction()))
        for name in sorted(names):
            path = Path(base, name)
            if sensitive(name) or path.is_symlink():
                continue
            count += 1
            if count > 2000:
                return
            yield path
