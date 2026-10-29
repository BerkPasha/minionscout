"""Bounded worker processes, stage classification and compare argument checks.

The workers here are tiny stand-in Python scripts, not the OpenMinion probe, so
these tests need neither the network nor an SDK runtime.
"""

import sys
import textwrap
from pathlib import Path

import pytest

from upgrade_scout import compare as compare_module
from upgrade_scout.cli import main
from upgrade_scout.compare import Timeouts, _stage_blockers, prepare_environment, run_bounded, run_stage


def test_run_bounded_kills_a_hung_worker(tmp_path):
    result = run_bounded([sys.executable, "-c", "import time; time.sleep(120)"],
                         log_path=tmp_path / "hang.log", timeout_s=2)

    assert result["status"] == "timeout" and result["returncode"] is None
    assert result["seconds"] < 60


def test_run_bounded_keeps_the_log_of_a_failing_worker(tmp_path):
    result = run_bounded([sys.executable, "-c", "print('worker diagnostics'); raise SystemExit(3)"],
                         log_path=tmp_path / "fail.log", timeout_s=60)

    assert result["status"] == "failed" and result["returncode"] == 3
    assert "worker diagnostics" in result["log_tail"]


def test_run_bounded_reports_a_missing_executable(tmp_path):
    result = run_bounded([str(tmp_path / "no-such-python.exe")], log_path=tmp_path / "x.log", timeout_s=5)

    assert result["status"] == "error" and "Error" in result["error"]


def _fake_probe(tmp_path, body):
    script = tmp_path / "fake_probe.py"
    script.write_text(textwrap.dedent("""
        import json, sys, time
        args = sys.argv[1:]
        output = args[args.index("--output") + 1]
    """) + textwrap.dedent(body), encoding="utf-8")
    return script


def test_run_stage_keeps_partial_evidence_when_the_worker_hangs(tmp_path):
    probe = _fake_probe(tmp_path, """
        json.dump({"complete": False, "current_step": "socketpair"}, open(output, "w"))
        time.sleep(120)
    """)

    record = run_stage("preflight", "9.9.1", sys.executable, tmp_path / "work", tmp_path / "evidence", 3,
                       probe_path=probe)

    assert record["status"] == "timeout"
    assert record["last_step"] == "socketpair"
    assert record["evidence"] == "preflight.json"


def test_run_stage_without_a_result_file_is_crashed(tmp_path):
    probe = _fake_probe(tmp_path, "print('exited without writing a result')\n")

    record = run_stage("surface", "9.9.1", sys.executable, tmp_path / "work", tmp_path / "evidence", 30,
                       probe_path=probe)

    assert record["status"] == "crashed" and "result" not in record
    assert "exited without writing a result" in record["process"]["log_tail"]


def test_run_stage_with_a_complete_result_is_completed(tmp_path):
    probe = _fake_probe(tmp_path, 'json.dump({"complete": True, "outcome": "completed"}, open(output, "w"))\n')

    record = run_stage("echo_turn", "9.9.1", sys.executable, tmp_path / "work", tmp_path / "evidence", 30,
                       probe_path=probe)

    assert record["status"] == "completed" and record["result"]["outcome"] == "completed"


def test_run_stage_accepts_a_relative_evidence_dir(tmp_path, monkeypatch):
    """Regression: the worker runs in its workdir, so a relative --output once pointed into it."""
    probe = _fake_probe(tmp_path, 'json.dump({"complete": True}, open(output, "w"))\n')
    monkeypatch.chdir(tmp_path)

    record = run_stage("surface", "9.9.1", sys.executable, tmp_path / "work", Path("relative-evidence"), 30,
                       probe_path=probe)

    assert record["status"] == "completed"
    assert (tmp_path / "relative-evidence" / "surface.json").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="the MAX_PATH limit only applies on Windows")
def test_too_deep_environment_path_fails_before_creating_anything(tmp_path, monkeypatch):
    monkeypatch.setattr(compare_module, "_long_paths_enabled", lambda: False)
    env_dir = tmp_path / ("d" * 150) / "envs" / "9.9.1"

    env = prepare_environment("9.9.1", env_dir, tmp_path / "evidence", Timeouts(), recreate=False)

    assert env["status"] == "failed" and env["failure"] == "path_too_long"
    assert not env_dir.exists() and not (tmp_path / "evidence").exists()


def test_preflight_results_gate_later_stages():
    ok = {"installed_version": "9.9.1", "socketpair": {"ok": True}, "asyncio_loop": {"ok": True}}

    assert _stage_blockers("9.9.1", {"status": "completed", "result": ok}) == (None, None)
    assert _stage_blockers("9.9.1", {"status": "timeout"})[1] == "preflight timeout"
    mismatch = _stage_blockers("9.9.2", {"status": "completed", "result": ok})
    assert mismatch[0] and "9.9.2" in mismatch[0]
    no_loop = {**ok, "socketpair": {"ok": False}}
    assert _stage_blockers("9.9.1", {"status": "completed", "result": no_loop})[1]


@pytest.mark.parametrize("bad", ["latest", "0.1", "0.1.8;calc", "0.1.8 --index-url=http://x", "", "v0.1.8"])
def test_compare_rejects_invalid_versions_before_doing_anything(bad, tmp_path, capsys):
    output_dir = tmp_path / "out"

    assert main(["compare", "--baseline", bad, "--candidate", "0.1.15", "--output-dir", str(output_dir)]) == 2
    assert "release version" in capsys.readouterr().err
    assert not output_dir.exists()


def test_compare_refuses_a_non_empty_directory_it_did_not_create(tmp_path, capsys):
    (tmp_path / "unrelated.txt").write_text("keep me", encoding="utf-8")

    code = main(["compare", "--baseline", "0.1.8", "--candidate", "0.1.15", "--output-dir", str(tmp_path)])

    assert code == 2 and "not empty" in capsys.readouterr().err
    assert (tmp_path / "unrelated.txt").read_text(encoding="utf-8") == "keep me"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["unrelated.txt"]


def test_compare_rejects_non_positive_timeouts(tmp_path):
    args = ["compare", "--baseline", "0.1.8", "--candidate", "0.1.15", "--output-dir", str(tmp_path / "o"),
            "--probe-timeout", "0"]

    assert main(args) == 2
    assert not (tmp_path / "o").exists()
