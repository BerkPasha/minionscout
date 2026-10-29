"""Offline tests of the comparison logic and report rendering.

SYNTHETIC TEST FIXTURES: every record in this module is hand-built by
synthetic_record() to exercise the comparison rules. None of it is OpenMinion
release evidence; the real 0.1.8 / 0.1.15 evidence is in evidence/phase2/.
"""

import json

import pytest

from upgrade_scout.compare import (
    EXIT_COMPATIBLE, EXIT_INCONCLUSIVE, EXIT_REGRESSIONS, SCOPE, build_report, compare, render_markdown,
)
from upgrade_scout.probe import ENTRY_POINTS

SYNTHETIC_SIGNATURE = "(self, *, instructions: 'str | None' = None)"
SYNTHETIC_PARAMETERS = [
    {"name": "self", "kind": "POSITIONAL_OR_KEYWORD", "has_default": False, "default": None, "annotation": None},
    {"name": "instructions", "kind": "KEYWORD_ONLY", "has_default": True, "default": "None",
     "annotation": "str | None"},
]


def _completed(result):
    return {"status": "completed", "result": {"complete": True, **result}}


def synthetic_record(role="baseline", version="9.9.1"):
    """A SYNTHETIC probe_version record in which every probe completed."""
    surface = {
        "sdk_version": version,
        "exports": {"openminion": ["Agent", "tool"], "openminion.api": ["RuntimeTurnHandle"]},
        "export_errors": {},
        "signatures": {label: SYNTHETIC_SIGNATURE for label in ENTRY_POINTS},
        "parameters": {label: [dict(p) for p in SYNTHETIC_PARAMETERS] for label in ENTRY_POINTS},
        "unresolved": {},
    }
    echo = {"outcome": "completed", "result": {
        "run_state": "completed", "session_id": "upgrade-scout-probe", "has_run_id": True,
        "text_contains_message": True, "runtime_provider": "echo", "result_type": "AgentRunResult",
        "result_fields": ["run_state", "stats", "text"],
        "stats": {"llm_calls": 1, "tool_calls": 0, "input_tokens": 0, "output_tokens": 0},
    }}
    minimal = {"outcome": "raised", "invalid_channel_rejection": True,
               "error": {"type": "RuntimeError", "message": "synthetic: reason=invalid_channel"}}
    preflight = {"installed_version": version, "python": {"version": "3.13.5"}, "platform": "synthetic",
                 "socketpair": {"ok": True}, "asyncio_loop": {"ok": True}}
    return {
        "role": role, "requested_version": version, "evidence_dir": f"{role}-{version}",
        "environment": {"status": "ok"},
        "stages": {
            "preflight": _completed(preflight),
            "surface": _completed({"surface": surface}),
            "echo_turn": _completed(echo),
            "minimal_config": _completed(minimal),
        },
    }


def pair():
    return synthetic_record("baseline", "9.9.1"), synthetic_record("candidate", "9.9.2")


def surface_of(record):
    return record["stages"]["surface"]["result"]["surface"]


def kinds(report):
    return sorted(r["kind"] for r in report["regressions"])


def test_identical_behavior_is_compatible_without_false_regressions():
    report = compare(*pair())

    assert report["verdict"] == "compatible" and report["exit_code"] == EXIT_COMPATIBLE
    assert report["regressions"] == [] and report["complete"] is True
    assert report["exports"]["openminion"] == {"added": [], "removed": []}
    assert report["signatures"]["unchanged"] == list(ENTRY_POINTS)
    assert [b["classification"] for b in report["behavior"]] == ["unchanged", "unchanged"]


def test_added_export_is_not_a_regression():
    base, cand = pair()
    surface_of(cand)["exports"]["openminion"].append("NewThing")

    report = compare(base, cand)

    assert report["exports"]["openminion"]["added"] == ["NewThing"]
    assert report["verdict"] == "compatible"


def test_removed_export_is_a_regression():
    base, cand = pair()
    surface_of(cand)["exports"]["openminion"].remove("tool")

    report = compare(base, cand)

    assert report["exports"]["openminion"]["removed"] == ["tool"]
    assert kinds(report) == ["export_removed"]
    assert report["exit_code"] == EXIT_REGRESSIONS


