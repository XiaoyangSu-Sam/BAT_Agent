import difflib
import json
import os
import tempfile
import uuid
from .paths import inside, text_file, digest, walk
from ..errors import HarnessError

class FileTools:
    def __init__(self, root, state):
        self.root, self.state = root, state

    def list_files(self, path="."):
        base = inside(self.root, path, True)
        if not base.is_dir():
            raise HarnessError("not_directory", "Expected a directory.", "tool")
        paths = [p.relative_to(self.root).as_posix() for p in walk(base)]
        return {"files": paths[:500], "possibly_truncated": len(paths) >= 500,
                "scan_limit": 2000}

    def read_file(self, path, start_line=1, end_line=300):
        p = inside(self.root, path, True)
        data, value = text_file(p)
        lines = value.splitlines()
        if end_line < start_line or end_line-start_line > 1000:
            raise HarnessError("invalid_range", "Read at most 1001 lines with end_line >= start_line.", "tool")
        return {"path": p.relative_to(self.root).as_posix(), "sha256": digest(data),
                "total_lines": len(lines), "start_line": start_line,
                "content": "\n".join(lines[start_line-1:end_line])[:30000]}

    def search_files(self, query, path="."):
        base = inside(self.root, path, True)
        if not base.is_dir():
            raise HarnessError("not_directory", "Expected a directory.", "tool")
        matches = []
        for p in walk(base):
            try:
                _, value = text_file(p)
            except HarnessError:
                continue
            for n, line in enumerate(value.splitlines(), 1):
                if query in line:
                    matches.append({"path": p.relative_to(self.root).as_posix(),
                                    "line": n, "text": line[:500]})
                    if len(matches) == 100:
                        return {"matches": matches, "truncated": True}
        return {"matches": matches, "truncated": False, "scan_limit": 2000}

    def write_file(self, path, content, expected_sha256=""):
        p = inside(self.root, path)
        before, old = text_file(p) if p.exists() else (b"", "")
        actual = digest(before) if p.exists() else ""
        if actual != expected_sha256:
            raise HarnessError("file_conflict", "File changed or overwrite lacks the current SHA256. Read it again.", "tool")
        after = content.encode("utf-8")
        if len(after) > 1_000_000:
            raise HarnessError("file_too_large", "Write exceeds 1 MB.", "tool")
        rel = p.relative_to(self.root).as_posix()
        change_id = uuid.uuid4().hex
        diff = "".join(difflib.unified_diff(old.splitlines(True), content.splitlines(True),
                                          fromfile=rel+" (before)", tofile=rel+" (after)"))
        backup = self.state / "changes"
        backup.mkdir(parents=True, exist_ok=True)
        (backup / (change_id+".json")).write_text(json.dumps(
            {"path": rel, "existed": p.exists(), "before": old, "before_sha256": actual,
             "after_sha256": digest(after)}, ensure_ascii=False), encoding="utf-8")
        p.parent.mkdir(parents=True, exist_ok=True)
        temp = None
        try:
            with tempfile.NamedTemporaryFile(dir=p.parent, delete=False) as f:
                temp = f.name
                f.write(after)
            os.replace(temp, p)
        finally:
            if temp and os.path.exists(temp):
                os.unlink(temp)
        return {"path": rel, "sha256": digest(after), "change_id": change_id,
                "diff": diff[:24000], "diff_truncated": len(diff)>24000,
                "bytes_written": len(after)}

    def edit_file(self, path, old_text, new_text, expected_sha256):
        p = inside(self.root, path, True)
        _, value = text_file(p)
        # read_file exposes logical lines with LF; preserve uniform Windows CRLF on edits.
        if "\r\n" in value and "\n" not in value.replace("\r\n", ""):
            old_text = old_text.replace("\r\n", "\n").replace("\n", "\r\n")
            new_text = new_text.replace("\r\n", "\n").replace("\n", "\r\n")
        if not old_text or value.count(old_text) != 1:
            raise HarnessError("ambiguous_edit", "old_text must match exactly once.", "tool")
        return self.write_file(path, value.replace(old_text, new_text, 1), expected_sha256)

