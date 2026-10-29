"""The minimal Upgrade Scout agent, built on the OpenMinion 0.1 Python SDK."""

from __future__ import annotations

import json

from openminion import Agent, AgentRunResult, tool

from .surface import sdk_surface

DEFAULT_MESSAGE = "Which OpenMinion SDK version is installed, and what does it export?"

INSTRUCTIONS = (
    "You are Minion Upgrade Scout. Call installed_sdk_surface, then report the "
    "installed OpenMinion version and how many public names each import root "
    "exports, in at most three sentences. Use only facts from the tool result."
)


@tool
def installed_sdk_surface() -> str:
    """Return the installed OpenMinion SDK version, public exports and key signatures as JSON."""
    return json.dumps(sdk_surface(), sort_keys=True)


def run_scout(
    message: str = DEFAULT_MESSAGE,
    *,
    config_path: str,
    session_id: str = "upgrade-scout",
    timeout_seconds: float = 180,
) -> AgentRunResult:
    """Run one scout turn against the agent configured at config_path."""
    with Agent(
        instructions=INSTRUCTIONS,
        tools=[installed_sdk_surface],
        forced_tools=["installed_sdk_surface"],
        config_path=config_path,
        session_id=session_id,
    ) as agent:
        return agent.run(message, timeout_seconds=timeout_seconds)
