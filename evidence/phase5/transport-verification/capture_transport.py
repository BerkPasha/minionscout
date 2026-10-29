"""OFFLINE TRANSPORT VERIFICATION with a MOCKED provider (finding F9). Not live evidence.

Runs one analysis turn twice through the real analysis worker, its decorated evidence
tool, its approval callback and the installed SDK, against the honest MOCKED local
OpenAI-compatible endpoint in tests/test_tool_transport.py. No network, no key, no paid call.

- fixed: the tool returns the structured, grouped payload built from the real Phase 3
  comparison (the same 17 facts and 3 options openai-attempt-4 sent);
- negative control: the tool returns openai-attempt-4's actual payload as one JSON string.

Writes, next to this script: summary.txt, and for each run the decoded tool message and the
full post-tool provider request body (home paths redacted).

usage: python evidence/phase5/transport-verification/capture_transport.py <scratch work dir>
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO), str(REPO / "tests")]

from test_tool_transport import (  # noqa: E402
    TRUNCATION_MARKERS, attempt4_payload, capture_turn, expected_items, fact_arrived, option_arrived,
    readable_strings, real_inputs, tool_contents,
)
from upgrade_scout.probe import redact  # noqa: E402

NOTE = ("MOCKED PROVIDER: captured offline at a local fake OpenAI-compatible endpoint. The real SDK, worker, "
        "decorated tool and approval callback ran; the model did not. Not live evidence.")


def write_json(name, value):
    text = redact(json.dumps(value, indent=2, ensure_ascii=False)) + "\n"
    if Path.home().name.lower() in text.lower():
        raise SystemExit(f"refusing to write {name}: it still contains the home directory name")
    (HERE / name).write_text(text, encoding="utf-8")


def run(label, work, payload, facts, options, monolithic):
    result, captured, log = capture_turn(work, payload, facts, options, monolithic=monolithic)
    post_tool = [body for body in captured if tool_contents(body)]
    content = tool_contents(post_tool[0])[0]
    strings = readable_strings(content)
    try:
        decoded = json.loads(content)
    except ValueError:
        decoded = content
    write_json(f"{label}-tool-message.json", {"note": NOTE, "tool_message_content_decoded": decoded})
    write_json(f"{label}-post-tool-request.json", {"note": NOTE, "provider_request_body": post_tool[0]})
    rows = []
    for item_id, expected in expected_items(facts, options).items():
        fact = next((f for f in facts if f["id"] == item_id), None)
        intact = fact_arrived(fact, strings) if fact else option_arrived(
            next(o for o in options if o["id"] == item_id), strings)
        rows.append(f"  {item_id:31} {expected[0]:18} {'intact' if intact else 'MISSING'}")
    received = sum(row.endswith("intact") for row in rows)
    markers = [m for m in TRUNCATION_MARKERS if m in content]
    return [
        f"## {label}",
        f"tool returned (audit log): {[entry['returned'] for entry in log]}",
        f"provider requests captured: {len(captured)}; post-tool requests: {len(post_tool)}",
        f"identical tool message in every post-tool request: "
        f"{all(tool_contents(body) == [content] for body in post_tool)}",
        f"tool message: {len(content)} characters; truncation markers: {markers or 'none'}",
        f"tool message outputs identical to the payload the tool returned: "
        f"{isinstance(decoded, dict) and decoded.get('outputs') == payload}",
        f"expected vs received (id, kind, arrived with full text): {received} of {len(rows)} intact",
        *rows,
        f"worker status: {result.get('status')}; model output: "
        f"{json.dumps(result.get('output') if result.get('status') == 'completed' else result.get('raw_text'))}",
        "",
    ]


def main():
    work = Path(sys.argv[1])
    _, facts, options, payload = real_inputs()
    lines = [
        "# Tool-result transport verification (F9), OFFLINE, MOCKED PROVIDER",
        NOTE,
        "Inputs: evidence/phase3/compare/0.1.8-vs-0.1.15/report.json (17 facts, 3 next-check options), checked "
        "equal to openai-attempt-4's request.",
        "",
    ]
    lines += run("fixed", work / "fixed", payload, facts, options, monolithic=False)
    lines += run("negative-control", work / "negative-control", attempt4_payload(), facts, options, monolithic=True)
    (HERE / "summary.txt").write_text(redact("\n".join(lines)), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
