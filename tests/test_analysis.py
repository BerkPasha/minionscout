"""Offline tests of `analyze`: report validation, evidence references, credentials,
tool-execution requirements and failure handling.

MOCKED MODEL RESULTS: no test here calls a model. Every model selection, worker result
and Agent below is a hand-written stand-in marked MOCKED, and the comparison
directories are built from the SYNTHETIC fixtures of test_compare.py. None of it
is live evidence of model behavior.
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_compare import echo_summary, pair, surface_of  # SYNTHETIC fixtures
from upgrade_scout import analysis_worker
from upgrade_scout.analysis import (
    ECHO_LIMITATION, EXIT_FAILED, EXIT_INVALID, EXIT_SUCCESS, OUTPUT_MARKER, ModelSelection, judge,
    next_check_options, run_analyze, usage_from, validate_inputs, validate_selection,
)
from upgrade_scout.compare import EvidenceError, build_report, sha256_file

FAKE_KEY = "sk-MOCKED-not-a-real-key-0123456789"


def write_comparison(tmp_path, mutate=None):
    """Write a SYNTHETIC comparison directory (report.json + per-version evidence) and return report.json."""
    base, cand = pair()
    if mutate:
        mutate(base, cand)
    root = tmp_path / "comparison"
    for record in (base, cand):
        directory = root / record["evidence_dir"]
        directory.mkdir(parents=True)
        (directory / "environment.json").write_text(json.dumps(record["environment"]), encoding="utf-8")
        for stage, stage_record in record["stages"].items():
            if "result" in stage_record:
                # Stamp each stage file the way the real probe's recorder does.
                stage_record["result"].update(stage=stage, requested_version=record["requested_version"])
                stage_record.update(evidence=f"{stage}.json", process={"seconds": 0.1, "log": f"{stage}.log"})
                (directory / f"{stage}.json").write_text(json.dumps(stage_record["result"]), encoding="utf-8")
                (directory / f"{stage}.log").write_text("", encoding="utf-8")
    report = build_report(base, cand, request={})
    (root / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return root / "report.json"


def mocked_selection(**changes):
    """MOCKED model output (analysis schema 2): hand-written, not produced by any model."""
    selection = {
        "key_observations": ["X1", "G1", "B3"],
        "relevant_limitations": ["S2"],
        "next_checks": [{"check_id": "validate_with_real_provider", "rationale": "MOCKED rationale.",
                         "evidence": ["S2"]}],
    }
    selection.update(changes)
    return selection


def fact_ids(report_path):
    return {fact["id"] for fact in validate_inputs(report_path)[1]}


def analysis_kwargs(tmp_path, mutate=None):
    """facts and next-check options of a SYNTHETIC comparison, as judge() takes them."""
    report, facts, _ = validate_inputs(write_comparison(tmp_path, mutate))
    return {"facts": facts, "options": next_check_options(report, facts)}


# --- report and evidence validation ----------------------------------------------------


def test_validate_inputs_accepts_a_consistent_synthetic_comparison(tmp_path):
    report_path = write_comparison(tmp_path)

    report, facts, files = validate_inputs(report_path)

    ids = [fact["id"] for fact in facts]
    assert ids[0] == "V1" and "compatible" in facts[0]["statement"]
    assert {"S2", "P1", "P2", "X1", "X2", "G1", "B1", "B2", "B3"} <= set(ids)
    assert all(len(entry["sha256"]) == 64 for entry in files)
    for fact in facts:
        for path in fact["evidence"]:
            assert (report_path.parent / path).is_file()


def test_a_report_that_disagrees_with_its_raw_evidence_is_rejected(tmp_path):
    report_path = write_comparison(tmp_path, lambda b, c: echo_summary(c).update(text_contains_message=False))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["verdict"] == "regressions_detected"
    report.update(verdict="compatible", exit_code=0, regressions=[])  # tampered
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(EvidenceError, match="does not match its raw evidence"):
        validate_inputs(report_path)


def test_an_older_schema_report_is_rejected(tmp_path):
    report_path = write_comparison(tmp_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["schema"] = "minion-upgrade-scout/compare/1"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(EvidenceError, match="not the current"):
        validate_inputs(report_path)


def rewrite_report(report_path, mutate):
    report = json.loads(report_path.read_text(encoding="utf-8"))
    mutate(report)
    report_path.write_text(json.dumps(report), encoding="utf-8")


def test_a_false_installed_version_is_rejected_before_any_model_call(tmp_path):
    """Phase 4 reviewer-reproduced application defect A (installed_version); SYNTHETIC fixture."""
    report_path = write_comparison(tmp_path)
    rewrite_report(report_path, lambda r: r["versions"]["candidate"].update(installed_version="999.999.999"))

    with pytest.raises(EvidenceError, match=r"versions.candidate does not match its raw evidence.*installed_version"):
        validate_inputs(report_path)


def test_a_false_scope_statement_is_rejected_before_any_model_call(tmp_path):
    """Phase 4 reviewer-reproduced application defect A (scope); SYNTHETIC fixture."""
    report_path = write_comparison(tmp_path)
    false_claim = "Real model inference and model-driven tool execution succeeded."
    rewrite_report(report_path, lambda r: r["scope"].__setitem__(1, false_claim))

    with pytest.raises(EvidenceError, match="scope differs"):
        validate_inputs(report_path)


@pytest.mark.parametrize("mutate, message", [
    (lambda r: r["echo_contract"].update(completed="anything goes"), "echo_contract differs"),
    (lambda r: r["versions"]["baseline"].update(python="2.7.18"), "versions.baseline does not match"),
    (lambda r: r["versions"]["candidate"]["environment"].update(status="failed"), "versions.candidate does not match"),
    (lambda r: r["versions"]["candidate"].update(requested_version="9.9.3"), "evidence_dir"),
])
def test_other_report_declarations_must_match_definitions_and_raw_evidence(tmp_path, mutate, message):
    report_path = write_comparison(tmp_path)
    rewrite_report(report_path, mutate)

    with pytest.raises(EvidenceError, match=message):
        validate_inputs(report_path)


def test_stage_evidence_from_a_different_version_is_rejected(tmp_path):
    report_path = write_comparison(tmp_path)
    surface = report_path.parent / "candidate-9.9.2" / "surface.json"
    data = json.loads(surface.read_text(encoding="utf-8"))
    data["requested_version"] = "9.9.1"
    surface.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(EvidenceError, match="was not produced by the surface probe for 9.9.2"):
        validate_inputs(report_path)


def test_facts_are_built_from_validated_information(tmp_path):
    report, facts, _ = validate_inputs(write_comparison(tmp_path))
    by_id = {fact["id"]: fact["statement"] for fact in facts}

    assert "installed 9.9.2" in by_id["P2"]
    assert by_id["S2"] == report["scope"][1]
    assert "prove neither real model inference nor model-driven tool execution" in by_id["S2"]


def test_a_missing_evidence_file_is_rejected(tmp_path):
    report_path = write_comparison(tmp_path)
    (report_path.parent / "candidate-9.9.2" / "surface.json").unlink()

    with pytest.raises(EvidenceError):
        validate_inputs(report_path)


def test_an_evidence_path_outside_the_comparison_is_rejected(tmp_path):
    report_path = write_comparison(tmp_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["versions"]["baseline"]["evidence_dir"] = "../outside"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(EvidenceError, match="is not baseline-9.9.1"):
        validate_inputs(report_path)


def test_a_stage_evidence_name_outside_the_comparison_is_rejected(tmp_path):
    report_path = write_comparison(tmp_path)
    rewrite_report(report_path, lambda r: r["versions"]["candidate"]["stages"]["surface"].update(
        evidence="../../report.json"))

    with pytest.raises(EvidenceError, match="unsafe evidence name"):
        validate_inputs(report_path)


# --- selection validation (MOCKED selections) -------------------------------------------


def validate(tmp_path, data, verdict="compatible"):
    kwargs = analysis_kwargs(tmp_path)
    return validate_selection(data, kwargs["facts"], kwargs["options"], verdict)


def test_a_grounded_mocked_selection_is_accepted(tmp_path):
    selection, problems = validate(tmp_path, mocked_selection())

    assert problems == [] and selection["key_observations"] == ["X1", "G1", "B3"]


def test_unknown_ids_are_rejected(tmp_path):
    selection, problems = validate(tmp_path, mocked_selection(key_observations=["X1", "Z9"]))

    assert selection is None and problems == ["key_observations: unknown id 'Z9'"]


@pytest.mark.parametrize("data", [
    mocked_selection(verdict="compatible"),                                # the model may not supply a verdict
    mocked_selection(summary="MOCKED prose summary"),                      # nor free-form summary text
    {k: v for k, v in mocked_selection().items() if k != "next_checks"},   # missing section
    mocked_selection(key_observations=[]),                                 # empty ranking
    "not a JSON object",
])
def test_structurally_invalid_output_is_rejected(tmp_path, data):
    selection, problems = validate(tmp_path, data)

    assert selection is None and problems and problems[0].startswith("schema:")


def test_a_rationale_that_upgrades_an_inconclusive_verdict_is_rejected(tmp_path):
    data = mocked_selection(next_checks=[{"check_id": "validate_with_real_provider",
                                          "rationale": "MOCKED: the upgrade is fully compatible.", "evidence": []}])

    selection, problems = validate(tmp_path, data, verdict="inconclusive")

    assert selection is None and "claims compatibility" in problems[0]


# --- success criteria (MOCKED worker results) ---------------------------------------------


def mocked_worker_result(selection=None, provider="openai"):
    """MOCKED worker result: what a completed real turn would look like, hand-written."""
    return {"status": "completed", "run_state": "completed", "output": selection or mocked_selection(),
            "runtime": {"metadata_provider": provider, "metadata_model": "brain-orchestrator",
                        "stats": {"tool_calls": 1}}}


ONE_TOOL_CALL = [{"tool": "comparison_evidence", "at": "MOCKED",
                  "returned": {"verdict": 1, "scope_rules": 5, "observations": 11, "next_check_options": 3}}]
# Process records follow run_bounded's contract: status ok|failed|timeout|error plus returncode.
FINISHED = {"status": "ok", "returncode": 0}
TIMED_OUT = {"status": "timeout", "returncode": None}


def test_usage_keeps_missing_telemetry_distinct_from_zero():
    assert usage_from(None)["available"] is False and "not zero usage" in usage_from(None)["note"]
    usage = usage_from({"stats": {"input_tokens": 0, "llm_calls": 2}})
    assert usage["available"] is True
    assert usage["input_tokens"] == 0 and usage["output_tokens"] == "not reported" and usage["llm_calls"] == 2


def test_success_requires_every_condition(tmp_path):
    decision = judge(provider="openai", process=FINISHED, worker_result=mocked_worker_result(),
                     tool_calls=ONE_TOOL_CALL, **analysis_kwargs(tmp_path), verdict="compatible")

    assert decision["status"] == "success"
    assert [o["id"] for o in decision["model_selection"]["key_observations"]] == ["X1", "G1", "B3"]


def test_a_valid_selection_without_observed_tool_execution_fails(tmp_path):
    decision = judge(provider="openai", process=FINISHED, worker_result=mocked_worker_result(), tool_calls=[],
                     **analysis_kwargs(tmp_path), verdict="compatible")

    assert decision["status"] == "failed" and decision["failure_reasons"] == ["tool_not_executed"]
    assert decision["model_selection"] is None


def test_the_echo_provider_never_counts_as_a_successful_analysis(tmp_path):
    decision = judge(provider="echo", process=FINISHED, worker_result=mocked_worker_result(provider="echo"),
                     tool_calls=ONE_TOOL_CALL, **analysis_kwargs(tmp_path), verdict="compatible")

    assert decision["failure_reasons"] == ["echo_provider_is_not_a_model"] and decision["model_selection"] is None


@pytest.mark.parametrize("process", [
    {"status": "failed", "returncode": 7},                                   # the reviewer's reproduction
    {"status": "error", "returncode": None, "error": "OSError: MOCKED"},     # could not start
    {"status": "ok", "returncode": 3},                                       # inconsistent record
    {"status": "ok"},                                                        # no exit code recorded
])
def test_a_failed_worker_process_is_never_accepted_even_with_a_valid_result(tmp_path, process):
    """Phase 4 reviewer-reproduced application defect B; MOCKED result and tool call."""
    decision = judge(provider="openai", process=process, worker_result=mocked_worker_result(),
                     tool_calls=ONE_TOOL_CALL, **analysis_kwargs(tmp_path), verdict="compatible")

    assert decision["status"] == "failed" and decision["model_selection"] is None
    assert decision["failure_reasons"] == ["worker_process_failed"]


def test_a_timed_out_worker_is_rejected_even_if_a_result_file_exists(tmp_path):
    decision = judge(provider="openai", process=TIMED_OUT, worker_result=mocked_worker_result(),
                     tool_calls=ONE_TOOL_CALL, **analysis_kwargs(tmp_path), verdict="compatible")

    assert decision["failure_reasons"] == ["deadline_exceeded"] and decision["model_selection"] is None


@pytest.mark.parametrize("process, worker_result, reason", [
    (TIMED_OUT, None, "deadline_exceeded"),
    (FINISHED, None, "worker_crashed"),
    (FINISHED, {"status": "provider_error", "error": {"code": "PROVIDER_ERROR"}}, "provider_error"),
    (FINISHED, {"status": "output_invalid", "raw_text": "MOCKED prose"}, "output_invalid"),
    (FINISHED, {**mocked_worker_result(), "run_state": "failed"}, "run_not_completed"),
    (FINISHED, mocked_worker_result(provider="groq"), "runtime_provider_mismatch"),
])
def test_each_failure_is_named(tmp_path, process, worker_result, reason):
    decision = judge(provider="openai", process=process, worker_result=worker_result, tool_calls=ONE_TOOL_CALL,
                     **analysis_kwargs(tmp_path), verdict="compatible")

    assert reason in decision["failure_reasons"] and decision["status"] == "failed"


# --- the analyze command with stand-in workers ------------------------------------------


def stub_worker(tmp_path, *, selection=None, hang=False, call_tool=True):
    """A MOCKED worker script standing in for upgrade_scout.analysis_worker (no model, no SDK)."""
    script = tmp_path / "mocked_worker.py"
    result = mocked_worker_result(selection)
    script.write_text(f"""
