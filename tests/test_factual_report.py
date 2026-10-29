"""The application-owned factual report and the bounded model role (analysis schema 2).

SYNTHETIC comparisons come from test_compare's fixtures; MOCKED selections are hand-written.
One test reads the real attempt-3 model output from evidence/ and modifies it; that
derivative is labelled SYNTHETIC. Nothing here is live evidence of model behavior.
"""

import json
from pathlib import Path

import pytest

from test_analysis import FAKE_KEY, analyze, load_analysis, mocked_selection, stub_worker, write_comparison
from test_compare import _unresolve, echo_summary
from upgrade_scout.analysis import (
    ModelSelection, factual_report, next_check_options, resolve_selection, validate_inputs, validate_selection,
)

REPO = Path(__file__).resolve().parents[1]
ATTEMPT_3_RESULT = REPO / "evidence/phase5/analysis/openai-attempt-3/worker/result.json"
PHASE3_REPORT = REPO / "evidence/phase3/compare/0.1.8-vs-0.1.15/report.json"


def regression(base, cand):
    echo_summary(cand)["text_contains_message"] = False


def coverage_gap(base, cand):
    for record in (base, cand):
        _unresolve(record, "openminion.Agent.run_stream")


def inputs(tmp_path, mutate=None):
    report, facts, _ = validate_inputs(write_comparison(tmp_path, mutate))
    return report, facts, next_check_options(report, facts)


def option_ids(options):
    return {o["id"] for o in options}


# --- 1. the verdict belongs to the application ---------------------------------------------


def test_the_model_output_contract_has_no_verdict_or_free_text_fields():
    assert set(ModelSelection.model_fields) == {"key_observations", "relevant_limitations", "next_checks"}


@pytest.mark.parametrize("mutate, verdict", [(None, "compatible"), (regression, "regressions_detected"),
                                             (coverage_gap, "inconclusive")])
def test_the_rendered_verdict_comes_from_the_comparison_whatever_the_model_says(tmp_path, monkeypatch, mutate,
                                                                                 verdict):
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_KEY)
    claims_compatible = mocked_selection(
        key_observations=["B1"],
        next_checks=[{"check_id": "validate_with_real_provider", "rationale": "MOCKED: worth a live run.",
                      "evidence": []}])

    analyze(tmp_path, write_comparison(tmp_path, mutate), stub_worker(tmp_path, selection=claims_compatible))

    record = load_analysis(tmp_path)
    assert record["factual_report"]["verdict"] == record["input"]["deterministic_verdict"] == verdict
    markdown = (tmp_path / "analysis" / "analysis.md").read_text(encoding="utf-8")
    assert f"## Authoritative verdict (application-generated)\n\n**{verdict}**" in markdown


# --- 2. scope rules are not measured results -------------------------------------------------


@pytest.mark.parametrize("field, value, expected", [
    ("key_observations", ["S3"], "key_observations: 'S3' is a scope_rule fact, not observation"),
    ("key_observations", ["V1"], "key_observations: 'V1' is a verdict fact, not observation"),
    ("relevant_limitations", ["X1"], "relevant_limitations: 'X1' is a observation fact, not scope_rule"),
])
def test_fact_categories_are_enforced(tmp_path, field, value, expected):
    report, facts, options = inputs(tmp_path)

    selection, problems = validate_selection(mocked_selection(**{field: value}), facts, options, "compatible")

    assert selection is None and expected in problems


def test_scope_rules_never_appear_among_the_measured_results(tmp_path):
    report, facts, _ = inputs(tmp_path)
    scope = {f["statement"] for f in facts if f["category"] == "scope_rule"}

    rendered = factual_report(report, facts)

    assert not scope & {edge["statement"] for edge in rendered["known_rough_edges"]}
    assert not any(s in rendered["summary"] for s in scope)
    assert [s["statement"] for s in rendered["scope_limitations"]] == [f["statement"] for f in facts
                                                                       if f["category"] == "scope_rule"]


# --- 3. no-change evidence renders no changes and no gaps ------------------------------------


def test_unchanged_evidence_renders_no_export_or_signature_changes_and_no_gaps(tmp_path):
    report, facts, options = inputs(tmp_path)

    rendered = factual_report(report, facts)
    core = rendered["core_results"]

    assert all(e["added"] == [] and e["removed"] == [] for e in core["exports"])
    assert core["signatures"]["changed"] == [] and core["coverage_gaps"] == [] and core["regressions"] == []
    assert "Exports: no additions or removals" in rendered["summary"] and "Coverage gaps: none" in rendered["summary"]
    assert {"C0", "R0", "N0"} <= {f["id"] for f in facts}
    assert not option_ids(options) & {"review_signature_changes", "fill_coverage_gaps", "review_added_exports",
                                      "investigate_regressions"}


@pytest.mark.parametrize("check_id", ["review_signature_changes", "fill_coverage_gaps", "investigate_regressions"])
def test_a_check_the_evidence_does_not_support_is_rejected(tmp_path, check_id):
    report, facts, options = inputs(tmp_path)
    data = mocked_selection(next_checks=[{"check_id": check_id, "rationale": "MOCKED", "evidence": []}])

    selection, problems = validate_selection(data, facts, options, "compatible")

    assert selection is None and f"next_checks[0]: {check_id!r} is not an applicable next-check option" in problems