def test_signature_text_change_alone_needs_review_but_is_not_a_regression():
    base, cand = pair()
    label = "openminion.Agent.run"
    surface_of(cand)["signatures"][label] = "(self, *, instructions: 'Optional[str]' = None)"
    surface_of(cand)["parameters"][label][1]["annotation"] = "Optional[str]"

    report = compare(base, cand)

    [change] = report["signatures"]["changed"]
    assert change["entry_point"] == label
    assert change["modified"] == {"instructions": {"annotation": {"baseline": "str | None", "candidate": "Optional[str]"}}}
    assert change["removed"] == [] and change["added_required"] == []
    assert report["regressions"] == [] and report["verdict"] == "compatible"


def test_added_optional_parameter_is_not_a_regression():
    base, cand = pair()
    label = "openminion.Agent"
    surface_of(cand)["signatures"][label] = SYNTHETIC_SIGNATURE[:-1] + ", verbose: bool = False)"
    surface_of(cand)["parameters"][label].append(
        {"name": "verbose", "kind": "KEYWORD_ONLY", "has_default": True, "default": "False", "annotation": "bool"})

    report = compare(base, cand)

    assert report["signatures"]["changed"][0]["added_optional"] == ["verbose"]
    assert report["regressions"] == []


def test_removed_and_newly_required_parameters_are_regressions():
    base, cand = pair()
    label = "openminion.tool"
    surface_of(cand)["signatures"][label] = "(self, *, name: str)"
    surface_of(cand)["parameters"][label] = [
        SYNTHETIC_PARAMETERS[0],
        {"name": "name", "kind": "KEYWORD_ONLY", "has_default": False, "default": None, "annotation": "str"},
    ]

    report = compare(base, cand)

    assert kinds(report) == ["parameter_now_required", "parameter_removed"]
    assert report["verdict"] == "regressions_detected"


def test_symbol_missing_in_candidate_becomes_evidence_not_a_crash():
    base, cand = pair()
    label = "openminion.Agent.run_stream"
    del surface_of(cand)["signatures"][label]
    del surface_of(cand)["parameters"][label]
    surface_of(cand)["unresolved"][label] = {"type": "AttributeError", "message": "synthetic: no run_stream"}

    report = compare(base, cand)

    assert report["signatures"]["unresolved_in_candidate"][0]["entry_point"] == label
    assert kinds(report) == ["entry_point_missing"]
    assert report["coverage_gaps"] == []  # the absence itself is the observed regression
    assert "openminion.Agent.run_stream" in render_markdown(build_report(base, cand, request={}))


def _unresolve(record, label, error_type="AttributeError"):
    surface = surface_of(record)
    del surface["signatures"][label]
    del surface["parameters"][label]
    surface["unresolved"][label] = {"type": error_type, "message": "synthetic"}


def test_entry_point_unresolved_in_both_versions_is_a_coverage_gap_and_inconclusive():
    """Reviewer-reproduced defect 1: this case used to report compatible with complete=true."""
    base, cand = pair()
    label = "openminion.Agent.run_stream"
    for record in (base, cand):
        _unresolve(record, label)

    report = compare(base, cand)

    assert report["signatures"]["unresolved_in_both"] == [label]
    assert [(g["symbol"], g["unmeasured_in"]) for g in report["coverage_gaps"]] == [(label, "baseline and candidate")]
    assert report["regressions"] == []
    assert report["complete"] is False
    assert report["verdict"] == "inconclusive" and report["exit_code"] == EXIT_INCONCLUSIVE


def test_export_root_unavailable_in_both_versions_is_a_coverage_gap_and_inconclusive():
    base, cand = pair()
    for record in (base, cand):
        del surface_of(record)["exports"]["openminion.api"]
        surface_of(record)["export_errors"]["openminion.api"] = {"type": "ModuleNotFoundError", "message": "synthetic"}

    report = compare(base, cand)

    assert [g["symbol"] for g in report["coverage_gaps"]] == ["openminion.api"]
    assert report["regressions"] == [] and report["verdict"] == "inconclusive"


