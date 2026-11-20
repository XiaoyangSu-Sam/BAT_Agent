"""Behavior checks for reusing an existing environment before changing packages."""
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location(
    "environment_check", Path(__file__).resolve().parents[2] / "scripts/check_environment.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


@pytest.mark.parametrize("version", ["1.10.0", "3.0.0"])
def test_unsupported_dependency_never_reports_ready(version, monkeypatch):
    original = checker.importlib.metadata.version
    monkeypatch.setattr(checker.importlib.metadata, "version",
                        lambda name: version if name == "pydantic" else original(name))
    report = checker.check()
    assert not report["ok"]
    assert any("pydantic" in issue for issue in report["issues"])
    assert report["configuration"] == "not checked"
    assert report["network_tested"] is False


def test_missing_dependency_never_reports_ready(monkeypatch):
    original = checker.importlib.metadata.version
    def version(name):
        if name == "httpx":
            raise checker.importlib.metadata.PackageNotFoundError(name)
        return original(name)
    monkeypatch.setattr(checker.importlib.metadata, "version", version)
    report = checker.check()
    assert not report["ok"]
    assert any("httpx" in issue for issue in report["issues"])
