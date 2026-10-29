"""Upgrade analysis for one saved comparison: ``python -m upgrade_scout analyze``.

Every factual statement in the result is written by this application from the
validated comparison: the authoritative verdict, the summary, the core results,
the scope limitations and the known rough edges. The model's role is narrow. One
OpenMinion Agent turn runs in a child process (upgrade_scout.analysis_worker)
under an external deadline; the agent must call a no-argument @tool bound to the
validated facts, then reply with a ModelSelection that ranks observation ids,
picks scope-rule ids, and ranks next checks chosen from options this application
derived as applicable. The application resolves every id to its canonical
statement. The only model-written text kept is the labelled rationale of each
ranked next check. A selection is accepted only if a real (non-echo) provider ran,
the tool's Python code was seen to execute, and the selection passes validation.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from . import __version__
from .compare import (
    _VERDICT_TEXT as VERDICT_TEXT,
    COMPARISON_FIELDS, ECHO_CONTRACT, REPORT_SCHEMA, SCOPE, EvidenceError, compare, default_state_root,
    evidence_file, load_records, load_report, run_bounded, sha256_file, version_facts,
)
from .home import PROVIDER_KEY_ENV, missing_credential
from .probe import ENTRY_POINTS, redact, write_text_atomic

# 2: application-rendered factual report; the model returns a ModelSelection, not prose.
ANALYSIS_SCHEMA = "minion-upgrade-scout/analysis/2"
OUTPUT_MARKER = ".upgrade-scout-analysis"
TOOL_NAME = "comparison_evidence"
SESSION_ID = "upgrade-scout-analysis"

EXIT_SUCCESS = 0
EXIT_FAILED = 1
EXIT_INVALID = 2

# Tool-result transport limits of the pinned SDK (openminion 0.1.15, modules/brain/constants.py; the same
# values are in 0.1.8). Before the model sees a tool result, the SDK silently cuts each string past 1200
# characters, keeps the first 16 items of a list or dict, and replaces containers nested 8 deep; it shortens
# a tool's "summary" to 600 characters (modules/brain/adapters/tool/results.py). Phase 5 finding F9.
TOOL_MESSAGE_STRING_LIMIT = 1200
TOOL_MESSAGE_SEQUENCE_LIMIT = 16
TOOL_MESSAGE_DEPTH_LIMIT = 8
TOOL_SUMMARY_LIMIT = 600

ECHO_LIMITATION = (
    "The comparison's echo-provider probes make no model call: they prove neither real model inference "
    "nor model-driven tool execution."
)
_PROVIDER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_\-]*$")

FAILURE_TEXT = {
    "invalid_report": "The comparison report or its evidence failed validation; nothing was sent to a model.",
    "payload_exceeds_transport_limits": "The evidence payload would not reach the model intact under the pinned "
                                        "SDK's tool-result limits; nothing was sent to a model.",
    "missing_credentials": "The provider's credential variable is not set; nothing was sent to a model.",
    "echo_provider_is_not_a_model": "The echo provider is not a model, so an echo run can only be test evidence.",
    "deadline_exceeded": "The worker process did not finish before the external deadline and was killed.",
    "worker_crashed": "The worker process exited successfully but wrote no result.",
    "worker_process_failed": "The worker process could not start or exited with a non-zero code; any result file "
                             "it left is not trusted.",
    "provider_error": "The provider failed (ProviderError).",
    "turn_timeout": "Agent.run hit its own timeout (TurnTimeoutError).",
    "output_invalid": "The SDK rejected the reply against the ModelSelection output_type (AgentOutputValidationError); "
                      "that exception carries the reply text but no run_id or stats, so run identity is unavailable.",
    "error": "The worker raised an unexpected exception.",
    "run_not_completed": "The turn returned but its run_state is not 'completed'.",
    "tool_not_executed": "The evidence tool's Python implementation never ran during the turn.",
    "selection_invalid": "The model's selection failed validation: an unknown or wrong-category id, an inapplicable "
                         "or repeated next check, or a rationale that contradicts the verdict.",
    "runtime_provider_mismatch": "The runtime reported a different provider than the one configured.",
    "source_report_changed": "The comparison report changed while the analysis ran.",
}

AUTOMATIC_CHECKS = [
    "the comparison report matches its raw evidence, and its declarations match this tool's definitions",
    "the evidence payload fits the pinned SDK's tool-result limits (checked before any model call), so it is not "
    "cut on its way to the model",
    "the verdict and every measured result are rendered by this application, never by the model",
    "the reply matches ModelSelection exactly (extra fields such as a verdict or summary are rejected)",
    "key_observations are observation facts; relevant_limitations are scope-rule facts; ids exist",
    "every ranked next check is one of the options this application derived as applicable",
    "the evidence tool's Python body executed (tool_calls.jsonl), after a scoped allow_once approval",
    "a real provider ran, the worker exited 0, the turn completed, and the source report hash is unchanged",
]
HUMAN_REVIEW = [
    "whether the model's ranking of observations and next checks is sensible for your agent",
    "the model-written rationales, which are recommendations and may still be misleading",
    "whether the applicable next checks are sufficient; this tool only offers checks the evidence supports",
]


# --- the model's bounded output --------------------------------------------------------


class RankedCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check_id: str = Field(description="an id from next_check_options")
    rationale: str = Field(min_length=1, max_length=400,
                           description="why this check matters for this upgrade; a recommendation, not a fact")
    evidence: list[str] = Field(default_factory=list, max_length=6,
                                description="ids of observation or scope_rule facts the rationale relies on")


class ModelSelection(BaseModel):
    """The only reply shape accepted from the model: ids and rankings, no measured results."""

    model_config = ConfigDict(extra="forbid")
    key_observations: list[str] = Field(min_length=1, max_length=6,
                                        description="ids of observation facts, most important first")
    relevant_limitations: list[str] = Field(min_length=1, max_length=5,
                                            description="ids of scope_rule facts that most limit this comparison")
    next_checks: list[RankedCheck] = Field(min_length=1, max_length=5,
                                           description="checks from next_check_options, most important first")


def instructions() -> str:
    schema = json.dumps(ModelSelection.model_json_schema(), separators=(",", ":"))
    return (
        "You are Minion Upgrade Scout. The application has already written the factual upgrade report from a "
        "deterministic comparison. Your job is to prioritize it.\n"
        f"1. First call the {TOOL_NAME} tool. It takes no arguments. It returns the verdict, scope_rules, "
        "observations and next_check_options; every item has an id.\n"
        "2. Then reply with one JSON object and nothing else, matching this JSON schema:\n"
        f"{schema}\n"
        "Rules:\n"
        "- key_observations: ids from observations, most important for someone upgrading first.\n"
        "- relevant_limitations: ids from scope_rules that most limit what this comparison shows. A scope rule is "
        "not a measured result.\n"
        "- next_checks: choose check_id values from next_check_options only, most important first. Give each a "
        "one- or two-sentence rationale and the ids from observations or scope_rules it relies on.\n"
        "- Use only ids returned by the tool. Do not include a verdict, a summary, or any other field: the "
        "application renders the verdict and all measured results itself.\n"
        "- A rationale is a recommendation. Do not state results that the cited facts do not contain, and do not "
        "state or imply that the upgrade is safe for arbitrary agents, real model providers, or production use."
    )


def run_message(baseline: str, candidate: str) -> str:
    """The turn's user message, which repeats the full instructions.

    In an offline capture of the installed SDK's provider requests, the per-run system
    prompt (Agent.instructions) was cut to its identity budget and was absent from the
    requests made after the tool result, while the user message reached every request.
    """
    return f"Prioritize the upgrade evidence for openminion {baseline} -> {candidate}.\n\n{instructions()}"


# --- validated input and the facts the tool returns ----------------------------------


def validate_inputs(report_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, str]]]:
    """Load a current-schema report, confirm it matches its raw evidence, and build its facts.

    Returns (report, facts, evidence_files with sha256). Raises EvidenceError.
    """
    report = load_report(report_path)
    if report["schema"] != REPORT_SCHEMA:
        raise EvidenceError(
            f"report schema {report['schema']!r} is not the current {REPORT_SCHEMA!r}; "
            "run `python -m upgrade_scout recheck` or a new `compare` first"
        )
    records = load_records(report_path, report)
    fresh = compare(records["baseline"], records["candidate"])
    mismatched = [key for key in COMPARISON_FIELDS if fresh[key] != report.get(key)]
    if mismatched:
        raise EvidenceError(f"report.json does not match its raw evidence (fields: {', '.join(mismatched)})")
    # Declarations are fixed by the schema and probe definitions, not by the report file.
    if report.get("scope") != SCOPE:
        raise EvidenceError("report scope differs from this tool's schema-2 probe definitions")
    if report.get("echo_contract") != ECHO_CONTRACT:
        raise EvidenceError("report echo_contract differs from this tool's echo contract definition")
    for role, record in records.items():
        expected = version_facts(record)
        stored = report["versions"][role]
        wrong = sorted(key for key in expected if stored.get(key) != expected[key])
        if wrong:
            raise EvidenceError(f"versions.{role} does not match its raw evidence (fields: {', '.join(wrong)})")
    # Facts come from the recomputed comparison and the raw records, never from report text.
    facts = build_facts(fresh, records)
    paths = sorted({path for fact in facts for path in fact["evidence"]})
    evidence_files = []
    for relative in paths:
        target = report_path if relative == "report.json" else evidence_file(report_path.parent, *relative.split("/"))
        if not target.is_file():
            raise EvidenceError(f"referenced evidence file is missing: {relative}")
        evidence_files.append({"path": relative, "sha256": sha256_file(target)})
    return report, facts, evidence_files


def _stage_file(record: dict[str, Any], stage: str) -> str | None:
    name = record["stages"][stage].get("evidence")
    return f"{record['evidence_dir']}/{name}" if name else None


def _files(*paths: str | None) -> list[str]:
    return [p for p in paths if p] or ["report.json"]


def _surface_counts(record: dict[str, Any]) -> dict[str, int]:
    surface = (record["stages"]["surface"].get("result") or {}).get("surface") or {}
    return {root: len(names) for root, names in (surface.get("exports") or {}).items()}


def _names(values: list[str]) -> str:
    return ", ".join(values) or "none"


def build_facts(comparison: dict[str, Any], records: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Number the facts, from a recomputed comparison and raw evidence records.

    Each fact has a category: "verdict" (V1), "scope_rule" (S*: what the probes cover,
    not a measured result) or "observation" (everything measured). Absences are stated
    as observations too (R0, C0, N0), so nothing has to be inferred from a scope rule.
    """
    facts: list[dict[str, Any]] = []

    def add(fact_id: str, category: str, statement: str, evidence: list[str], data: Any = None) -> None:
        fact = {"id": fact_id, "category": category, "statement": statement, "evidence": evidence}
        if data is not None:
            fact["data"] = data
        facts.append(fact)

    base, cand = records["baseline"], records["candidate"]
    b_ver, c_ver = base["requested_version"], cand["requested_version"]
    add("V1", "verdict", f"Deterministic verdict for openminion {b_ver} -> {c_ver}: {comparison['verdict']} "
                         f"(exit code {comparison['exit_code']}); comparison complete: {comparison['complete']}.",
        ["report.json"])
    for i, line in enumerate(SCOPE, 1):
        add(f"S{i}", "scope_rule", line, ["report.json"])
    for fact_id, role, record in (("P1", "baseline", base), ("P2", "candidate", cand)):
        v = version_facts(record)
        add(fact_id, "observation", f"The {role} requested openminion {v['requested_version']}; installed "
                                    f"{v['installed_version']}; imported __version__ {v['imported_version']}; "
                                    f"Python {v['python']} on {v['platform']}; environment "
                                    f"{v['environment']['status']}.",
            _files(f"{record['evidence_dir']}/environment.json", _stage_file(record, "preflight")))

    surfaces = _files(_stage_file(base, "surface"), _stage_file(cand, "surface"))
    if not comparison["regressions"]:
        add("R0", "observation", "No regressions were observed in the executed probes.", ["report.json"])
    for i, regression in enumerate(comparison["regressions"], 1):
        detail = f" ({regression['detail']})" if regression.get("detail") else ""
        add(f"R{i}", "observation", f"Regression {regression['kind']}: {regression['symbol']}{detail}.",
            ["report.json"])
    if comparison["exports"] is not None:
        b_counts, c_counts = _surface_counts(base), _surface_counts(cand)
        for i, (root, entry) in enumerate(comparison["exports"].items(), 1):
            if "added" in entry:
                data = {"root": root, "comparable": True, "baseline_count": b_counts.get(root),
                        "candidate_count": c_counts.get(root), "added": entry["added"], "removed": entry["removed"]}
                statement = (f"Exports of {root}: {data['baseline_count']} names in {b_ver}, "
                             f"{data['candidate_count']} in {c_ver}; added: {_names(entry['added'])}; "
                             f"removed: {_names(entry['removed'])}.")
            else:
                data = {"root": root, "comparable": False}
                statement = f"Exports of {root} could not be compared: {entry}."
            add(f"X{i}", "observation", statement, surfaces, data)
    if comparison["signatures"] is not None:
        sigs = comparison["signatures"]
        changed = [change["entry_point"] for change in sigs["changed"]]
        add("G1", "observation", f"Entry-point signatures: {len(sigs['unchanged'])} of {len(ENTRY_POINTS)} identical "
                                 f"in both versions ({_names(sigs['unchanged'])}); {len(changed)} changed.",
            surfaces, {"identical": sigs["unchanged"], "changed": changed})
        for i, change in enumerate(sigs["changed"], 2):
            details = {k: change[k] for k in ("removed", "added_required", "added_optional", "modified") if change[k]}
            add(f"G{i}", "observation", f"Signature of {change['entry_point']} changed: {details}.", surfaces)
        if not comparison["coverage_gaps"]:
            add("C0", "observation", "No coverage gaps: every export root and entry point was measured in both "
                                     "versions.", surfaces)
    for i, gap in enumerate(comparison["coverage_gaps"], 1):
        add(f"C{i}", "observation", f"Coverage gap: {gap['symbol']} ({gap['target']}) was not measured in "
                                    f"{gap['unmeasured_in']}.", surfaces)
    problems = comparison["environment_failures"] + comparison["incomplete"]
    if not problems:
        add("N0", "observation", "No environment failures or incomplete stages.", ["report.json"])
    for i, problem in enumerate(problems, 1):
        where = f" in stage {problem['stage']}" if problem.get("stage") else ""
        add(f"N{i}", "observation", f"{problem['role']} {problem['version']}: {problem['kind']}{where}"
                                    f"{': ' + str(problem['detail']) if problem.get('detail') else ''}.",
            _files(problem.get("evidence")))

    echo, minimal = comparison["behavior"]
    echo_files = _files(_stage_file(base, "echo_turn"), _stage_file(cand, "echo_turn"))
    if echo.get("contract_checks"):
        failed = {side: [k for k, ok in checks.items() if not ok] for side, checks in echo["contract_checks"].items()}
        add("B1", "observation", f"Echo contract ({', '.join(ECHO_CONTRACT)}): baseline {echo['baseline']}, candidate "
                                 f"{echo['candidate']}; failed checks {failed}; classification "
                                 f"{echo['classification']}.", echo_files)
        observed = echo["observed"]
        add("B2", "observation", "Echo telemetry (no model call): " + "; ".join(
            f"{side} llm_calls={view['llm_calls']} tool_calls={view['tool_calls']} "
            f"input_tokens={view['input_tokens']} output_tokens={view['output_tokens']}"
            for side, view in observed.items()) + ".", echo_files,
            {side: {key: view[key] for key in ("llm_calls", "tool_calls")} for side, view in observed.items()})
    else:
        add("B1", "observation", f"The echo turn could not be compared ({echo['classification']}).", echo_files)
    error = (minimal.get("candidate_error") or {}).get("message")
    add("B3", "observation", f"Documented minimal config without default_channel: baseline {minimal.get('baseline')}, "
                             f"candidate {minimal.get('candidate')} ({minimal['classification']})"
                             f"{'; candidate error: ' + error if error else ''}.",
        _files(_stage_file(base, "minimal_config"), _stage_file(cand, "minimal_config")))
    return facts


