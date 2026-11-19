import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import yaml
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal
from .errors import HarnessError

class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["openai_compatible", "fake"] = "openai_compatible"
    endpoint: str = ""
    model: str = "nemotron"
    api_key: str = ""
    temperature: float = Field(default=0.2, ge=0, le=2)
    timeout: float = Field(default=180, gt=0, le=1800)
    connect_timeout: float = Field(default=10, gt=0, le=120)
    max_retries: int = Field(default=2, ge=0, le=5)
    max_tokens: int = Field(default=4096, gt=0, le=131072)
    tool_mode: Literal["native", "json", "disabled"] = "native"
    trust_env: bool = True
    context_window: int | None = Field(default=None, ge=1024, le=10000000)

    def secret(self):
        value = self.api_key
        match = re.fullmatch(r"\$(?:\{([A-Za-z_]\w*)\}|([A-Za-z_]\w*))", value)
        if match:
            key = match[1] or match[2]
            if not os.environ.get(key):
                raise HarnessError("missing_credential",
                    f"Environment variable {key} is unset. For no-auth endpoints set api_key to an empty string.",
                    "configuration")
            return os.environ[key]
        return value

    def url(self):
        p = urlsplit(self.endpoint.strip())
        if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password or p.query or p.fragment:
            raise HarnessError("invalid_endpoint", "Use an http(s) endpoint without URL credentials, query or fragment.", "configuration")
        path = p.path.rstrip("/")
        if not path.endswith("/chat/completions"):
            path += "/chat/completions" if path.endswith("/v1") else "/v1/chat/completions"
        return urlunsplit((p.scheme, p.netloc, path, "", ""))

class ExecutionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_root: str = "./workspace"
    python_executable: str = ""
    timeout: float = Field(default=120, gt=0, le=1800)
    max_steps: int = Field(default=24, ge=1, le=200)
    max_context_chars: int = Field(default=120000, ge=4000, le=2000000)
    max_output_chars: int = Field(default=16000, ge=1000, le=100000)
    approval_mode: Literal["execution", "all", "trusted"] = "execution"

    def python(self):
        return self.python_executable or sys.executable

def read_yaml(path):
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must contain a YAML mapping")
    return data

class Settings:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.models = {}
        self.default_model = None
        self.execution = ExecutionConfig()
        self.reload()

    def reload(self):
        try:
            self.execution = ExecutionConfig(**read_yaml(self.root / "config/execution.yaml"))
            single = read_yaml(self.root / "config/model.yaml")
            for env, key in [("LLM_ENDPOINT", "endpoint"), ("LLM_MODEL", "model")]:
                if os.getenv(env):
                    single[key] = os.environ[env]
            if os.getenv("LLM_API_KEY"):
                single["api_key"] = "$LLM_API_KEY"
            multi = read_yaml(self.root / "config/environment.yaml")
            entries = multi.get("models", {})
            if not isinstance(entries, dict):
                raise ValueError("environment.yaml models must be a mapping keyed by model id")
            models = {"default": ModelConfig(**single)} if single else {}
            models.update({k: ModelConfig(**v) for k, v in entries.items()})
            default = multi.get("default_model") or next(iter(models), None)
            if os.getenv("AGENT_HARNESS_MODEL_PROVIDER") == "fake":
                models = {"demo": ModelConfig(provider="fake", model="offline-scripted-demo")}
                default = "demo"
            if default and default not in models:
                raise ValueError("default_model does not name a configured model")
            self.models, self.default_model = models, default
        except Exception as exc:
            raise HarnessError("invalid_configuration", "Configuration is invalid; check YAML schema and field types.", "configuration") from exc

    @property
    def workspace(self):
        return (self.root / self.execution.workspace_root).resolve()

    @property
    def state_dir(self):
        return self.root / ".harness"

    def model(self, name=None):
        key = name or self.default_model
        if key not in self.models:
            raise HarnessError("model_not_configured", "Configure a model, or start with --demo.", "configuration")
        return self.models[key].model_copy(deep=True)

    def public(self):
        def ready(model):
            try:
                if model.provider != "fake":
                    model.url()
                    model.secret()
                return True
            except HarnessError:
                return False
        return {"models": [{**v.model_dump(exclude={"api_key"}), "id": k, "model": v.model, "provider": v.provider,
                            "tool_mode": v.tool_mode, "endpoint": v.endpoint,
                            "credential_configured": bool(v.api_key),
                            "credential_env": v.api_key.lstrip("$").strip("{}") if v.api_key.startswith("$") else "",
                            "ready": ready(v), "context_window": v.context_window}
                           for k, v in self.models.items()],
                "default_model": self.default_model,
                "setup_required": not any(ready(m) for m in self.models.values()),
                "workspace": str(self.workspace), "execution": self.execution.model_dump()}