import json, os, sys, time
from pathlib import Path
request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print("MOCKED worker; credential seen:", os.environ.get("OPENAI_API_KEY"))
if {hang!r}:
    time.sleep(120)
if {call_tool!r}:
    with open(request["approval_log"], "a", encoding="utf-8") as log:
        log.write(json.dumps({{"tool": "comparison_evidence", "decision": "allow_once", "at": "MOCKED"}}) + "\\n")
    with open(request["tool_log"], "a", encoding="utf-8") as log:
        log.write(json.dumps({{"tool": "comparison_evidence", "at": "MOCKED", "returned": {{"verdict": 1}}}}) +"\\n")
Path(request["result_path"]).write_text(json.dumps({json.dumps(result)!s}), encoding="utf-8")
""", encoding="utf-8")
    return lambda request_path: [sys.executable, str(script), str(request_path)]


def analyze(tmp_path, report_path, worker, output="analysis", deadline=60, provider="openai"):
    return run_analyze(report_path, provider, "MOCKED-model", tmp_path / output, deadline_s=deadline,
                       state_root=tmp_path / "state", worker_command=worker)


def load_analysis(tmp_path, output="analysis"):
    return json.loads((tmp_path / output / "analysis.json").read_text(encoding="utf-8"))


def test_missing_credentials_fail_before_any_worker_runs(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def must_not_run(request_path):
        raise AssertionError("worker started without credentials")

    assert analyze(tmp_path, write_comparison(tmp_path), must_not_run) == EXIT_INVALID
    record = load_analysis(tmp_path)
    assert record["status"] == "failed" and record["failure_reasons"] == ["missing_credentials"]
    assert "OPENAI_API_KEY is not set" in record["error"] and record["model_selection"] is None


def test_a_mocked_successful_worker_yields_a_success_record_without_leaking_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_KEY)
    report_path = write_comparison(tmp_path)
    before = sha256_file(report_path)

    assert analyze(tmp_path, report_path, stub_worker(tmp_path)) == EXIT_SUCCESS

    record = load_analysis(tmp_path)
    assert record["status"] == "success" and record["factual_report"]["verdict"] == "compatible"
    assert record["model_selection"]["next_checks"][0]["model_rationale"] == "MOCKED rationale."
    assert record["tool_execution"]["python_invocations"] == 1
    assert [a["decision"] for a in record["approvals"]] == ["allow_once"]
    assert record["input"]["report_sha256"] == before == sha256_file(report_path)
    assert record["configured"]["model"] == "MOCKED-model"
    assert record["runtime"]["metadata_model"] == "brain-orchestrator"
    markdown = (tmp_path / "analysis" / "analysis.md").read_text(encoding="utf-8")
    assert "## Authoritative verdict (application-generated)" in markdown and ECHO_LIMITATION in markdown
    assert "*Model rationale (model-written):* MOCKED rationale." in markdown
    for path in (tmp_path / "analysis").rglob("*"):
        if path.is_file():
            assert FAKE_KEY not in path.read_text(encoding="utf-8", errors="replace"), path


def test_a_stalled_worker_is_killed_and_replaces_an_earlier_success(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_KEY)
    output = tmp_path / "analysis"
    output.mkdir()
    (output / OUTPUT_MARKER).write_text("", encoding="utf-8")
    (output / "analysis.json").write_text(json.dumps({"status": "success"}), encoding="utf-8")  # stale

    code = analyze(tmp_path, write_comparison(tmp_path), stub_worker(tmp_path, hang=True), deadline=3)

    record = load_analysis(tmp_path)
    assert code == EXIT_FAILED and record["status"] == "failed" and record["model_selection"] is None
    assert "deadline_exceeded" in record["failure_reasons"] and "tool_not_executed" in record["failure_reasons"]


def test_a_mocked_reply_with_unknown_ids_is_kept_only_as_unaccepted_raw_output(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_KEY)
    bad = mocked_selection(key_observations=["Z9"])

    code = analyze(tmp_path, write_comparison(tmp_path), stub_worker(tmp_path, selection=bad))

    record = load_analysis(tmp_path)
    assert code == EXIT_FAILED and record["failure_reasons"] == ["selection_invalid"]
    assert record["model_selection"] is None and record["factual_report"]["verdict"] == "compatible"
    raw = json.loads((tmp_path / "analysis" / "worker" / "model_output.json").read_text(encoding="utf-8"))
    assert raw["accepted"] is False and raw["output"]["key_observations"] == ["Z9"]


def test_an_invalid_report_is_recorded_as_a_failed_analysis(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_KEY)
    report_path = write_comparison(tmp_path)
    report_path.write_text("{not json", encoding="utf-8")

    assert analyze(tmp_path, report_path, stub_worker(tmp_path)) == EXIT_INVALID
    assert load_analysis(tmp_path)["failure_reasons"] == ["invalid_report"]


def test_the_output_dir_may_not_be_inside_the_comparison(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_KEY)
    report_path = write_comparison(tmp_path)
    before = sorted(p.name for p in report_path.parent.iterdir())

    code = run_analyze(report_path, "openai", "MOCKED-model", report_path.parent / "analysis",
                       state_root=tmp_path / "state", worker_command=stub_worker(tmp_path))

    assert code == EXIT_INVALID and sorted(p.name for p in report_path.parent.iterdir()) == before


def test_analyze_requires_an_explicit_model_for_real_providers(tmp_path):
    assert run_analyze(write_comparison(tmp_path), "openai", None, tmp_path / "a") == EXIT_INVALID


# --- the worker with a MOCKED SDK ---------------------------------------------------------


class MockedOutputError(Exception):
    def __init__(self, message, raw_text):
        super().__init__(message)
        self.raw_text = raw_text


class MockedProviderError(Exception):
    def __init__(self, message, code):
        super().__init__(message)
        self.message, self.code = message, code


def mocked_sdk(behaviour):
    """A MOCKED stand-in for the openminion module: no runtime, no model."""

    class MockedAgent:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def run(self, message, timeout_seconds, approval_callback=None):
            return behaviour({**self.kwargs, "run_approval_callback": approval_callback})

    return SimpleNamespace(Agent=MockedAgent, tool=lambda fn: fn, version="MOCKED",
                           AgentOutputValidationError=MockedOutputError, ProviderError=MockedProviderError,
                           TurnTimeoutError=TimeoutError)


# MOCKED evidence payload, in the structured shape the evidence tool returns.
MOCKED_PAYLOAD = {"summary": "MOCKED", "report_sha256": "MOCKED",
                  "verdict": {"id": "V1", "value": "compatible", "statement": "MOCKED"},
                  "scope_rules": [{"id": "S1", "statement": "MOCKED"}],
                  "observations": [{"id": "B3", "statement": "MOCKED"}],
                  "next_check_options": [{"id": "validate_with_real_provider", "action": "MOCKED",
                                          "applies_because": "MOCKED"}]}


def worker_request(tmp_path):
    return {"provider": "openai", "model": "MOCKED-model", "home": str(tmp_path / "home"),
            "tool_log": str(tmp_path / "tool_calls.jsonl"), "approval_log": str(tmp_path / "approvals.jsonl"),
            "session_id": "s", "turn_timeout": 5,
            "instructions": "MOCKED", "message": "MOCKED",
            "facts_payload": MOCKED_PAYLOAD}


def test_worker_records_that_the_tool_body_executed(tmp_path):
    def model_calls_the_tool(kwargs):
        assert kwargs["forced_tools"] == ["comparison_evidence"] and kwargs["output_type"] is ModelSelection
        payload = kwargs["tools"][0]()
        assert payload == MOCKED_PAYLOAD and payload is not MOCKED_PAYLOAD  # structured data, and a copy
        return SimpleNamespace(output=ModelSelection(**mocked_selection()), text="MOCKED", run_state="completed",
                               id="i", run_id="r", session_id="s", stats={"tool_calls": 1},
                               metadata={"provider": "openai", "model": "brain-orchestrator", "seen": payload})

    result = analysis_worker.execute(worker_request(tmp_path), sdk=mocked_sdk(model_calls_the_tool))

    assert result["status"] == "completed" and result["runtime"]["metadata_model"] == "brain-orchestrator"
    lines = (tmp_path / "tool_calls.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["returned"] for line in lines] == [
        {"verdict": 1, "scope_rules": 1, "observations": 1, "next_check_options": 1}]


def test_worker_reports_rejected_structured_output_and_no_tool_execution(tmp_path):
    def model_answers_in_prose(kwargs):
        raise MockedOutputError("did not validate", raw_text="MOCKED prose reply")

    result = analysis_worker.execute(worker_request(tmp_path), sdk=mocked_sdk(model_answers_in_prose))

    assert result["status"] == "output_invalid" and result["raw_text"] == "MOCKED prose reply"
    assert not (tmp_path / "tool_calls.jsonl").exists()


def test_worker_reports_provider_errors(tmp_path):
    def provider_down(kwargs):
        raise MockedProviderError("MOCKED connection refused", code="PROVIDER_ERROR")

    result = analysis_worker.execute(worker_request(tmp_path), sdk=mocked_sdk(provider_down))

    assert result["status"] == "provider_error" and result["error"]["code"] == "PROVIDER_ERROR"


# --- tool approval (Phase 5: the SDK held comparison_evidence for confirmation) ------------


def approvals(tmp_path):
    path = tmp_path / "approvals.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


def test_the_installed_sdk_accepts_an_approval_callback_on_agent_run():
    import inspect

    import openminion

    assert "approval_callback" in inspect.signature(openminion.Agent.run).parameters


def test_approval_allows_only_the_bound_evidence_tool_with_empty_arguments(tmp_path):
    approve = analysis_worker.make_approval_callback(tmp_path / "approvals.jsonl")

    assert approve("comparison_evidence", {}, "approval-1") is True

    [entry] = approvals(tmp_path)
    assert entry["decision"] == "allow_once" and entry["approval_id"] == "approval-1"
    assert "local write" in entry["reason"]


@pytest.mark.parametrize("tool_name", ["fs.write", "shell.exec", "installed_sdk_surface", "comparison_evidence_v2", ""])
def test_approval_denies_every_other_tool(tmp_path, tool_name):
    approve = analysis_worker.make_approval_callback(tmp_path / "approvals.jsonl")

    assert approve(tool_name, {}, "approval-2") is False
    assert approvals(tmp_path)[0]["decision"] == "deny"


@pytest.mark.parametrize("args", [{"path": "C:/Windows"}, {"report": "other.json"}, {"": None}, None, ["x"]])
def test_approval_denies_the_evidence_tool_with_unexpected_arguments(tmp_path, args):
    approve = analysis_worker.make_approval_callback(tmp_path / "approvals.jsonl")

    assert approve("comparison_evidence", args, "approval-3") is False
    [entry] = approvals(tmp_path)
    assert entry["decision"] == "deny" and "unexpected arguments" in entry["reason"]


def test_worker_routes_sdk_confirmations_through_the_callback(tmp_path):
    """MOCKED Agent: it asks for confirmation the way the SDK runner does, then calls the tool if allowed."""

    def runtime_asks_before_each_tool(kwargs):
        approve = kwargs["run_approval_callback"]
        assert approve("fs.write", {"path": "x"}, "a-1") is False          # never reaches a tool
        assert approve("comparison_evidence", {}, "a-2") is True
        kwargs["tools"][0]()                                                # runs only after approval
        return SimpleNamespace(output=ModelSelection(**mocked_selection()), text="MOCKED", run_state="completed",
                               id="i", run_id="r", session_id="s", stats={"tool_calls": 1},
                               metadata={"provider": "openai", "model": "MOCKED"})

    result = analysis_worker.execute(worker_request(tmp_path), sdk=mocked_sdk(runtime_asks_before_each_tool))

    assert result["status"] == "completed"
    assert [(a["tool"], a["decision"]) for a in approvals(tmp_path)] == [
        ("fs.write", "deny"), ("comparison_evidence", "allow_once")]
    assert len((tmp_path / "tool_calls.jsonl").read_text(encoding="utf-8").splitlines()) == 1