def test_repeated_checks_and_verdict_citations_are_rejected(tmp_path):
    report, facts, options = inputs(tmp_path)
    check = {"check_id": "validate_with_real_provider", "rationale": "MOCKED", "evidence": ["V1"]}

    selection, problems = validate_selection(mocked_selection(next_checks=[check, check]), facts, options,
                                             "compatible")

    assert selection is None
    assert "next_checks repeats a check_id" in problems
    assert "next_checks[0].evidence: 'V1' is a verdict fact, not observation or scope_rule" in problems


# --- 4. the minimal-config rejection stays visible -------------------------------------------


def test_the_minimal_config_rejection_is_reported_even_if_the_model_ignores_it(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_KEY)
    ignores_it = mocked_selection(key_observations=["X1"])

    analyze(tmp_path, write_comparison(tmp_path), stub_worker(tmp_path, selection=ignores_it))

    record = load_analysis(tmp_path)
    assert record["status"] == "success"
    assert record["factual_report"]["core_results"]["minimal_config"]["candidate"] == "rejected_invalid_channel"
    assert ["B3"] in [edge["facts"] for edge in record["factual_report"]["known_rough_edges"]]
    assert "set_default_channel" in option_ids(record["next_check_options"])
    markdown = (tmp_path / "analysis" / "analysis.md").read_text(encoding="utf-8")
    assert "| documented minimal config | rejected_invalid_channel / rejected_invalid_channel" in markdown


# --- 5. model text cannot enter the factual report -------------------------------------------


def test_a_fabricated_claim_in_a_rationale_stays_labelled_and_out_of_the_facts(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_KEY)
    fabricated = "MOCKED FABRICATION: twelve exports were added and Agent.run changed."
    lying = mocked_selection(next_checks=[{"check_id": "validate_with_real_provider", "rationale": fabricated,
                                           "evidence": ["S2"]}])

    analyze(tmp_path, write_comparison(tmp_path), stub_worker(tmp_path, selection=lying), output="with_model")
    record = load_analysis(tmp_path, "with_model")

    report, facts, _ = inputs(tmp_path / "independent")
    assert record["factual_report"] == factual_report(report, facts)       # identical with or without the model
    assert fabricated not in json.dumps(record["factual_report"])
    markdown = (tmp_path / "with_model" / "analysis.md").read_text(encoding="utf-8")
    factual_part = markdown.split("## Model contribution")[0]
    assert fabricated not in factual_part
    assert f"*Model rationale (model-written):* {fabricated}" in markdown


def test_selected_ids_resolve_to_canonical_statements_only(tmp_path):
    report, facts, options = inputs(tmp_path)
    selection, problems = validate_selection(mocked_selection(), facts, options, "compatible")

    resolved = resolve_selection(selection, facts, options)

    canonical = {f["id"]: f["statement"] for f in facts}
    assert problems == []
    assert all(item["statement"] == canonical[item["id"]] for item in resolved["key_observations"])
    actions = {o["id"]: o["action"] for o in options}
    assert all(check["action"] == actions[check["check_id"]] for check in resolved["next_checks"])


# --- 6. known citations alone do not make statements true (attempt-3 failure class) ---------


@pytest.mark.skipif(not ATTEMPT_3_RESULT.exists(), reason="the attempt-3 evidence is not present")
def test_attempt3_output_with_only_its_verdict_corrected_is_still_rejected():
    """SYNTHETIC derivative of the real attempt-3 output: only its verdict changed to "compatible"."""
    output = json.loads(ATTEMPT_3_RESULT.read_text(encoding="utf-8"))["output"]
    output["verdict"] = "compatible"
    report, facts, _ = validate_inputs(PHASE3_REPORT)
    cited = {i for section in ("observed", "untested") for item in output[section] for i in item["evidence"]}
    assert cited <= {f["id"] for f in facts}                              # every citation is a known id ...

    selection, problems = validate_selection(output, facts, next_check_options(report, facts), "compatible")

    assert selection is None and any(p.startswith("schema:") for p in problems)   # ... yet it cannot be accepted
    rendered = factual_report(report, facts)                               # and the facts say the opposite
    assert "Exports: no additions or removals" in rendered["summary"]
    assert rendered["core_results"]["signatures"]["changed"] == [] and rendered["core_results"]["coverage_gaps"] == []


# --- 7. distinct authoritative outcomes ------------------------------------------------------


def test_compatible_regression_and_inconclusive_stay_distinct(tmp_path):
    outcomes = {}
    for name, mutate in (("compatible", None), ("regression", regression), ("inconclusive", coverage_gap)):
        report, facts, options = inputs(tmp_path / name, mutate)
        outcomes[name] = (factual_report(report, facts), option_ids(options))

    assert [(r["verdict"], r["exit_code"]) for r, _ in outcomes.values()] == [
        ("compatible", 0), ("regressions_detected", 1), ("inconclusive", 3)]
    assert "investigate_regressions" in outcomes["regression"][1]
    assert "fill_coverage_gaps" in outcomes["inconclusive"][1]
    assert outcomes["regression"][0]["core_results"]["regressions"]
    assert outcomes["inconclusive"][0]["core_results"]["coverage_gaps"][0]["symbol"] == "openminion.Agent.run_stream"
