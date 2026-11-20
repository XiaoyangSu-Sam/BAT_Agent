"""Install a verified source release into an existing project. Dry-run by default."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from datetime import datetime, timezone
import uuid

MANAGED = ("agent_harness", "docs", "scripts", "web")
ROOT_FILES = {
    "README.md", "README.zh-CN.md", "SECURITY.md", "CHANGELOG.md",
    "COPILOT_SETUP.md", "pyproject.toml", "uv.lock", ".python-version",
    "SOURCE-MANIFEST.json",
}
MERGE_FILES = (".gitignore", ".gitattributes")
RESET = ("config/model.yaml", "config/environment.yaml", "config/execution.yaml", ".harness")


def no_links(path):
    """Check lexical ancestors as well as the path itself before resolving it."""
    path = Path(os.path.abspath(path))
    for item in (path, *path.parents):
        if item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction()):
            raise ValueError("Links/junctions are not supported in deployment paths.")
        if item.exists():
            stat = item.lstat()
            if getattr(stat, "st_file_attributes", 0) & 0x400:
                raise ValueError("Reparse points are not supported in deployment paths.")
    return path


def contained(root, relative):
    candidate = no_links(root / relative)
    if not candidate.resolve().is_relative_to(root.resolve()) or candidate == root:
        raise ValueError("Deployment path leaves its intended directory.")
    return candidate


def check_tree(path):
    no_links(path)
    if path.is_dir():
        for current, dirs, files in os.walk(path, followlinks=False):
            for name in dirs + files:
                no_links(Path(current) / name)


def permitted(name):
    p = PurePosixPath(name)
    if name in ROOT_FILES | set(MERGE_FILES):
        return True
    if p.parts[0] in MANAGED:
        return all(not part.startswith(".") and part not in ("__pycache__", "node_modules")
                   for part in p.parts)
    return (name.startswith("config/") and len(p.parts) == 2 and name.endswith(".yaml.example")
            or name in ("workspace/README.md", "skills/local-coding/SKILL.md"))


def verify_source(source):
    no_links(source)
    manifest_path = contained(source, "SOURCE-MANIFEST.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not manifest:
        raise ValueError("Missing or empty source manifest.")
    for name, expected in manifest.items():
        p = PurePosixPath(name)
        if (not isinstance(name, str) or "\\" in name or ":" in name or p.is_absolute()
                or ".." in p.parts or not permitted(name) or str(p) != name):
            raise ValueError("Unexpected path in source manifest.")
        file = contained(source, name)
        if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != expected:
            raise ValueError("Source integrity check failed: " + name)
    required = {"agent_harness/__main__.py", "pyproject.toml", "scripts/check_environment.py"}
    if not required.issubset(manifest):
        raise ValueError("Source manifest is incomplete.")
    return manifest


def deploy(source, target, apply=False, reset_local=False):
    source = no_links(source).resolve()
    target = no_links(target).resolve()
    if not target.is_dir() or target == Path(target.anchor):
        raise ValueError("Destination must be an existing project directory, not a drive root.")
    if source.is_relative_to(target) or target.is_relative_to(source):
        raise ValueError("Extract the release outside the destination project.")
    manifest = verify_source(source)
    replace = [d for d in MANAGED if any(n.startswith(d + "/") for n in manifest)]
    replace += sorted(ROOT_FILES.intersection(manifest.keys() | {"SOURCE-MANIFEST.json"}))
    replace += [name for name in MERGE_FILES if name in manifest]
    replace += sorted(n for n in manifest if n.startswith("config/"))
    seeds = sorted(n for n in manifest if n.startswith(("skills/", "workspace/"))
                   and not contained(target, n).exists())
    reset = list(RESET) if reset_local else []
    # Preflight every touched existing tree. Existing private Skills are never traversed.
    for name in replace + seeds + reset:
        check_tree(contained(target, name))
    info = {"target": str(target), "replace": replace, "seed_if_missing": seeds,
            "archive_local": reset, "applied": False}
    if not apply:
        return info
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = no_links(target.parent / (target.name + ".bat-backup-" + stamp + "-" + uuid.uuid4().hex[:8]))
    backup.mkdir()
    backup = backup.resolve()
    stage = Path(tempfile.mkdtemp(prefix=target.name + ".bat-stage-", dir=target.parent)).resolve()
    no_links(stage)
    saved, installed, made_dirs = [], [], []
    record = {"target": str(target), "saved": saved, "installed": installed, "status": "staging"}
    def journal():
        (backup / "DEPLOYMENT.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    def make_parents(dest):
        missing = []
        parent = dest.parent
        while parent != target and not parent.exists():
            contained(target, parent.relative_to(target))
            missing.append(parent)
            parent = parent.parent
        for folder in reversed(missing):
            folder.mkdir()
            made_dirs.append(folder)
    try:
        for name in manifest:
            out = contained(stage, name)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(contained(source, name).read_bytes())
        shutil.copyfile(source / "SOURCE-MANIFEST.json", stage / "SOURCE-MANIFEST.json")
        verify_source(stage)
        for name in MERGE_FILES:
            dest = contained(target, name)
            if name in manifest and dest.is_file():
                old = dest.read_text(encoding="utf-8")
                additions = [line for line in (stage / name).read_text(encoding="utf-8").splitlines()
                             if line not in old.splitlines()]
                (stage / name).write_text(old.rstrip("\n") + "\n" + "\n".join(additions) + "\n", encoding="utf-8")
        record["status"] = "applying"
        journal()
        for name in replace + reset:
            dest = contained(target, name)
            if dest.exists():
                saved_path = contained(backup, name)
                saved_path.parent.mkdir(parents=True, exist_ok=True)
                dest.rename(saved_path)
                saved.append(name)
                journal()
        for name in replace + seeds:
            src, dest = contained(stage, name), contained(target, name)
            if not src.exists():
                continue
            make_parents(dest)
            src.rename(dest)
            installed.append(name)
            journal()
        record["status"] = "complete"
        journal()
    except Exception as error:
        failures = []
        for name in reversed(installed):
            try:
                dest = contained(target, name)
                check_tree(dest)
                if dest.is_dir():
                    shutil.rmtree(dest)
                elif dest.exists():
                    dest.unlink()
            except Exception:
                failures.append(name)
        for name in reversed(saved):
            try:
                old, dest = contained(backup, name), contained(target, name)
                dest.parent.mkdir(parents=True, exist_ok=True)
                old.rename(dest)
            except Exception:
                failures.append(name)
        for folder in reversed(made_dirs):
            try:
                contained(target, folder.relative_to(target)).rmdir()
            except OSError:
                pass
        record["status"] = "rollback_incomplete" if failures else "rolled_back"
        record["rollback_failures"] = failures
        journal()
        raise RuntimeError("Deployment failed; " + record["status"] + ". Backup: " + str(backup)) from error
    finally:
        # Only the exact temporary directory created above, outside the destination.
        if stage.parent == target.parent and stage.name.startswith(target.name + ".bat-stage-"):
            check_tree(stage)
            shutil.rmtree(stage)
    return {**info, "applied": True, "backup": str(backup)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--reset-local", action="store_true", help="Archive local model/execution configuration and session state")
    args = parser.parse_args()
    try:
        result = deploy(Path(__file__).resolve().parents[1], args.target, args.apply, args.reset_local)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, str(exc) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
