"""The evidence reaches the model intact: the tool-result transport fix for finding F9.

In openai-attempt-4 the evidence tool returned its payload as one 4294-character JSON
string. The installed SDK cuts every string in a tool result to 1200 characters, so the
model saw only V1 and S1-S4. The tool now returns structured data that fits the SDK's
limits, and analyze refuses to start when a payload would not fit.

MOCKED PROVIDER in the runtime tests: a local fake OpenAI-compatible endpoint stands in
for the model. It is honest: it answers with a selection only when every fact and every
next-check option arrived, with its id and full text, in the tool message it received,
and it builds that selection from what arrived. Otherwise it answers in prose, which the
SDK rejects. The real SDK, the real analysis worker, its decorated tool and its approval
callback run the turn. The facts and options are the real Phase 3 comparison's, checked
against the payload openai-attempt-4 actually sent; there is no one-fact fixture.
Nothing here is live evidence.
"""

import copy
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from upgrade_scout import analysis, analysis_worker
from upgrade_scout.analysis import (
    TOOL_NAME, instructions, next_check_options, run_analyze, run_message, tool_payload, transport_problems,
    validate_inputs, validate_selection,
)
from upgrade_scout.compare import sha256_file

REPO = Path(__file__).resolve().parents[1]
PHASE3_REPORT = REPO / "evidence/phase3/compare/0.1.8-vs-0.1.15/report.json"
ATTEMPT4_REQUEST = REPO / "evidence/phase5/analysis/openai-attempt-4/worker/request.json"
TRUNCATION_MARKERS = ("[truncated]", "__truncated__", "more item(s)")
REAL_COUNTS = {"verdict": 1, "scope_rules": 5, "observations": 11, "next_check_options": 3}


def real_inputs():
    """The real Phase 3 comparison: its verdict, facts, options, and the structured payload built from them."""
    report, facts, _ = validate_inputs(PHASE3_REPORT)
    options = next_check_options(report, facts)
    return report, facts, options, tool_payload(sha256_file(PHASE3_REPORT), report["verdict"], facts, options)


def attempt4_payload():
    """The payload openai-attempt-4's tool returned (as one JSON string), from its retained request."""
    return json.loads(ATTEMPT4_REQUEST.read_text(encoding="utf-8"))["facts_payload"]


def expected_items(facts, options):
    """Every fact and option the model must receive, keyed by id, with its canonical text."""
    items = {f["id"]: (f["category"], f["statement"]) for f in facts}
    items.update({o["id"]: ("next_check_option", o["action"], o["applies_because"]) for o in options})
    return items


def received_items(outputs):
    """The same view of a structured tool result; a repeated id fails here."""
    pairs = [(outputs["verdict"]["id"], ("verdict", outputs["verdict"]["statement"]))]
    pairs += [(f["id"], ("scope_rule", f["statement"])) for f in outputs["scope_rules"]]
    pairs += [(f["id"], ("observation", f["statement"])) for f in outputs["observations"]]
    pairs += [(o["id"], ("next_check_option", o["action"], o["applies_because"]))
              for o in outputs["next_check_options"]]
    assert len({key for key, _ in pairs}) == len(pairs), "an id was returned twice"
    return dict(pairs)


def tool_contents(body):
    """The content of every tool-role message in one provider request body."""
    contents = []
    for message in body.get("messages", []):
        if message.get("role") == "tool":
            content = message.get("content")
            if isinstance(content, list):
                content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
            contents.append(content or "")
    return contents


def readable_strings(content):
    """Every string a model could read in a tool message, decoded from its JSON where possible."""
    strings = []

    def collect(value):
        if isinstance(value, str):
            strings.append(value)
        elif isinstance(value, dict):
            for item in value.values():
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    try:
        collect(json.loads(content))
    except ValueError:
        strings.append(content)
    return strings


def _id_arrived(item_id, strings):
    # Structured: the id is its own value. Old monolithic string: it sits inside the JSON text.
    return item_id in strings or any(f'"id": "{item_id}"' in s for s in strings)


