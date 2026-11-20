"""Build a source-only BAT Agent release. Never includes local runtime state."""
import hashlib
import json
from pathlib import Path
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = (
    "README.md", "COPILOT_SETUP.md", "SECURITY.md", "CHANGELOG.md",
    "pyproject.toml", "uv.lock", ".python-version", ".gitignore", ".gitattributes",
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def collect():
    paths = {ROOT / name for name in ROOT_FILES}
    paths.update((ROOT / "config").glob("*.yaml.example"))
    paths.add(ROOT / "workspace/README.md")
    paths.add(ROOT / "skills/local-coding/SKILL.md")
    extensions = {".py", ".md", ".html", ".css", ".js", ".cjs", ".mjs", ".json", ".txt"}
    for directory in ("agent_harness", "docs", "scripts", "web"):
        paths.update(p for p in (ROOT / directory).rglob("*")
                     if p.is_file() and p.suffix in extensions
                     and not any(part.startswith(".") or part in ("__pycache__", "node_modules")
                                 for part in p.relative_to(ROOT).parts))
    payloads = {}
    for path in sorted(paths):
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            raise ValueError("Refusing a linked or external source file.")
        payloads[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    return payloads


def main():
    payloads = collect()
    manifest = {name: digest(data) for name, data in payloads.items()}
    manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode()
    (ROOT / "SOURCE-MANIFEST.json").write_bytes(manifest_bytes)
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    archive = ROOT.parent / ("bat-agent-v" + version + ".zip")
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as output:
        for name, data in payloads.items():
            output.writestr("BAT-Agent/" + name, data)
        output.writestr("BAT-Agent/SOURCE-MANIFEST.json", manifest_bytes)
    with zipfile.ZipFile(archive) as check:
        assert check.testzip() is None
        for name, expected in manifest.items():
            assert digest(check.read("BAT-Agent/" + name)) == expected, name
        assert len(check.namelist()) == len(manifest) + 1
    checksum = digest(archive.read_bytes())
    archive.with_suffix(".zip.sha256").write_text(checksum + "  " + archive.name + "\n", encoding="ascii")
    print(json.dumps({"archive": str(archive), "source_files": len(manifest),
                      "bytes": archive.stat().st_size, "sha256": checksum}, ensure_ascii=False))


if __name__ == "__main__":
    main()
