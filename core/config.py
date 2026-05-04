"""
YOLO model configuration.

Config is loaded in this priority order (highest wins):
  1. CLI flags   --provider  --host  --port  --model
  2. ~/.yolo/config.json   (user's persisted preference)
  3. Built-in provider defaults (see PROVIDER_DEFAULTS)

Supported providers:
  ollama    — http://localhost:11434   (default)
  lmstudio  — http://localhost:1234
  llamacpp  — http://localhost:8080
"""

import json
import os
from dataclasses import dataclass, asdict

CONFIG_FILE = os.path.expanduser("~/.yolo/config.json")

PROVIDER_DEFAULTS = {
    "ollama": {
        "host": "localhost",
        "port": 11434,
        "model": "hf.co/erdemozkan/YOLO-Coder-8B",
        "api_key": "ollama",
        # Ollama exposes /api/tags for listing models (not OpenAI-compat)
        "health_path": "/api/tags",
        "health_models_key": "models",        # key inside response JSON
        "health_name_field": "name",          # field on each model object
    },
    "lmstudio": {
        "host": "localhost",
        "port": 1234,
        "model": "",           # LM Studio uses whatever is currently loaded
        "api_key": "lm-studio",
        "health_path": "/v1/models",
        "health_models_key": "data",
        "health_name_field": "id",
    },
    "llamacpp": {
        "host": "localhost",
        "port": 8080,
        "model": "",
        "api_key": "no-key",
        "health_path": "/v1/models",
        "health_models_key": "data",
        "health_name_field": "id",
    },
}

PROVIDER_RUN_INSTRUCTIONS = {
    "ollama": [
        "Start Ollama:       ollama serve",
        "Pull the model:     ollama run hf.co/erdemozkan/YOLO-Coder-8B",
        "Verify it's there:  ollama list",
    ],
    "lmstudio": [
        "Open LM Studio and load a model via the Model tab.",
        "Then start the local server:  LM Studio → Local Server → Start Server",
        "Default port is 1234. Make sure 'Enable CORS' is checked.",
    ],
    "llamacpp": [
        "Start the server:   ./server -m your-model.gguf --port 8080",
        "Or via Python:      python -m llama_cpp.server --model your-model.gguf",
    ],
}


@dataclass
class ModelConfig:
    provider: str
    host: str
    port: int
    model: str
    api_key: str
    health_path: str
    health_models_key: str
    health_name_field: str

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}/v1"

    @property
    def health_url(self) -> str:
        return f"http://{self.host}:{self.port}{self.health_path}"

    def run_instructions(self) -> list[str]:
        return PROVIDER_RUN_INSTRUCTIONS.get(self.provider, [
            f"Start your {self.provider} server on port {self.port}."
        ])


def _load_file() -> dict:
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(provider: str, host: str, port: int, model: str) -> None:
    """Persist user preference to ~/.yolo/config.json."""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    data = {"provider": provider, "host": host, "port": port, "model": model}
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_config(
    provider: str | None = None,
    host: str | None = None,
    port: int | None = None,
    model: str | None = None,
) -> ModelConfig:
    """
    Build a ModelConfig by merging defaults → saved file → CLI overrides.
    Any None argument means "not provided by CLI — use lower-priority source".
    """
    saved = _load_file()

    # Determine provider (CLI > saved > default)
    resolved_provider = provider or saved.get("provider", "ollama")
    if resolved_provider not in PROVIDER_DEFAULTS:
        raise ValueError(
            f"Unknown provider '{resolved_provider}'. "
            f"Choose from: {', '.join(PROVIDER_DEFAULTS)}"
        )

    defaults = PROVIDER_DEFAULTS[resolved_provider]

    resolved_host  = host  or saved.get("host",  defaults["host"])
    resolved_port  = port  or saved.get("port",  defaults["port"])
    resolved_model = model or saved.get("model", defaults["model"])

    return ModelConfig(
        provider=resolved_provider,
        host=resolved_host,
        port=int(resolved_port),
        model=resolved_model,
        api_key=defaults["api_key"],
        health_path=defaults["health_path"],
        health_models_key=defaults["health_models_key"],
        health_name_field=defaults["health_name_field"],
    )