def test_entry_point_unresolved_only_in_baseline_is_a_coverage_gap_not_a_regression():
    base, cand = pair()
    _unresolve(base, "openminion.tool")

    report = compare(base, cand)

    assert report["coverage_gaps"][0]["unmeasured_in"] == "baseline"
    assert report["regressions"] == [] and report["verdict"] == "inconclusive"


def test_unintrospectable_candidate_signature_is_a_coverage_gap_not_a_missing_symbol():
    base, cand = pair()
    _unresolve(cand, "openminion.tool", error_type="ValueError")

    report = compare(base, cand)

    assert report["coverage_gaps"][0]["unmeasured_in"] == "candidate"
    assert report["regressions"] == [] and report["verdict"] == "inconclusive"


def test_candidate_export_root_without_all_is_a_coverage_gap_not_a_regression():
    base, cand = pair()
    del surface_of(cand)["exports"]["openminion.api"]
    surface_of(cand)["export_errors"]["openminion.api"] = {"type": "AttributeError", "message": "synthetic: no __all__"}

    report = compare(base, cand)

    assert [g["symbol"] for g in report["coverage_gaps"]] == ["openminion.api"]
    assert report["regressions"] == []


def test_an_observed_regression_takes_precedence_over_a_coverage_gap():
    base, cand = pair()
    _unresolve(base, "openminion.Agent.run_stream")
    _unresolve(cand, "openminion.Agent.run_stream")
    surface_of(cand)["exports"]["openminion"].remove("tool")

    report = compare(base, cand)

    assert kinds(report) == ["export_removed"]
    assert report["verdict"] == "regressions_detected" and report["complete"] is False


def test_export_root_that_fails_to_import_in_candidate_is_a_regression():
    base, cand = pair()
    del surface_of(cand)["exports"]["openminion.api"]
    surface_of(cand)["export_errors"]["openminion.api"] = {"type": "ModuleNotFoundError", "message": "synthetic"}

    report = compare(base, cand)

    assert kinds(report) == ["export_root_unavailable"]


def test_echo_turn_that_starts_failing_is_a_behavior_regression():
    base, cand = pair()
    cand["stages"]["echo_turn"] = _completed(
        {"outcome": "raised", "error": {"type": "RuntimeError", "message": "synthetic failure"}})

    report = compare(base, cand)

    assert report["behavior"][0]["classification"] == "regression"
    assert kinds(report) == ["behavior_regression"]
    assert report["exit_code"] == EXIT_REGRESSIONS


def echo_summary(record):
    return record["stages"]["echo_turn"]["result"]["result"]


def test_completed_echo_reply_without_the_message_breaks_the_contract():
    """Reviewer-reproduced defect 2: this case used to report compatible, classified only as changed."""
    base, cand = pair()
    echo_summary(cand)["text_contains_message"] = False

    report = compare(base, cand)

    echo = report["behavior"][0]
    assert (echo["baseline"], echo["candidate"]) == ("contract_met", "contract_failed")
    assert echo["contract_checks"]["candidate"]["echoed_message"] is False
    assert echo["classification"] == "regression"
    assert kinds(report) == ["behavior_regression"] and report["verdict"] == "regressions_detected"


@pytest.mark.parametrize("field, value, check", [
    ("runtime_provider", "openai", "echo_provider"),
    ("session_id", "some-other-session", "session_preserved"),
    ("run_state", "failed", "completed"),
])
def test_each_echo_contract_check_can_fail_the_candidate(field, value, check):
    base, cand = pair()
    echo_summary(cand)[field] = value

    report = compare(base, cand)

    assert report["behavior"][0]["contract_checks"]["candidate"][check] is False
    assert report["verdict"] == "regressions_detected"


def test_echo_contract_failing_in_both_versions_is_never_compatible():
    base, cand = pair()
    for record in (base, cand):
        echo_summary(record)["text_contains_message"] = False

    report = compare(base, cand)

    assert report["behavior"][0]["classification"] == "failing_in_both"
    assert report["regressions"] == [] and report["verdict"] == "inconclusive"


def test_echo_telemetry_difference_alone_is_informational():
    base, cand = pair()
    echo_summary(cand)["stats"]["llm_calls"] = 2
    echo_summary(cand)["result_fields"].append("extra")

    report = compare(base, cand)

    echo = report["behavior"][0]
    assert echo["classification"] == "changed" and set(echo["differences"]) == {"llm_calls", "result_fields"}
    assert report["regressions"] == [] and report["verdict"] == "compatible"


