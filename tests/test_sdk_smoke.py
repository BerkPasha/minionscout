"""Smoke tests for the OpenMinion SDK foundation. No network, no credentials."""

import inspect
import json

import pytest

import openminion
import openminion.api
from openminion import Agent, AgentRunResult
from upgrade_scout import BASELINE_SDK_VERSION
from upgrade_scout.agent import installed_sdk_surface, run_scout
from upgrade_scout.home import openminion_env
from upgrade_scout.surface import sdk_surface

# Public names listed for each import root in the OpenMinion 0.1 API reference.
DOCUMENTED_ROOT_EXPORTS = {
    "APIRuntime", "Agent", "AgentOutputValidationError", "AgentRunResult", "Handoff",
    "MemoryBundle", "OpenMinionConfig", "ProviderError", "TurnTimeoutError", "subagent", "tool",
}
DOCUMENTED_API_EXPORTS = {
    "RuntimeTurnHandle", "ToolCallSummary", "TurnChunk", "TurnError", "TurnResponse",
    "TurnTelemetry", "dispatch_request",
}
DOCUMENTED_AGENT_KEYWORDS = {
    "instructions", "output_type", "runtime", "config_path", "agent_id", "model",
    "tools", "forced_tools", "handoffs", "name", "session_id",
}


def test_installed_sdk_is_the_pinned_baseline():
    assert openminion.__version__ == BASELINE_SDK_VERSION


def test_documented_exports_are_present():
    assert DOCUMENTED_ROOT_EXPORTS <= set(openminion.__all__)
    assert DOCUMENTED_API_EXPORTS <= set(openminion.api.__all__)


def test_agent_accepts_documented_keywords():
    params = inspect.signature(Agent.__init__).parameters
    assert DOCUMENTED_AGENT_KEYWORDS <= params.keys()


def test_agent_initializes_and_closes_with_a_tool(scout_home):
    with Agent(config_path=str(scout_home), tools=[installed_sdk_surface]) as agent:
        assert isinstance(agent, Agent)


def test_agent_rejects_an_undecorated_tool():
    def plain() -> str:
        return "not a tool"

    with pytest.raises(TypeError, match="decorated with openminion.tool"):
        Agent(tools=[plain])


@pytest.mark.runtime
def test_echo_turn_runs_end_to_end(scout_home):
    """A full Agent.run through the runtime on the echo provider (no model inference)."""
    result = run_scout("ping from the smoke test", config_path=str(scout_home), session_id="smoke")

    assert isinstance(result, AgentRunResult)
    assert result.run_state == "completed"
    assert result.session_id == "smoke"
    assert result.run_id
    assert "ping from the smoke test" in result.text
    assert result.stats["llm_calls"] == 1
    assert result.stats["input_tokens"] == 0 and result.stats["output_tokens"] == 0


@pytest.mark.runtime
def test_documented_minimal_config_is_denied_without_default_channel(tmp_path, monkeypatch):
    """Characterizes a Phase 1 finding (seen on 0.1.8 and 0.1.15).

    The minimal config from the Configuration docs omits default_channel, so
    Agent.run sends an empty channel and the turn is denied. If an upgrade
    fixes this, this test fails and the finding should be re-checked.
    """
    home = tmp_path / "home"
    (home / ".openminion").mkdir(parents=True)
    config_path = home / ".openminion" / "agents.json"
    config_path.write_text(json.dumps({
        "default_agent": "default",
        "agents": {"default": {"name": "default", "provider": "echo"}},
    }), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    with openminion_env(home), Agent(config_path=str(config_path)) as agent:
        with pytest.raises(RuntimeError, match=r"reason=invalid_channel"):
            agent.run("hello", timeout_seconds=60)


def test_sdk_surface_snapshot_matches_the_install():
    snapshot = sdk_surface()

    assert snapshot["sdk_version"] == openminion.__version__
    assert snapshot["exports"]["openminion"] == sorted(openminion.__all__)
    assert "forced_tools" in snapshot["signatures"]["openminion.Agent"]
    assert json.loads(installed_sdk_surface()) == json.loads(json.dumps(snapshot))
