import os
import re
import tempfile
import yaml
from pydantic import BaseModel, Field, field_validator
from typing import Literal
from .config import ModelConfig, read_yaml
from .errors import HarnessError

class ModelInput(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,60}$")
    endpoint: str = Field(min_length=1, max_length=4096)
    endpoint_mode: Literal["auto", "exact"] = "auto"
    model: str = Field(default="nemotron", min_length=1, max_length=200)
    auth_mode: Literal["none","env","session","saved"] = "none"
    api_key_env: str = Field(default="LLM_API_KEY", pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    session_api_key: str = ""
    tool_mode: Literal["native","json","disabled"] = "native"
    temperature: float = Field(default=0.2, ge=0, le=2)
    timeout: float = Field(default=180, gt=0, le=1800)
    trust_env: bool = True
    context_window: int | None = Field(default=None, ge=1024, le=10000000)
    connect_timeout: float = Field(default=10, gt=0, le=120)
    max_retries: int = Field(default=2, ge=0, le=5)
    max_tokens: int = Field(default=4096, gt=0, le=131072)
    create_only: bool = False

    @field_validator("endpoint", "model", mode="before")
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value

def connection_config(value, settings=None):
    key = "" if value.auth_mode == "none" else "$"+value.api_key_env
    if value.auth_mode == "session" and not value.session_api_key:
        raise HarnessError("missing_credential", "Enter a session key or select another authentication mode.", "configuration")
    cfg = ModelConfig(endpoint=value.endpoint, model=value.model, api_key=key,
                      endpoint_mode=value.endpoint_mode,
                      tool_mode=value.tool_mode, temperature=value.temperature,
                      timeout=value.timeout, trust_env=value.trust_env, context_window=value.context_window,
                      connect_timeout=value.connect_timeout, max_retries=value.max_retries, max_tokens=value.max_tokens)
    cfg.url()
    if value.auth_mode == "session":
        cfg.api_key = value.session_api_key
    elif value.auth_mode == "saved":
        if settings is None:
            raise HarnessError("missing_credential", "Choose a saved connection first.", "configuration")
        cfg.api_key = settings.model(value.id).api_key
    return cfg


def save_model(settings, value):
    if value.create_only and value.id in settings.models:
        raise HarnessError("connection_exists", "Choose a unique connection name.", "configuration")
    cfg = connection_config(value, settings)
    path = settings.root / "config/environment.yaml"
    data = read_yaml(path)
    if not isinstance(data.get("models", {}), dict):
        raise HarnessError("invalid_configuration", "models must be a mapping.", "configuration")
    stored = cfg.model_dump()
    if value.auth_mode == "session":
        stored["api_key"] = "$" + value.api_key_env
    elif value.auth_mode == "saved":
        previous = data.get("models", {}).get(value.id)
        if previous is None:
            previous = read_yaml(settings.root / "config/model.yaml")
        stored["api_key"] = previous.get("api_key", "$LLM_API_KEY") if cfg.api_key else ""
    data.setdefault("models", {})[value.id] = stored
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
    settings.models[value.id] = cfg
    settings.default_model = value.id
