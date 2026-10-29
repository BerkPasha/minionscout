"""Project-local OpenMinion home, so scout runs never touch ~/.openminion."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

AGENT_ID = "scout"

# Credential variables from the OpenMinion environment-variable reference, for
# providers that cannot run without one. Only presence is checked, never printed.
PROVIDER_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "groq": "GROQ_API_KEY",
    "cerebras": "CEREBRAS_API_KEY",
}


def missing_credential(provider: str) -> str | None:
    """The credential variable provider needs but the environment lacks, if any."""
    key_env = PROVIDER_KEY_ENV.get(provider)
    return key_env if key_env and not os.environ.get(key_env) else None


def write_config(home: Path, provider: str = "echo", model: str | None = None) -> Path:
    """Write <home>/.openminion/agents.json and return its path.

    The file names a provider only; credentials stay in the environment.
    """
    agent = {
        "name": AGENT_ID,
        "provider": provider,
        # Not in the documented minimal config, but required: without it
        # Agent.run sends an empty channel and the default authenticity policy
        # denies the turn (reason=invalid_channel). See PROJECT_STATUS.md.
        "default_channel": "console",
    }
    config: dict[str, object] = {"default_agent": AGENT_ID, "agents": {AGENT_ID: agent}}
    if model:
        config["providers"] = {provider: {"model": model}}

    data_root = home / ".openminion"
    data_root.mkdir(parents=True, exist_ok=True)
    path = data_root / "agents.json"
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return path


@contextmanager
def openminion_env(home: Path) -> Iterator[None]:
    """Point OPENMINION_HOME and OPENMINION_DATA_ROOT at home, then restore them."""
    overrides = {
        "OPENMINION_HOME": str(home),
        "OPENMINION_DATA_ROOT": str(home / ".openminion"),
    }
    previous = {name: os.environ.get(name) for name in overrides}
    os.environ.update(overrides)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