def fact_arrived(fact, strings):
    return _id_arrived(fact["id"], strings) and any(fact["statement"] in s for s in strings)


def option_arrived(option, strings):
    return _id_arrived(option["id"], strings) and all(
        any(option[key] in s for s in strings) for key in ("action", "applies_because"))


def honest_reply(contents, facts, options):
    """The MOCKED model's answer: a selection only if all evidence arrived, built from what arrived."""
    strings = [s for content in contents for s in readable_strings(content)]
    missing = [f["id"] for f in facts if not fact_arrived(f, strings)]
    missing += [o["id"] for o in options if not option_arrived(o, strings)]
    if missing:
        return f"MOCKED: evidence incomplete; missing {', '.join(missing)}"
    observations = [f["id"] for f in facts if f["category"] == "observation"]
    scope_rules = [f["id"] for f in facts if f["category"] == "scope_rule"]
    return json.dumps({
        "key_observations": observations[-3:], "relevant_limitations": scope_rules[:2],
        "next_checks": [{"check_id": o["id"], "rationale": "MOCKED rationale", "evidence": []} for o in options],
    })


def honest_provider(captured, facts, options):
    """A MOCKED OpenAI chat-completions endpoint that records every request body."""
    state = {"tool_requested": False}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            captured.append(body)
            names = [t.get("function", {}).get("name") or "" for t in body.get("tools") or []]
            offered = [n for n in names if TOOL_NAME in n]
            contents = tool_contents(body)
            if contents:
                message, finish = {"role": "assistant", "content": honest_reply(contents, facts, options)}, "stop"
            elif offered and not state["tool_requested"]:
                state["tool_requested"] = True
                message = {"role": "assistant", "content": None, "tool_calls": [{
                    "id": "call_1", "type": "function", "function": {"name": offered[0], "arguments": "{}"}}]}
                finish = "tool_calls"
            else:
                # The SDK's own classifier requests carry no evidence, so they never get a selection.
                message, finish = {"role": "assistant", "content": "MOCKED: no evidence in this request"}, "stop"
            out = json.dumps({"id": "mocked", "object": "chat.completion", "created": 0, "model": body.get("model"),
                              "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                              "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *args):
            pass

    return Handler


def capture_turn(work, payload, facts, options, *, monolithic=False):
    """One analysis turn through the real SDK and worker, against the honest MOCKED provider.

    monolithic=True is the negative control: the tool returns json.dumps(payload) as one
    string, exactly as openai-attempt-4's did. Returns (worker result, provider request
    bodies, tool log entries).
    """
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    captured = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), honest_provider(captured, facts, options))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}/v1"
    real_write_config, real_result = analysis_worker.write_config, analysis_worker.evidence_result

    def write_config_for_mock(home, provider="echo", model=None):
        path = real_write_config(home, provider=provider, model=model)
        config = json.loads(path.read_text(encoding="utf-8"))
        config["providers"]["openai"].update(base_url=base_url, api_key="MOCKED-not-a-key")
        path.write_text(json.dumps(config), encoding="utf-8")
        return path

    analysis_worker.write_config = write_config_for_mock
    if monolithic:
        analysis_worker.evidence_result = lambda value: json.dumps(value, sort_keys=True)
    cwd = os.getcwd()
    os.chdir(work)  # APIRuntime creates .openminion/ under the cwd (F2)
    try:
        result = analysis_worker.execute({
            "provider": "openai", "model": "gpt-4.1-mini", "home": str(work / "home"),
            "tool_log": str(work / "tool_calls.jsonl"), "approval_log": str(work / "approvals.jsonl"),
            "session_id": "transport-capture", "turn_timeout": 120, "instructions": instructions(),
            "message": run_message("0.1.8", "0.1.15"), "facts_payload": payload,
        })
    finally:
        os.chdir(cwd)
        analysis_worker.write_config, analysis_worker.evidence_result = real_write_config, real_result
        server.shutdown()
    log_path = work / "tool_calls.jsonl"
    log = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()] if log_path.exists() else []
    return result, captured, log


