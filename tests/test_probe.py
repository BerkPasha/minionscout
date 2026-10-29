"""The shared probe: defensive symbol resolution, redaction, and running as a script."""

import json
import sys
from pathlib import Path

import pytest

import openminion
from upgrade_scout import probe
from upgrade_scout.compare import PROBE_PATH, run_bounded


def test_resolve_records_a_missing_module_and_attribute():
    obj, error = probe.resolve("no_such_module_for_upgrade_scout")
    assert obj is None and error["type"] == "ModuleNotFoundError"

    obj, error = probe.resolve("json", "dumps.no_such_attribute")
    assert obj is None and error["type"] == "AttributeError"


def test_describe_signature_records_an_unavailable_signature():
    class BadSignature:
        __signature__ = "not a Signature"

    described, error = probe.describe_signature(BadSignature)

    assert described is None and error["type"] in {"TypeError", "ValueError"}


def test_collect_surface_turns_missing_symbols_into_evidence(monkeypatch):
    monkeypatch.setattr(probe, "EXPORT_ROOTS", ("json", "no_such_module_for_upgrade_scout"))
    monkeypatch.setattr(probe, "ENTRY_POINTS", {
        "json.dumps": ("json", "dumps"),
        "json.gone": ("json", "gone"),
    })

    surface = probe.collect_surface()

    assert "dumps" in surface["exports"]["json"]
    assert surface["export_errors"]["no_such_module_for_upgrade_scout"]["type"] == "ModuleNotFoundError"
    assert "obj" in surface["signatures"]["json.dumps"]
    assert surface["unresolved"]["json.gone"]["type"] == "AttributeError"


def test_redact_replaces_the_home_directory_in_plain_and_json_text():
    home = str(Path.home())
    text = f"{home}/x {json.dumps(home)}"

    assert home not in probe.redact(text) and json.dumps(home) not in probe.redact(text)


def test_write_text_atomic_retries_a_transiently_locked_target(tmp_path, monkeypatch):
    """Regression: on OneDrive-synced folders os.replace briefly failed with WinError 5."""
    real_replace, calls = probe.os.replace, []

    def flaky_replace(src, dst):
        calls.append(dst)
        if len(calls) < 3:
            raise PermissionError(5, "simulated: target held open by another process")
        real_replace(src, dst)

    monkeypatch.setattr(probe.os, "replace", flaky_replace)
    monkeypatch.setattr(probe.time, "sleep", lambda seconds: None)

    probe.write_text_atomic(tmp_path / "out.json", "{}")

    assert len(calls) == 3 and (tmp_path / "out.json").read_text(encoding="utf-8") == "{}"


def test_write_text_atomic_gives_up_after_its_attempts(tmp_path, monkeypatch):
    def always_locked(src, dst):
        raise PermissionError(5, "simulated: permanently locked")

    monkeypatch.setattr(probe.os, "replace", always_locked)
    monkeypatch.setattr(probe.time, "sleep", lambda seconds: None)

    with pytest.raises(PermissionError):
        probe.write_text_atomic(tmp_path / "out.json", "{}", attempts=3)


def _run_probe_stage(tmp_path, stage):
    output = tmp_path / f"{stage}.json"
    result = run_bounded(
        [sys.executable, "-I", "-X", "utf8", str(PROBE_PATH), stage, "--requested-version",
         openminion.__version__, "--workdir", str(tmp_path / "work"), "--output", str(output)],
        log_path=tmp_path / f"{stage}.log", timeout_s=120,
    )
    return result, json.loads(output.read_text(encoding="utf-8"))


def test_probe_surface_stage_runs_isolated_as_a_script(tmp_path):
    result, data = _run_probe_stage(tmp_path, "surface")

    assert result["status"] == "ok" and data["complete"] is True
    assert data["surface"]["sdk_version"] == openminion.__version__
    assert data["surface"]["unresolved"] == {}


@pytest.mark.runtime
def test_probe_preflight_stage_runs_isolated_as_a_script(tmp_path):
    result, data = _run_probe_stage(tmp_path, "preflight")

    assert result["status"] == "ok" and data["complete"] is True
    assert data["installed_version"] == openminion.__version__
    assert data["socketpair"]["ok"] and data["asyncio_loop"]["ok"]
