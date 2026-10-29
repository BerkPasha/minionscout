"""OFFLINE DIAGNOSTIC (MOCKED endpoint): what does the SDK send to the provider after the tool runs?

HISTORICAL: this reproduced F9 with the pre-fix worker, whose tool returned one JSON string.
The worker now returns structured data, so this script no longer shows the cut. The
reproduction with current code, including a negative control with attempt-4's exact string,
is evidence/phase5/transport-verification/capture_transport.py.

Replays attempt-4's real request (instructions, message, facts_payload) through the real
analysis worker and installed SDK, against the MOCKED local OpenAI-compatible endpoint from
tests/test_instruction_capture.py. No network, no key, no paid call. Writes every captured
request body to OUT_DIR/requests.json and prints what the tool-result message contained.
"""

import json
import os
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

REPO = Path(sys.argv[1])
OUT_DIR = Path(sys.argv[2])
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tests"))

from upgrade_scout import analysis_worker  # noqa: E402
from test_instruction_capture import _fake_openai  # noqa: E402

OUT_DIR.mkdir(parents=True, exist_ok=True)
attempt4 = json.loads((REPO / "evidence/phase5/analysis/openai-attempt-4/worker/request.json").read_text(encoding="utf-8"))

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


analysis_worker.write_config = write_config_for_fake_endpoint
os.chdir(OUT_DIR)
request = {
    "provider": "openai", "model": "gpt-4.1-mini", "home": str(OUT_DIR / "home"),
    "tool_log": str(OUT_DIR / "tool_calls.jsonl"), "approval_log": str(OUT_DIR / "approvals.jsonl"),
    "session_id": "capture", "turn_timeout": 120,
    "instructions": attempt4["instructions"], "message": attempt4["message"],
    "facts_payload": attempt4["facts_payload"],
}
try:
    result = analysis_worker.execute(request)
finally:
    server.shutdown()

(OUT_DIR / "requests.json").write_text(json.dumps(captured, indent=2), encoding="utf-8")
(OUT_DIR / "result.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
sent = json.dumps(attempt4["facts_payload"], sort_keys=True)
print("worker status:", result.get("status"), "| stats:", (result.get("runtime") or {}).get("stats"))
print("provider requests captured:", len(captured))
print("tool payload returned by the Python body:", len(sent), "chars")
for i, body in enumerate(captured):
    print(f"--- request {i}: tool_choice={json.dumps(body.get('tool_choice'))} "
          f"tools={[t.get('function', {}).get('name') for t in body.get('tools') or []]}")
    for m in body.get("messages", []):
        content = m.get("content")
        text = content if isinstance(content, str) else json.dumps(content)
        print(f"  role={m.get('role'):9} chars={len(text or ''):6} tool_calls={bool(m.get('tool_calls'))}")
        if m.get("role") == "tool":
            print("    identical to payload:", text == sent, "| payload is a prefix-substring:", sent[:200] in (text or ""))
            for needle in ['"S5"', '"P1"', '"X1"', '"G1"', '"C0"', '"B3"', "next_check_options", "validate_with_real_provider"]:
                print(f"    contains {needle}: {needle in (text or '')}")
            print("    tail:", repr((text or "")[-300:]))
