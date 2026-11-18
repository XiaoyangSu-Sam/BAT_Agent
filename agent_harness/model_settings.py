import os
import re
import tempfile
import yaml
from pydantic import BaseModel, Field
from typing import Literal
from .config import ModelConfig, read_yaml
from .errors import HarnessError

class ModelInput(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,60}$")
    endpoint: str
    model: str = "nemotron"
    auth_mode: Literal["none","env","session"] = "none"
    api_key_env: str = Field(default="LLM_API_KEY", pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    session_api_key: str = ""
    tool_mode: Literal["native","json","disabled"] = "native"
    temperature: float = 0.2
    timeout: float = 180
    trust_env: bool = True

def save_model(settings, value):
    key = "" if value.auth_mode == "none" else "$"+value.api_key_env
    if value.auth_mode == "session" and not value.session_api_key:
        raise HarnessError("missing_credential", "Enter a session key or select another authentication mode.", "configuration")
    cfg = ModelConfig(endpoint=value.endpoint, model=value.model, api_key=key,
                      tool_mode=value.tool_mode, temperature=value.temperature,
                      timeout=value.timeout, trust_env=value.trust_env)
    cfg.url()
    path = settings.root / "config/environment.yaml"
    data = read_yaml(path)
    if not isinstance(data.get("models", {}), dict):
        raise HarnessError("invalid_configuration", "models must be a mapping.", "configuration")
    data.setdefault("models", {})[value.id] = cfg.model_dump()
    data["default_model"] = value.id
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as f:
        yaml.safe_dump(data, f, sort_keys=False)
        temp = f.name
    try:
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    if value.auth_mode == "session":
        cfg.api_key = value.session_api_key
    settings.models[value.id] = cfg
    settings.default_model = value.id