# --- the application-written factual report and next-check options --------------------


def _ids(facts: list[dict[str, Any]], prefix: str, *, skip: str = "") -> list[str]:
    return [f["id"] for f in facts if f["id"].startswith(prefix) and f["id"] != skip]


def factual_report(report: dict[str, Any], facts: list[dict[str, Any]]) -> dict[str, Any]:
    """Everything factual the analysis shows, generated from the validated comparison."""
    base_v = report["versions"]["baseline"]["requested_version"]
    cand_v = report["versions"]["candidate"]["requested_version"]
    by_id = {f["id"]: f for f in facts}
    exports = [{**f["data"], "fact": f["id"]} for f in facts if f["id"].startswith("X")]
    sigs = report["signatures"]
    signatures = None if sigs is None else {
        "identical": sigs["unchanged"], "changed": [c["entry_point"] for c in sigs["changed"]],
        "unresolved": {k: sigs[k] for k in ("unresolved_in_baseline", "unresolved_in_candidate",
                                            "unresolved_in_both") if sigs[k]},
        "facts": _ids(facts, "G"),
    }
    gaps = [{"symbol": g["symbol"], "target": g["target"], "unmeasured_in": g["unmeasured_in"]}
            for g in report["coverage_gaps"]]
    echo, minimal = report["behavior"]
    observed = echo.get("observed") or {}
    echo_core = {
        "baseline": echo.get("baseline"), "candidate": echo.get("candidate"), "classification": echo["classification"],
        "tool_calls": {side: view.get("tool_calls") for side, view in observed.items()},
        "llm_calls": {side: view.get("llm_calls") for side, view in observed.items()},
        "facts": [i for i in ("B1", "B2") if i in by_id],
    }
    minimal_core = {
        "baseline": minimal.get("baseline"), "candidate": minimal.get("candidate"),
        "classification": minimal["classification"],
        "candidate_error": (minimal.get("candidate_error") or {}).get("message"), "facts": ["B3"],
    }

    if not exports:
        export_text = "not compared"
    elif all(e["comparable"] and not e["added"] and not e["removed"] for e in exports):
        export_text = "no additions or removals (" + ", ".join(
            f"{e['root']} {e['baseline_count']} -> {e['candidate_count']}" for e in exports) + ")"
    else:
        export_text = "; ".join(
            f"{e['root']}: added {_names(e['added'])}, removed {_names(e['removed'])}" if e["comparable"]
            else f"{e['root']}: not comparable" for e in exports)
    if signatures is None:
        signature_text = "not compared"
    elif not signatures["changed"]:
        signature_text = f"all {len(signatures['identical'])} measured entry points identical"
    else:
        signature_text = f"{len(signatures['changed'])} changed ({_names(signatures['changed'])})"
    gap_text = "not measured" if signatures is None else (_names([g["symbol"] for g in gaps]) if gaps else "none")
    tool_text = "/".join(str(echo_core["tool_calls"].get(side)) for side in ("baseline", "candidate"))
    summary = (
        f"openminion {base_v} -> {cand_v}: {report['verdict']} (exit code {report['exit_code']}), within the probe "
        f"scope listed below only. Exports: {export_text}. Signatures: {signature_text}. Coverage gaps: {gap_text}. "
        f"Regressions: {len(report['regressions'])}. Echo turn: {echo_core['baseline']}/"
        f"{echo_core['candidate']}, tool_calls {tool_text} (echo makes no model call). Documented minimal config: "
        f"baseline {minimal_core['baseline']}, candidate {minimal_core['candidate']}."
    )

    rough_edges = [{"statement": by_id[i]["statement"], "facts": [i]} for i in _ids(facts, "R", skip="R0")]
    if minimal_core["baseline"] != "accepted" or minimal_core["candidate"] != "accepted":
        rough_edges.append({"statement": by_id["B3"]["statement"], "facts": ["B3"]})
    rough_edges += [{"statement": by_id[i]["statement"], "facts": [i]} for i in _ids(facts, "C", skip="C0")]
    rough_edges += [{"statement": by_id[i]["statement"], "facts": [i]} for i in _ids(facts, "N", skip="N0")]
    if echo["classification"] in ("regression", "failing_in_both", "not_comparable"):
        rough_edges.append({"statement": by_id["B1"]["statement"], "facts": ["B1"]})

    return {
        "authored_by": "application (generated from the validated comparison; not model-written)",
        "verdict": report["verdict"], "exit_code": report["exit_code"], "complete": report["complete"],
        "verdict_text": VERDICT_TEXT[report["verdict"]],
        "summary": summary,
        "core_results": {
            "regressions": [by_id[i]["statement"] for i in _ids(facts, "R", skip="R0")],
            "exports": exports, "signatures": signatures, "coverage_gaps": gaps,
            "echo": echo_core, "minimal_config": minimal_core,
        },
        "known_rough_edges": rough_edges,
        "scope_limitations": [{"id": f["id"], "statement": f["statement"]} for f in facts
                              if f["category"] == "scope_rule"],
    }


