"""Build and verify a source-only archive of this baseline. Never includes local run state."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.3.0"
PREFIX = "agent-harness-baseline"
ROOT_FILES = (
    "README.md", "README.zh-CN.md", "AGENTS.md", "SECURITY.md", "CHANGELOG.md",
    "pyproject.toml", "uv.lock", ".python-version", ".gitignore",
)
def digest(data):
    return hashlib.sha256(data).hexdigest()

def main():
    paths = {ROOT / name for name in ROOT_FILES}
    paths.update((ROOT / "config").glob("*.yaml.example"))
    paths.add(ROOT / "workspace/README.md")
    paths.add(ROOT / "skills/local-coding/SKILL.md")
    extensions = {".py", ".md", ".html", ".css", ".js", ".cjs"}
    for directory in ("agent_harness", "docs", "scripts"):
        paths.update(p for p in (ROOT / directory).rglob("*")
                     if p.is_file() and p.suffix in extensions
                     and not any(part.startswith(".") or part == "__pycache__"
                                 for part in p.relative_to(ROOT).parts))
    payloads = {}
    for path in sorted(paths):
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            raise ValueError(f"Refusing link or external file: {path.name}")
        payloads[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    manifest = {name:digest(data) for name,data in payloads.items()}
    archive = ROOT.parent / f"{PREFIX}-v{VERSION}.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as output:
        for name, data in payloads.items():
            output.writestr(f"{PREFIX}/{name}", data)
        output.writestr(f"{PREFIX}/SOURCE-MANIFEST.json",
                        json.dumps(manifest, ensure_ascii=False, indent=2)+"\n")
    with zipfile.ZipFile(archive) as check:
        assert check.testzip() is None
        for name, expected in manifest.items():
            assert digest(check.read(f"{PREFIX}/{name}")) == expected, name
        assert len(check.namelist()) == len(manifest)+1
    checksum = digest(archive.read_bytes())
    archive.with_suffix(".zip.sha256").write_text(
        f"{checksum}  {archive.name}\n", encoding="ascii")
    print(json.dumps({"archive":str(archive), "source_files":len(manifest),
                      "bytes":archive.stat().st_size, "sha256":checksum},
                     ensure_ascii=False))

if __name__ == "__main__":
    main()
