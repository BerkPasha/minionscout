"""Instruction preservation after tool execution, captured through the real SDK.

MOCKED MODEL: a local fake OpenAI-compatible endpoint stands in for the provider. It asks
for comparison_evidence once, then answers with a hand-written selection. The real SDK, the
real analysis worker and its approval callback run the turn; nothing here is live evidence.

Why: Phase 5 openai-attempt-2 returned prose after the tool ran. Capturing the installed
SDK's provider requests showed Agent.instructions cut to the identity budget and missing
from the requests made after the tool result, while the user message reached every
request. analyze therefore repeats the instructions in the run message.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from upgrade_scout import analysis_worker
from upgrade_scout.analysis import instructions, run_message

MOCKED_SELECTION = {
    "key_observations": ["B3"],
    "relevant_limitations": ["S2"],
    "next_checks": [{"check_id": "validate_with_real_provider", "rationale": "MOCKED rationale", "evidence": []}],
}


def _fake_openai(captured):
    """A MOCKED OpenAI chat-completions endpoint that records every request body."""
    state = {"tool_requested": False}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            captured.append(body)
            names = [t.get("function", {}).get("name") or "" for t in body.get("tools") or []]
            offered = [n for n in names if "comparison_evidence" in n]
            if offered and not state["tool_requested"]:
                state["tool_requested"] = True
                message = {"role": "assistant", "content": None, "tool_calls": [{
                    "id": "call_1", "type": "function", "function": {"name": offered[0], "arguments": "{}"}}]}
                finish = "tool_calls"
            else:
                message, finish = {"role": "assistant", "content": json.dumps(MOCKED_SELECTION)}, "stop"
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


@pytest.mark.runtime
def test_full_instructions_reach_every_provider_request_after_the_tool_runs(tmp_path, monkeypatch):
    captured = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _fake_openai(captured))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}/v1"
    real_write_config = analysis_worker.write_config

    def write_config_for_fake_endpoint(home, provider="echo", model=None):
        path = real_write_config(home, provider=provider, model=model)
        config = json.loads(path.read_text(encoding="utf-8"))
        config["providers"]["openai"].update(base_url=base_url, api_key="MOCKED-not-a-key")
        path.write_text(json.dumps(config), encoding="utf-8")
        return path

    monkeypatch.setattr(analysis_worker, "write_config", write_config_for_fake_endpoint)
    monkeypatch.chdir(tmp_path)
    request = {
        "provider": "openai", "model": "gpt-4.1-mini", "home": str(tmp_path / "home"),
        "tool_log": str(tmp_path / "tool_calls.jsonl"), "approval_log": str(tmp_path / "approvals.jsonl"),
        "session_id": "capture", "turn_timeout": 120, "instructions": instructions(),
        "message": run_message("0.1.8", "0.1.15"),
        "facts_payload": {"summary": "MOCKED", "verdict": {"id": "V1", "value": "compatible", "statement": "MOCKED"},
                          "scope_rules": [], "observations": [], "next_check_options": []},
    }

    try:
        result = analysis_worker.execute(request)
    finally:
        server.shutdown()

    assert len((tmp_path / "tool_calls.jsonl").read_text(encoding="utf-8").splitlines()) == 1
    after_tool = [body for body in captured if any(m.get("role") == "tool" for m in body.get("messages", []))]
    assert after_tool, "the SDK made no provider request after the tool result"
    for body in after_tool:
        text = "\n".join(str(m.get("content")) for m in body["messages"])
        assert instructions() in text
    assert result["status"] == "completed", result.get("error")
    assert result["output"]["key_observations"] == ["B3"]