def next_check_options(report: dict[str, Any], facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The next checks this comparison's evidence supports; the model may only rank these."""
    options = []

    def offer(check_id: str, action: str, because: str, evidence: list[str]) -> None:
        options.append({"id": check_id, "action": action, "applies_because": because, "evidence": evidence})

    if report["regressions"]:
        offer("investigate_regressions", "Investigate each observed regression before upgrading.",
              f"{len(report['regressions'])} regression(s) observed", _ids(facts, "R", skip="R0"))
    if report["environment_failures"] or report["incomplete"]:
        offer("rerun_incomplete_stages", "Re-run the comparison so every probe completes on both versions.",
              "some environments or stages did not complete", _ids(facts, "N", skip="N0"))
    if report["coverage_gaps"]:
        offer("fill_coverage_gaps", "Measure the export roots or entry points that could not be measured.",
              f"{len(report['coverage_gaps'])} coverage gap(s) measured", _ids(facts, "C", skip="C0"))
    if report["signatures"] and report["signatures"]["changed"]:
        offer("review_signature_changes", "Review the changed entry-point signatures against your agent's calls.",
              f"{len(report['signatures']['changed'])} signature change(s) observed", _ids(facts, "G", skip="G1"))
    added = [f["id"] for f in facts if f["id"].startswith("X") and (f.get("data") or {}).get("added")]
    if added:
        offer("review_added_exports", "Review the newly added exports for features worth adopting.",
              "exports were added", added)
    if report["behavior"][1].get("candidate") == "rejected_invalid_channel":
        offer("set_default_channel", "Set default_channel on agents that rely on the documented minimal config.",
              "the candidate rejects the documented minimal config (invalid_channel)", ["B3"])
    offer("validate_with_real_provider",
          "Run your agent's own workflow with a real model provider on the candidate version.",
          "the echo probes prove neither real inference nor model-driven tool execution", ["S2", "B2"])
    offer("test_uncovered_building_blocks",
          "Test the building blocks your agent uses that these probes do not exercise (memory, skills, tasks, "
          "delegation, permissions).", "the probes cover only exports, signatures, an echo turn and the minimal "
                                       "config", ["S1", "S5"])
    return options


_PAYLOAD_GROUPS = {"scope_rule": "scope_rules", "observation": "observations"}
PAYLOAD_LISTS = ("scope_rules", "observations", "next_check_options")


def tool_payload(report_sha: str, verdict: str, facts: list[dict[str, Any]],
                 options: list[dict[str, Any]]) -> dict[str, Any]:
    """What the evidence tool returns to the model: structured data, grouped by fact category.

    It is returned as data, not as one JSON string: the SDK cuts every string in a tool
    result to TOOL_MESSAGE_STRING_LIMIT characters, and as one 4294-character string the
    payload lost every observation and option in openai-attempt-4 (F9). Every fact and
    option appears exactly once, with its canonical id and text.
    """
    verdicts = [f for f in facts if f["category"] == "verdict"]
    if len(verdicts) != 1:
        raise ValueError(f"expected exactly one verdict fact, got {len(verdicts)}")
    groups: dict[str, list[dict[str, str]]] = {group: [] for group in _PAYLOAD_GROUPS.values()}
    for fact in facts:
        if fact["category"] == "verdict":
            continue
        if fact["category"] not in _PAYLOAD_GROUPS:
            raise ValueError(f"fact {fact['id']} has an unknown category {fact['category']!r}")
        groups[_PAYLOAD_GROUPS[fact["category"]]].append({"id": fact["id"], "statement": fact["statement"]})
    checks = [{key: o[key] for key in ("id", "action", "applies_because")} for o in options]
    return {
        # The SDK shows a tool's own "summary" in the tool message; without one it derives a cut copy of the payload.
        "summary": (f"Evidence of one comparison: the verdict, {len(groups['scope_rules'])} scope rules, "
                    f"{len(groups['observations'])} observations and {len(checks)} next-check options, all included."),
        "report_sha256": report_sha,
        "verdict": {"id": verdicts[0]["id"], "value": verdict, "statement": verdicts[0]["statement"]},
        **groups,
        "next_check_options": checks,
    }


def returned_counts(value: Any) -> dict[str, Any]:
    """Audit counts of what the evidence tool actually returned."""
    if not isinstance(value, dict):
        return {"type": type(value).__name__, "chars": len(str(value))}
    return {"verdict": int(isinstance(value.get("verdict"), dict)),
            **{group: len(value.get(group) or []) for group in PAYLOAD_LISTS}}


def transport_problems(payload: Any) -> list[str]:
    """Every place where the pinned SDK would alter the payload on its way to the model.

    Mirrors the SDK's tool-message compaction (the root is depth 0). It reports; it never
    trims: analyze refuses to start when this list is not empty.
    """
    problems: list[str] = []

    def walk(value: Any, path: str, depth: int) -> None:
        if isinstance(value, str):
            if len(value) > TOOL_MESSAGE_STRING_LIMIT:
                problems.append(f"{path}: a string of {len(value)} characters exceeds {TOOL_MESSAGE_STRING_LIMIT}")
        elif isinstance(value, (dict, list, tuple)):
            if depth >= TOOL_MESSAGE_DEPTH_LIMIT:
                problems.append(f"{path}: a container nested {depth} deep reaches the depth limit "
                                f"{TOOL_MESSAGE_DEPTH_LIMIT}")
                return
            if len(value) > TOOL_MESSAGE_SEQUENCE_LIMIT:
                problems.append(f"{path}: {len(value)} items exceed {TOOL_MESSAGE_SEQUENCE_LIMIT}")
            if isinstance(value, dict):
                for key, item in value.items():
                    walk(item, f"{path}.{key}", depth + 1)
            else:
                for index, item in enumerate(value):
                    walk(item, f"{path}[{index}]", depth + 1)

    walk(payload, "payload", 0)
    summary = payload.get("summary") if isinstance(payload, dict) else None
    if isinstance(summary, str) and len(summary) > TOOL_SUMMARY_LIMIT:
        problems.append(f"payload.summary: {len(summary)} characters exceed the summary limit {TOOL_SUMMARY_LIMIT}")
    return problems


# --- validating and resolving the model's selection ------------------------------------

# A narrow guard, kept from schema 1, against rationales that contradict the verdict.
_COMPATIBILITY_CLAIM = re.compile(r"\b(is|are|fully|remains?|verdict:?)\s+compatible\b", re.IGNORECASE)
_NO_REGRESSION_CLAIM = re.compile(r"\bno regressions?\b", re.IGNORECASE)


def validate_selection(data: Any, facts: list[dict[str, Any]], options: list[dict[str, Any]],
                       verdict: str) -> tuple[dict[str, Any] | None, list[str]]:
    """Return (selection, []) for an acceptable reply, or (None, problems)."""
    try:
        selection = ModelSelection.model_validate(data)
    except ValidationError as exc:
        return None, [f"schema: {'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()]
    categories = {f["id"]: f["category"] for f in facts}
    applicable = {o["id"] for o in options}
    problems: list[str] = []

    def check_ids(field: str, ids: list[str], allowed: tuple[str, ...]) -> None:
        if len(set(ids)) != len(ids):
            problems.append(f"{field} repeats an id")
        for fact_id in ids:
            if fact_id not in categories:
                problems.append(f"{field}: unknown id {fact_id!r}")
            elif categories[fact_id] not in allowed:
                problems.append(f"{field}: {fact_id!r} is a {categories[fact_id]} fact, not {' or '.join(allowed)}")

    check_ids("key_observations", selection.key_observations, ("observation",))
    check_ids("relevant_limitations", selection.relevant_limitations, ("scope_rule",))
    chosen = [check.check_id for check in selection.next_checks]
    if len(set(chosen)) != len(chosen):
        problems.append("next_checks repeats a check_id")
    for n, check in enumerate(selection.next_checks):
        if check.check_id not in applicable:
            problems.append(f"next_checks[{n}]: {check.check_id!r} is not an applicable next-check option")
        check_ids(f"next_checks[{n}].evidence", check.evidence, ("observation", "scope_rule"))
    rationales = " ".join(check.rationale for check in selection.next_checks)
    if verdict != "compatible" and _COMPATIBILITY_CLAIM.search(rationales):
        problems.append("a rationale claims compatibility that the deterministic verdict does not support")
    if verdict == "regressions_detected" and _NO_REGRESSION_CLAIM.search(rationales):
        problems.append("a rationale denies regressions that the deterministic verdict reports")
    return (None if problems else selection.model_dump()), problems


def resolve_selection(selection: dict[str, Any], facts: list[dict[str, Any]],
                      options: list[dict[str, Any]]) -> dict[str, Any]:
    """Replace the model's ids with canonical, application-written statements."""
    by_id = {f["id"]: f for f in facts}
    by_option = {o["id"]: o for o in options}
    return {
        "authored_by": "model ranking and rationales; every statement and action is application-written",
        "key_observations": [{"id": i, "statement": by_id[i]["statement"]} for i in selection["key_observations"]],
        "relevant_limitations": [{"id": i, "statement": by_id[i]["statement"]}
                                 for i in selection["relevant_limitations"]],
        "next_checks": [{
            "check_id": c["check_id"], "action": by_option[c["check_id"]]["action"],
            "applies_because": by_option[c["check_id"]]["applies_because"],
            "model_rationale": c["rationale"], "evidence": c["evidence"],
        } for c in selection["next_checks"]],
    }


def judge(
    *, provider: str, process: dict[str, Any], worker_result: dict[str, Any] | None,
    tool_calls: list[dict[str, Any]], facts: list[dict[str, Any]], options: list[dict[str, Any]], verdict: str,
) -> dict[str, Any]:
    """Decide whether the model's contribution is accepted. Pure: no I/O."""
    reasons: list[str] = []
    problems: list[str] = []
    selection = None
    if provider == "echo":
        reasons.append("echo_provider_is_not_a_model")
    # The process contract comes first: a result file from a process that timed out,
    # failed to start or exited non-zero is never trusted.
    if process.get("status") == "timeout":
        reasons.append("deadline_exceeded")
    elif process.get("status") != "ok" or process.get("returncode") != 0:
        reasons.append("worker_process_failed")
    elif worker_result is None:
        reasons.append("worker_crashed")
    if worker_result is not None and process.get("status") != "timeout":
        if worker_result.get("status") != "completed":
            reasons.append(worker_result.get("status") or "error")
        elif worker_result.get("run_state") != "completed":
            reasons.append("run_not_completed")
    if not tool_calls:
        reasons.append("tool_not_executed")
    if worker_result and worker_result.get("status") == "completed":
        selection, problems = validate_selection(worker_result.get("output"), facts, options, verdict)
        if problems:
            reasons.append("selection_invalid")
        runtime_provider = (worker_result.get("runtime") or {}).get("metadata_provider")
        if runtime_provider and runtime_provider != provider:
            reasons.append("runtime_provider_mismatch")
    success = not reasons
    return {"status": "success" if success else "failed", "failure_reasons": reasons, "validation_problems": problems,
            "model_selection": resolve_selection(selection, facts, options) if success else None}


USAGE_KEYS = ("llm_calls", "input_tokens", "output_tokens", "cache_read_tokens", "tool_calls", "duration_ms")


def usage_from(runtime: dict[str, Any] | None) -> dict[str, Any]:
    """Runtime-reported usage, keeping 'not reported' distinct from a reported zero."""
    stats = (runtime or {}).get("stats")
    if not isinstance(stats, dict):
        return {"available": False, "note": "the runtime returned no stats: missing telemetry, not zero usage"}
    return {"available": True, **{key: stats.get(key, "not reported") for key in USAGE_KEYS}}


# --- secrets, files and rendering ----------------------------------------------------


def redact_secrets(text: str) -> str:
    """Remove credential values present in this environment, and the home directory."""
    for name, value in os.environ.items():
        if (name.endswith(("_API_KEY", "_TOKEN")) or "SECRET" in name) and len(value) >= 8:
            text = text.replace(value, "[redacted]")
    return redact(text)


def _write(path: Path, text: str) -> None:
    write_text_atomic(path, redact_secrets(text))


def _read_tool_log(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    return [json.loads(line) for line in lines if line.strip()]


def _prepare_output_dir(output_dir: Path, report_dir: Path) -> str | None:
    resolved, source = output_dir.resolve(), report_dir.resolve()
    if resolved == source or source in resolved.parents:
        return "--output-dir must not be inside the comparison directory; the source evidence is never modified"
    if output_dir.exists() and any(output_dir.iterdir()):
        if not (output_dir / OUTPUT_MARKER).exists():
            return f"{output_dir} is not empty and was not created by analyze; choose another --output-dir"
        # Drop every earlier result first, so a failed run never leaves a stale success behind.
        for name in ("analysis.json", "analysis.md"):
            (output_dir / name).unlink(missing_ok=True)
        shutil.rmtree(output_dir / "worker", ignore_errors=True)
    (output_dir / "worker").mkdir(parents=True, exist_ok=True)
    (output_dir / OUTPUT_MARKER).write_text("written by python -m upgrade_scout analyze\n", encoding="utf-8")
    return None


def _approval_text(approvals: list[dict[str, Any]] | None) -> str:
    if approvals is None:
        return "not run"
    allowed = sum(1 for a in approvals if a.get("decision") == "allow_once")
    return f"{allowed} / {len(approvals) - allowed}"


def _usage_text(usage: dict[str, Any] | None) -> str:
    if not usage:
        return "not run"
    if not usage["available"]:
        return usage["note"]
    return ", ".join(f"{key}={usage[key]}" for key in USAGE_KEYS)


def _render_factual_report(report: dict[str, Any]) -> list[str]:
    core = report["core_results"]
    out = ["## Factual report (application-generated from the validated comparison; not model-written)", "",
           report["summary"], "", "| core result | value | facts |", "| --- | --- | --- |"]
    for export in core["exports"]:
        value = (f"{export['baseline_count']} -> {export['candidate_count']} names; added "
                 f"{_names(export['added'])}; removed {_names(export['removed'])}"
                 if export["comparable"] else "not comparable")
        out.append(f"| exports of `{export['root']}` | {value} | {export['fact']} |")
    sigs = core["signatures"]
    if sigs is None:
        out.append("| entry-point signatures | not compared | |")
    else:
        out.append(f"| entry-point signatures | {len(sigs['identical'])} identical; changed: {_names(sigs['changed'])}"
                   f"{'; unresolved: ' + str(sigs['unresolved']) if sigs['unresolved'] else ''} | "
                   f"{', '.join(sigs['facts'])} |")
    gaps = core["coverage_gaps"]
    out.append(f"| coverage gaps | {_names([g['symbol'] + ' (' + g['unmeasured_in'] + ')' for g in gaps])} | "
               f"{'C0' if not gaps and sigs is not None else ''} |")
    out.append(f"| regressions | {len(core['regressions'])} | {'R0' if not core['regressions'] else ''} |")
    echo = core["echo"]
    out.append(f"| echo turn (no model call) | {echo['baseline']} / {echo['candidate']}; tool_calls "
               f"{echo['tool_calls'].get('baseline')} / {echo['tool_calls'].get('candidate')} | "
               f"{', '.join(echo['facts'])} |")
    minimal = core["minimal_config"]
    out.append(f"| documented minimal config | {minimal['baseline']} / {minimal['candidate']}"
               f"{' (' + minimal['candidate_error'] + ')' if minimal['candidate_error'] else ''} | B3 |")
    out += ["", "### Known rough edges (application-generated)", ""]
    out += [f"- {edge['statement']} [{', '.join(edge['facts'])}]" for edge in report["known_rough_edges"]] or ["- None."]
    out += ["", "### Scope limitations (application-generated)", ""]
    out += [f"- **{s['id']}** {s['statement']}" for s in report["scope_limitations"]]
    return out


def render_markdown(analysis: dict[str, Any]) -> str:
    source = analysis["input"]
    comparison = source.get("comparison") or {}
    title = f"{comparison.get('baseline')} -> {comparison.get('candidate')}" if comparison else "(no valid report)"
    out = [f"# Upgrade analysis: openminion {title}", ""]
    if analysis["status"] == "success":
        out.append("**Analysis status: success.** A real provider ran, the evidence tool executed, and the model's "
                   "selection passed validation.")
    else:
        out.append(f"**Analysis status: FAILED** ({', '.join(analysis['failure_reasons'])}). No model selection was "
                   "accepted; the factual report below does not depend on the model.")
    report = analysis.get("factual_report")
    out += ["", "## Authoritative verdict (application-generated)", ""]
    if report:
        out += [f"**{report['verdict']}** (exit code {report['exit_code']}, complete: {report['complete']}). "
                f"{report['verdict_text']} From `report.json` sha256 `{source['report_sha256']}`; the model cannot "
                "change it.", ""]
    out += [f"> {ECHO_LIMITATION}", ""]
    if report:
        out += _render_factual_report(report) + [""]

    selection = analysis.get("model_selection")
    if selection:
        out += ["## Model contribution (ranking and rationales only)", "",
                "The model chose and ordered the ids below; every statement and action is application-written. "
                "Only the text marked *Model rationale* is model-written, and it is a recommendation, not a fact.", "",
                "### Key observations, ranked by the model", ""]
        out += [f"{n}. {item['statement']} [{item['id']}]" for n, item in enumerate(selection["key_observations"], 1)]
        out += ["", "### Limitations the model considered most relevant", ""]
        out += [f"- {item['statement']} [{item['id']}]" for item in selection["relevant_limitations"]]
        out += ["", "### Next checks, ranked by the model", ""]
        for n, check in enumerate(selection["next_checks"], 1):
            cited = f" [{', '.join(check['evidence'])}]" if check["evidence"] else ""
            out += [f"{n}. **{check['action']}** (applies because {check['applies_because']})",
                    f"   - *Model rationale (model-written):* {check['model_rationale']}{cited}"]
        out.append("")
    else:
        out += ["## Model contribution: not accepted", ""]
        out += [f"- `{reason}`: {FAILURE_TEXT.get(reason, '')}" for reason in analysis["failure_reasons"]]
        out += [f"  - {problem}" for problem in analysis["validation_problems"]]
        out += [f"  - {problem}" for problem in analysis.get("transport_problems", [])]
        if analysis.get("error"):
            out.append(f"- detail: {analysis['error']}")
        out.append("")
    if analysis.get("raw_model_output"):
        out += [f"Raw model output, as returned and separately identified: `{analysis['raw_model_output']}`.", ""]

    out += ["## Model run", "", "| | |", "| --- | --- |"]
    configured, runtime, tool = analysis["configured"], analysis["runtime"] or {}, analysis["tool_execution"]
    rows = [
        ("SDK", f"openminion {analysis['sdk']['openminion_version']}"),
        ("configured provider", configured["provider"]),
        ("configured model", configured["model"]),
        ("runtime metadata: provider", runtime.get("metadata_provider")),
        ("runtime metadata: model (as reported; may not be a model id)", runtime.get("metadata_model")),
        ("run_id / session_id", f"{runtime.get('run_id')} / {runtime.get('session_id')}"),
        ("tool approvals (allow_once / deny), see `worker/approvals.jsonl`", _approval_text(analysis.get("approvals"))),
        (f"evidence tool `{TOOL_NAME}` executed (Python-side invocations)", tool["python_invocations"]),
        ("runtime-reported tool_calls", tool["runtime_reported_tool_calls"]),
        ("worker elapsed seconds (external process)", analysis.get("elapsed_seconds", "not run")),
        ("runtime-reported usage", _usage_text(analysis.get("usage"))),
    ]
    out += [f"| {label} | {value} |" for label, value in rows]
    out += ["", "## Checks", "", "Automatic:", ""] + [f"- {c}" for c in AUTOMATIC_CHECKS]
    out += ["", "Still needs human review:", ""] + [f"- {c}" for c in HUMAN_REVIEW]
    if analysis.get("facts"):
        out += ["", "## Facts supplied to the model (application-generated)", "",
                f"Evidence paths are relative to the directory of `{source['report']}`.", ""]
        out += [f"- **{f['id']}** ({f['category']}) {f['statement']} "
                f"(evidence: {', '.join(f'`{p}`' for p in f['evidence'])})" for f in analysis["facts"]]
    out.append("")
    return "\n".join(out)


# --- the command --------------------------------------------------------------------


def _worker_command(request_path: Path) -> list[str]:
    return [sys.executable, "-I", "-X", "utf8", "-m", "upgrade_scout.analysis_worker", str(request_path)]


def _worker_env() -> dict[str, str]:
    env = {name: value for name, value in os.environ.items() if not name.startswith("OPENMINION_")}
    env["OPENMINION_LOG_LEVEL"] = "WARNING"
    return env


def run_analyze(
    report_path: Path, provider: str, model: str | None, output_dir: Path, *,
    deadline_s: float = 600, state_root: Path | None = None, worker_command=_worker_command,
) -> int:
    if not _PROVIDER_PATTERN.match(provider):
        print(f"error: invalid --provider {provider!r}", file=sys.stderr)
        return EXIT_INVALID
    if provider != "echo" and not model:
        print("error: --model is required so the configured model identity is explicit", file=sys.stderr)
        return EXIT_INVALID
    if deadline_s <= 0:
        print("error: --deadline must be positive", file=sys.stderr)
        return EXIT_INVALID
    problem = _prepare_output_dir(output_dir, report_path.parent)
    if problem:
        print(f"error: {problem}", file=sys.stderr)
        return EXIT_INVALID

    output_dir = output_dir.resolve()
    worker_dir = output_dir / "worker"
    analysis: dict[str, Any] = {
        "schema": ANALYSIS_SCHEMA,
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "tool_version": __version__,
        "status": "failed", "failure_reasons": [], "validation_problems": [], "transport_problems": [],
        "input": {"report": redact(str(report_path)),
                  "note": "fact evidence paths are relative to the directory that holds this report"},
        "sdk": {"openminion_version": _sdk_version()},
        "configured": {"provider": provider, "model": model or "(provider default)",
                       "note": "configured identity; compare with the runtime metadata below"},
        "runtime": None,
        "tool_execution": {"tool": TOOL_NAME, "python_invocations": 0, "invocations": [],
                           "runtime_reported_tool_calls": None},
        "limitations": [ECHO_LIMITATION],
        "factual_report": None, "model_selection": None, "raw_model_output": None,
        "facts": [], "next_check_options": [],
    }

    def finish(code: int) -> int:
        _write(output_dir / "analysis.json", json.dumps(analysis, indent=2) + "\n")
        _write(output_dir / "analysis.md", render_markdown(analysis))
        print(f"analysis {analysis['status']}: {output_dir / 'analysis.md'}", file=sys.stderr)
        return code

    try:
        report, facts, evidence_files = validate_inputs(report_path)
    except (EvidenceError, OSError, KeyError, TypeError, ValueError) as exc:
        analysis["failure_reasons"] = ["invalid_report"]
        analysis["error"] = redact(f"{type(exc).__name__}: {exc}")
        return finish(EXIT_INVALID)
    report_sha = sha256_file(report_path)
    baseline = report["versions"]["baseline"]["requested_version"]
    candidate = report["versions"]["candidate"]["requested_version"]
    options = next_check_options(report, facts)
    analysis["input"].update(
        report_sha256=report_sha, evidence_files=evidence_files,
        comparison={"baseline": baseline, "candidate": candidate},
        deterministic_verdict=report["verdict"], exit_code=report["exit_code"], complete=report["complete"],
    )
    analysis.update(facts=facts, next_check_options=options, factual_report=factual_report(report, facts))
    analysis["limitations"] += report["scope"]
    payload = tool_payload(report_sha, report["verdict"], facts, options)
    problems = transport_problems(payload)
    if problems:
        analysis["failure_reasons"] = ["payload_exceeds_transport_limits"]
        analysis["transport_problems"] = problems
        for problem in problems:
            print(f"error: evidence payload: {problem}", file=sys.stderr)
        return finish(EXIT_INVALID)

    key_env = missing_credential(provider)
    if key_env:
        analysis["failure_reasons"] = ["missing_credentials"]
        analysis["error"] = f"{key_env} is not set (only its presence was checked)"
        return finish(EXIT_INVALID)
    analysis["configured"]["credential_env"] = PROVIDER_KEY_ENV.get(provider)  # present (checked); value never read

    work = (state_root or default_state_root()).resolve() / "work" / f"analysis-{uuid.uuid4().hex[:8]}"
    work.mkdir(parents=True)
    tool_log, result_path = worker_dir / "tool_calls.jsonl", worker_dir / "result.json"
    approval_log = worker_dir / "approvals.jsonl"
    request = {
        "provider": provider, "model": model, "home": str(work / "home"),
        "tool_log": str(tool_log), "result_path": str(result_path), "approval_log": str(approval_log),
        "session_id": SESSION_ID, "turn_timeout": max(1.0, deadline_s * 0.8),
        "instructions": instructions(),
        "message": run_message(baseline, candidate),
        "facts_payload": payload,
    }
    # The worker reads an unredacted copy in the temporary work dir; the evidence copy is redacted.
    request_path = work / "request.json"
    request_path.write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
    _write(worker_dir / "request.json", json.dumps(request, indent=2) + "\n")
    try:
        process = run_bounded(worker_command(request_path), log_path=worker_dir / "worker.log",
                              timeout_s=deadline_s, cwd=work, env=_worker_env())
    finally:
        shutil.rmtree(work, ignore_errors=True)
    _write(worker_dir / "worker.log", (worker_dir / "worker.log").read_text(encoding="utf-8", errors="replace"))
    process["log_tail"] = [redact_secrets(line) for line in process["log_tail"]]
    analysis["worker"] = process

    worker_result = None
    if result_path.is_file():
        worker_result = json.loads(result_path.read_text(encoding="utf-8"))
        _write(result_path, json.dumps(worker_result, indent=2) + "\n")
    tool_calls = _read_tool_log(tool_log)
    analysis["approvals"] = _read_tool_log(approval_log)
    runtime = (worker_result or {}).get("runtime")
    analysis["runtime"] = runtime
    if worker_result and worker_result.get("sdk_version"):
        analysis["sdk"]["openminion_version"] = worker_result["sdk_version"]
    analysis["tool_execution"].update(
        python_invocations=len(tool_calls), invocations=tool_calls,
        runtime_reported_tool_calls=((runtime or {}).get("stats") or {}).get("tool_calls", "not reported"),
    )
    analysis["elapsed_seconds"] = process["seconds"]
    analysis["usage"] = usage_from(runtime)
    if worker_result and worker_result.get("error"):
        analysis["error"] = worker_result["error"]

    decision = judge(provider=provider, process=process, worker_result=worker_result, tool_calls=tool_calls,
                     facts=facts, options=options, verdict=report["verdict"])
    analysis.update(decision)
    raw = (worker_result or {}).get("output", (worker_result or {}).get("raw_text"))
    if raw is not None:
        _write(worker_dir / "model_output.json", json.dumps({
            "note": "Raw model output, exactly as returned (model-written). The factual report does not use it.",
            "accepted": decision["status"] == "success", "output": raw}, indent=2) + "\n")
        analysis["raw_model_output"] = "worker/model_output.json"
    if sha256_file(report_path) != report_sha:
        analysis.update(status="failed", model_selection=None)
        analysis["failure_reasons"].append("source_report_changed")
    return finish(EXIT_SUCCESS if analysis["status"] == "success" else EXIT_FAILED)


def _sdk_version() -> str | None:
    try:
        import importlib.metadata

        return importlib.metadata.version("openminion")
    except Exception:  # noqa: BLE001
        return None
