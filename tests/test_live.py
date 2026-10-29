"""Real model-backed runs. Skipped unless SCOUT_LIVE_PROVIDER (and its API key) are set.

Example (PowerShell): set OPENAI_API_KEY in the session, then
    $env:SCOUT_LIVE_PROVIDER = "openai"; $env:SCOUT_LIVE_MODEL = "gpt-4.1-mini"
    python -m pytest tests/test_live.py -v
"""

import json
import os
from pathlib import Path

import pytest

from upgrade_scout import BASELINE_SDK_VERSION
from upgrade_scout.agent import run_scout
from upgrade_scout.analysis import EXIT_SUCCESS, run_analyze
from upgrade_scout.compare import sha256_file
from upgrade_scout.home import openminion_env, write_config

PROVIDER = os.environ.get("SCOUT_LIVE_PROVIDER")
MODEL = os.environ.get("SCOUT_LIVE_MODEL")
PHASE3_REPORT = Path(__file__).resolve().parents[1] / "evidence/phase3/compare/0.1.8-vs-0.1.15/report.json"


@pytest.mark.skipif(not PROVIDER, reason="set SCOUT_LIVE_PROVIDER and its API key for a real model run")
def test_live_model_run_uses_the_tool(tmp_path, monkeypatch):
    home = tmp_path / "home"
    config_path = write_config(home, provider=PROVIDER, model=MODEL)
    monkeypatch.chdir(tmp_path)

    with openminion_env(home):
        result = run_scout(config_path=str(config_path))

    assert result.run_state == "completed"
    assert result.stats["tool_calls"] >= 1
    assert BASELINE_SDK_VERSION in result.text


@pytest.mark.skipif(not (PROVIDER and MODEL), reason="set SCOUT_LIVE_PROVIDER, SCOUT_LIVE_MODEL and the API key")
def test_live_analysis_of_the_real_phase3_comparison(tmp_path):
    """The actual analyze workflow against the real 0.1.8 -> 0.1.15 report, with a real provider."""
    source_hash = sha256_file(PHASE3_REPORT)

    code = run_analyze(PHASE3_REPORT, PROVIDER, MODEL, tmp_path / "analysis", deadline_s=600,
                       state_root=tmp_path / "state")

    record = json.loads((tmp_path / "analysis" / "analysis.json").read_text(encoding="utf-8"))
    assert code == EXIT_SUCCESS, (record["failure_reasons"], record["validation_problems"], record.get("error"))
    assert record["worker"]["status"] == "ok" and record["worker"]["returncode"] == 0
    assert record["runtime"]["run_state"] == "completed"
    assert record["tool_execution"]["python_invocations"] >= 1
    assert record["transport_problems"] == []
    assert all(call["returned"] == {"verdict": 1, "scope_rules": 5, "observations": 11, "next_check_options": 3}
               for call in record["tool_execution"]["invocations"])
    assert record["schema"] == "minion-upgrade-scout/analysis/2"
    assert record["model_selection"] is not None
    assert record["factual_report"]["verdict"] == record["input"]["deterministic_verdict"]
    assert record["input"]["report_sha256"] == source_hash == sha256_file(PHASE3_REPORT)