# --- offline checks against the installed SDK's own code ----------------------------------


def test_the_payload_carries_exactly_what_attempt4_sent_grouped_and_within_the_limits():
    _, facts, options, payload = real_inputs()
    old = attempt4_payload()

    assert len(json.dumps(old, sort_keys=True)) == 4294
    assert [(f["id"], f["category"], f["statement"]) for f in facts] == [
        (f["id"], f["category"], f["statement"]) for f in old["facts"]]
    assert [{key: o[key] for key in ("id", "action", "applies_because")} for o in options] == old["next_check_options"]
    assert received_items(payload) == expected_items(facts, options)  # nothing dropped, nothing repeated
    assert (payload["report_sha256"], payload["verdict"]["value"]) == (old["report_sha256"], old["verdict"])
    assert analysis.returned_counts(payload) == REAL_COUNTS
    assert transport_problems(payload) == []


def test_the_pinned_limits_are_the_installed_sdks():
    import inspect

    from openminion.modules.brain import constants
    from openminion.modules.brain.adapters.tool import results

    assert (constants.TOOL_MESSAGE_STRING_LIMIT, constants.TOOL_MESSAGE_SEQUENCE_LIMIT,
            constants.TOOL_MESSAGE_DEPTH_LIMIT) == (analysis.TOOL_MESSAGE_STRING_LIMIT,
                                                    analysis.TOOL_MESSAGE_SEQUENCE_LIMIT,
                                                    analysis.TOOL_MESSAGE_DEPTH_LIMIT)
    assert inspect.signature(results._normalized_summary_token).parameters["limit"].default == \
        analysis.TOOL_SUMMARY_LIMIT


def test_the_installed_compactor_keeps_the_structured_payload_and_cuts_the_old_string():
    from openminion.modules.brain.loop.tools.messages import _compact_tool_message_value

    payload = real_inputs()[3]
    assert _compact_tool_message_value(payload) == payload

    cut = _compact_tool_message_value({"data": json.dumps(attempt4_payload(), sort_keys=True)})["data"]
    assert cut.endswith("...[truncated]") and len(cut) == 1200 + len("...[truncated]")
    assert '"id": "S4"' in cut and '"id": "S5"' not in cut and '"id": "X1"' not in cut
    assert "next_check_options" not in cut


def _too_long(payload):
    payload["observations"][3]["statement"] = "x" * 1201


def _too_many(payload):
    payload["observations"] += [{"id": f"Z{i}", "statement": "SYNTHETIC"} for i in range(6)]


def _too_deep(payload):
    nested = payload
    for _ in range(8):
        nested["n"] = {}
        nested = nested["n"]


@pytest.mark.parametrize("mutate, expected", [
    (_too_long, "payload.observations[3].statement: a string of 1201 characters exceeds 1200"),
    (_too_many, "payload.observations: 17 items exceed 16"),
    (_too_deep, "payload.n.n.n.n.n.n.n.n: a container nested 8 deep reaches the depth limit 8"),
])
def test_the_preflight_names_each_place_the_installed_sdk_would_alter(mutate, expected):
    from openminion.modules.brain.loop.tools.messages import _compact_tool_message_value

    payload = copy.deepcopy(real_inputs()[3])  # SYNTHETIC mutations of the real payload
    mutate(payload)

    assert transport_problems(payload) == [expected]
    assert _compact_tool_message_value(payload) != payload  # the SDK really would change it


def test_the_preflight_checks_the_tool_summary_limit():
    payload = copy.deepcopy(real_inputs()[3])
    payload["summary"] = "s" * 601  # SYNTHETIC

    assert transport_problems(payload) == ["payload.summary: 601 characters exceed the summary limit 600"]


