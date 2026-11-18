import pytest
from agent_harness.config import Settings, ModelConfig
from agent_harness.runtime.skills import SkillRegistry

@pytest.fixture
def settings(tmp_path, monkeypatch):
    for key in ("LLM_API_KEY","LLM_ENDPOINT","LLM_MODEL","AGENT_HARNESS_MODEL_PROVIDER"):
        monkeypatch.delenv(key, raising=False)
    (tmp_path / "workspace").mkdir()
    folder = tmp_path / "skills/local-coding"
    folder.mkdir(parents=True)
    folder.joinpath("SKILL.md").write_text("---\nname: local-coding\ndescription: Local coding\n---\nRead, edit and verify.", encoding="utf-8")
    cfg = Settings(tmp_path)
    cfg.models = {"demo":ModelConfig(provider="fake")}
    cfg.default_model = "demo"
    return cfg

@pytest.fixture
def skills(settings):
    return SkillRegistry(settings.root / "skills")