def test_minimal_config_fix_is_reported_as_a_change_not_a_regression():
    base, cand = pair()
    cand["stages"]["minimal_config"] = _completed({"outcome": "completed", "invalid_channel_rejection": False})

    report = compare(base, cand)

    minimal = report["behavior"][1]
    assert (minimal["baseline"], minimal["candidate"]) == ("rejected_invalid_channel", "accepted")
    assert minimal["classification"] == "fixed"
    assert report["regressions"] == [] and report["verdict"] == "compatible"


def test_minimal_config_that_stops_working_is_a_regression():
    base, cand = pair()
    base["stages"]["minimal_config"] = _completed({"outcome": "completed", "invalid_channel_rejection": False})

    report = compare(base, cand)

    assert report["behavior"][1]["classification"] == "regression"


def test_install_failure_is_an_inconclusive_environment_failure():
    base, cand = pair()
    cand["environment"] = {"status": "failed", "failure": "install_failed", "detail": "synthetic"}
    cand["stages"] = {stage: {"status": "not_run", "reason": "environment install_failed"} for stage in cand["stages"]}

    report = compare(base, cand)

    assert report["verdict"] == "inconclusive" and report["exit_code"] == EXIT_INCONCLUSIVE
    assert [f["kind"] for f in report["environment_failures"]] == ["install_failed"]
    assert report["exports"] is None and report["regressions"] == []


def test_worker_timeout_is_incomplete_and_not_an_sdk_failure():
    base, cand = pair()
    cand["stages"]["echo_turn"] = {"status": "timeout", "last_step": "agent_run"}

    report = compare(base, cand)

    assert report["incomplete"][0]["stage"] == "echo_turn"
    assert report["behavior"][0]["classification"] == "not_comparable"
    assert report["regressions"] == [] and report["verdict"] == "inconclusive"


def test_preflight_loopback_failure_is_an_environment_failure():
    base, cand = pair()
    cand["stages"]["preflight"]["result"]["socketpair"] = {"ok": False, "error": {"type": "OSError"}}
    for stage in ("echo_turn", "minimal_config"):
        cand["stages"][stage] = {"status": "not_run", "reason": "loopback socketpair or asyncio event loop failed"}

    report = compare(base, cand)

    assert "socketpair_failed" in [f.get("kind") for f in report["environment_failures"]]
    assert report["verdict"] == "inconclusive"


def test_a_regression_takes_precedence_over_incomplete_stages():
    base, cand = pair()
    surface_of(cand)["exports"]["openminion"].remove("Agent")
    cand["stages"]["minimal_config"] = {"status": "timeout", "last_step": "agent_run"}

    report = compare(base, cand)

    assert report["verdict"] == "regressions_detected" and report["complete"] is False


def test_required_probe_failing_in_both_versions_is_inconclusive():
    base, cand = pair()
    for record in (base, cand):
        record["stages"]["echo_turn"] = _completed({"outcome": "raised", "error": {"type": "RuntimeError"}})

    report = compare(base, cand)

    assert report["behavior"][0]["classification"] == "failing_in_both"
    assert report["verdict"] == "inconclusive"


@pytest.mark.parametrize("make_incomplete", [False, True])
def test_markdown_states_scope_and_never_claims_compatible_when_incomplete(make_incomplete):
    base, cand = pair()
    if make_incomplete:
        cand["stages"]["surface"] = {"status": "crashed", "last_step": "collect_surface"}

    report = build_report(base, cand, request={})
    markdown = render_markdown(report)
    json.dumps(report)  # report.json must be serializable

    assert "prove neither real model inference nor model-driven tool execution" in markdown
    assert SCOPE[0] in markdown
    if make_incomplete:
        assert report["verdict"] == "inconclusive" and "**Verdict: inconclusive**" in markdown
        assert "Verdict: compatible" not in markdown
    else:
        assert "**Verdict: compatible**" in markdown
        assert "| tool_calls | 0 | 0 |" in markdown
        assert "| echoed_message | the reply text contains the probe message | True | True |" in markdown
        assert "## Coverage gaps" in markdown and "every export root and entry point was measured" in markdown