def test_analyze_refuses_to_start_a_worker_when_the_payload_exceeds_the_limits(tmp_path, monkeypatch):
    monkeypatch.setattr(analysis, "TOOL_MESSAGE_SEQUENCE_LIMIT", 10)  # the real 11 observations no longer fit
    monkeypatch.setenv("OPENAI_API_KEY", "MOCKED-not-a-key")
    started = tmp_path / "worker-started"

    def worker(request_path):
        return [sys.executable, "-c", f"open({str(started)!r}, 'w').close()"]

    code = run_analyze(PHASE3_REPORT, "openai", "gpt-4.1-mini", tmp_path / "out", deadline_s=30,
                       state_root=tmp_path / "state", worker_command=worker)
    result = json.loads((tmp_path / "out" / "analysis.json").read_text(encoding="utf-8"))

    assert code == analysis.EXIT_INVALID and not started.exists() and not (tmp_path / "state").exists()
    assert result["failure_reasons"] == ["payload_exceeds_transport_limits"]
    assert result["transport_problems"] == ["payload.observations: 11 items exceed 10"]
    assert result["factual_report"]["verdict"] == "compatible" and result["model_selection"] is None
    assert "payload.observations: 11 items exceed 10" in (tmp_path / "out" / "analysis.md").read_text(encoding="utf-8")


def test_the_honest_mock_never_selects_without_the_complete_evidence():
    report, facts, options, payload = real_inputs()

    def message(outputs):
        return json.dumps({"status": "success", "summary": "MOCKED", "outputs": outputs})

    selection, problems = validate_selection(json.loads(honest_reply([message(payload)], facts, options)),
                                             facts, options, report["verdict"])
    assert problems == [] and selection is not None
    for group in ("observations", "next_check_options"):
        partial = copy.deepcopy(payload)
        partial[group] = partial[group][:-1]
        assert honest_reply([message(partial)], facts, options).startswith("MOCKED: evidence incomplete")
    cut = copy.deepcopy(payload)
    cut["observations"][0]["statement"] = cut["observations"][0]["statement"][:40]
    assert honest_reply([message(cut)], facts, options).startswith("MOCKED: evidence incomplete")


def test_the_instructions_name_the_groups_the_tool_returns():
    payload = real_inputs()[3]
    for group in ("verdict", "scope_rules", "observations", "next_check_options"):
        assert group in payload and group in instructions()


# --- the full path: decorated tool -> real SDK -> MOCKED provider --------------------------


@pytest.mark.runtime
def test_every_fact_and_option_reaches_the_post_tool_provider_request_intact(tmp_path):
    report, facts, options, payload = real_inputs()
    result, captured, log = capture_turn(tmp_path, payload, facts, options)

    assert [entry["returned"] for entry in log] == [REAL_COUNTS]
    post_tool = [contents for contents in map(tool_contents, captured) if contents]
    assert post_tool, "the SDK made no provider request after the tool result"
    for contents in post_tool:
        assert len(contents) == 1
        assert not any(marker in contents[0] for marker in TRUNCATION_MARKERS)
        message = json.loads(contents[0])
        assert message["status"] == "success" and message["summary"] == payload["summary"]
        assert message["outputs"] == payload
        assert received_items(message["outputs"]) == expected_items(facts, options)
    assert result["status"] == "completed", result.get("error")
    assert result["output"] == json.loads(honest_reply(post_tool[0], facts, options))  # built from what arrived
    selection, problems = validate_selection(result["output"], facts, options, report["verdict"])
    assert problems == [] and selection is not None


@pytest.mark.runtime
def test_negative_control_the_old_monolithic_string_loses_the_observations_and_options(tmp_path):
    _, facts, options, _ = real_inputs()
    result, captured, log = capture_turn(tmp_path, attempt4_payload(), facts, options, monolithic=True)

    assert [entry["returned"] for entry in log] == [{"type": "str", "chars": 4294}]
    contents = [content for body in captured for content in tool_contents(body)]
    assert contents and all("...[truncated]" in content for content in contents)
    strings = [s for content in contents for s in readable_strings(content)]
    # S4's statement ends exactly at character 1200; only its closing quote is cut.
    assert {f["id"] for f in facts if fact_arrived(f, strings)} == {"V1", "S1", "S2", "S3", "S4"}
    assert not any(option_arrived(o, strings) for o in options)
    assert result["status"] == "output_invalid"  # the honest mock answered in prose
