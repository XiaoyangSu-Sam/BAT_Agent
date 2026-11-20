import hashlib
import importlib.util
import json
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location("bat_deploy", Path(__file__).resolve().parents[2] / "scripts/deploy.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write(root, name, content):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def release(tmp_path):
    source = tmp_path / "release"
    source.mkdir()
    contents = {
        "agent_harness/__main__.py": "# new app",
        "scripts/check_environment.py": "# checker",
        "pyproject.toml": "# new metadata",
        "docs/setup.md": "new instructions",
        ".gitignore": ".harness/\nconfig/*.yaml\n",
        ".gitattributes": "* text=auto\n",
        "skills/local-coding/SKILL.md": "# sample",
        "workspace/README.md": "# sample workspace",
        "config/model.yaml.example": 'endpoint: ""',
    }
    for name, content in contents.items():
        write(source, name, content)
    manifest = {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in contents}
    write(source, "SOURCE-MANIFEST.json", json.dumps(manifest))
    target = tmp_path / "existing"
    target.mkdir()
    for name, content in {
        "agent_harness/obsolete.py": "# stale module",
        "docs/private-note.md": "local note",
        ".git/config": "git state",
        ".github/policy.md": "company policy",
        "AGENTS.md": "project instructions",
        ".venv/marker": "environment",
        "skills/private/SKILL.md": "# private skill",
        "skills/local-coding/SKILL.md": "# customized",
        "workspace/README.md": "user workspace",
        "config/model.yaml": "local connection",
        ".harness/runs.sqlite3": "old state",
        ".gitignore": "company-custom/\n",
        "unrelated.py": "# business application",
    }.items():
        write(target, name, content)
    return source, target


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_preview_does_not_mutate(release):
    source, target = release
    before = snapshot(target)
    result = module.deploy(source, target, reset_local=True)
    assert not result["applied"]
    assert snapshot(target) == before
    assert not list(target.parent.glob("*.bat-backup-*"))


def test_replacement_preserves_data_and_backs_up_old_code(release):
    source, target = release
    before = snapshot(target)
    result = module.deploy(source, target, apply=True)
    backup = Path(result["backup"])
    assert backup.parent == target.parent
    assert not (target / "agent_harness/obsolete.py").exists()
    assert (target / "agent_harness/__main__.py").is_file()
    assert (backup / "agent_harness/obsolete.py").read_bytes() == before[str(Path("agent_harness/obsolete.py"))]
    for name in [".git/config", ".github/policy.md", "AGENTS.md", ".venv/marker",
                 "skills/private/SKILL.md", "skills/local-coding/SKILL.md", "workspace/README.md",
                 "config/model.yaml", ".harness/runs.sqlite3", "unrelated.py"]:
        assert (target / name).read_bytes() == before[str(Path(name))]
    assert "company-custom/" in (target / ".gitignore").read_text()
    assert ".harness/" in (target / ".gitignore").read_text()
    assert (backup / "docs/private-note.md").is_file()
    assert json.loads((backup / "DEPLOYMENT.json").read_text())["status"] == "complete"


def test_fresh_configuration_is_archived(release):
    source, target = release
    result = module.deploy(source, target, apply=True, reset_local=True)
    backup = Path(result["backup"])
    for name in ("config/model.yaml", ".harness/runs.sqlite3"):
        assert not (target / name).exists()
        assert (backup / name).is_file()
    assert (target / "config/model.yaml.example").is_file()


def test_modified_source_refused_before_changes(release):
    source, target = release
    before = snapshot(target)
    write(source, "agent_harness/__main__.py", "# tampered")
    with pytest.raises(ValueError, match="integrity"):
        module.deploy(source, target, apply=True)
    assert snapshot(target) == before
    assert not list(target.parent.glob("*.bat-backup-*"))


@pytest.mark.parametrize("bad", ["../outside.py", "C:/outside.py", "agent_harness\\outside.py", ".git/config"])
def test_manifest_escape_refused(release, bad):
    source, target = release
    manifest = json.loads((source / "SOURCE-MANIFEST.json").read_text())
    manifest[bad] = "0" * 64
    write(source, "SOURCE-MANIFEST.json", json.dumps(manifest))
    with pytest.raises(ValueError):
        module.deploy(source, target, apply=True)


def test_source_inside_target_refused(release):
    source, target = release
    with pytest.raises(ValueError, match="outside"):
        module.deploy(target / "extracted", target)


def test_install_failure_rolls_back(release, monkeypatch):
    source, target = release
    before = snapshot(target)
    original = Path.rename
    def fail_on_scripts(path, destination):
        if ".bat-stage-" in str(path) and path.name == "scripts":
            raise PermissionError("simulated locked destination")
        return original(path, destination)
    monkeypatch.setattr(Path, "rename", fail_on_scripts)
    with pytest.raises(RuntimeError, match="rolled_back"):
        module.deploy(source, target, apply=True, reset_local=True)
    assert snapshot(target) == before


def test_destination_link_refused(release):
    source, target = release
    other = target.parent / "outside"
    other.mkdir()
    (target / "docs/private-note.md").unlink()
    (target / "docs").rmdir()
    try:
        (target / "docs").symlink_to(other, target_is_directory=True)
    except OSError:
        pytest.skip("Windows symlink privilege unavailable")
    with pytest.raises(ValueError, match="Links"):
        module.deploy(source, target, apply=True)
    assert list(other.iterdir()) == []
