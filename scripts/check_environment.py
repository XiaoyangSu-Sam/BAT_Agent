"""Check local prerequisites without making network requests or displaying configuration."""
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
REQUIRED = {"fastapi": (0, 115), "uvicorn": (0, 30), "httpx": (0, 27),
            "PyYAML": (6,), "jsonschema": (4, 23), "pydantic": (2,)}


def check():
    issues = []
    packages = {}
    if sys.version_info < (3, 11):
        issues.append("Python 3.11 or later is required.")
    for name, minimum in REQUIRED.items():
        try:
            version = importlib.metadata.version(name)
            parts = tuple(int(p) for p in version.split(".")[:len(minimum)])
            packages[name] = version
            if parts < minimum:
                issues.append(name + " needs updating.")
        except (importlib.metadata.PackageNotFoundError, ValueError):
            packages[name] = "missing or unrecognized"
            issues.append(name + " must be installed in this interpreter.")
    for name in ("index.html", "app.js", "editor.bundle.js", "markdown.bundle.js"):
        if not (ROOT / "agent_harness/static" / name).is_file():
            issues.append("Missing bundled UI asset: " + name)
    config_status = "not checked"
    if not issues:
        try:
            from agent_harness.config import Settings
            Settings(ROOT)
            config_status = "valid (connection not tested)"
        except Exception:
            config_status = "invalid"
            issues.append("Configuration could not load. Review local YAML fields and credential-variable availability; no values have been printed.")
    registered, warnings = [], []
    try:
        from agent_harness.runtime.skills import SkillRegistry
        registry = SkillRegistry(ROOT / "skills")
        registered = list(registry.skills)
        if registry.warnings:
            warnings.append("Some Skill folders are invalid; review the Skills panel.")
        # Deliberately avoid printing parser errors or Skill content.
        for folder in (ROOT / "skills").iterdir():
            if folder.is_dir() and not (folder / "SKILL.md").is_file() and any(folder.glob("*/SKILL.md")):
                warnings.append("A nested Skill archive wrapper was found; use skills/<id>/SKILL.md.")
    except Exception:
        warnings.append("Skill discovery could not be checked; review the Skills panel after startup.")
    return {"ok": not issues, "python": sys.executable,
            "python_version": sys.version.split()[0], "required_packages": packages,
            "configuration": config_status, "skill_folders": len(registered),
            "optional": {name: importlib.util.find_spec(name) is not None
                         for name in ("nbclient", "nbformat", "ipykernel", "playwright")},
            "issues": issues, "warnings": warnings,
            "network_tested": False}


if __name__ == "__main__":
    result = check()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["ok"] else 1)
