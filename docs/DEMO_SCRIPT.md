# Demo Script (1–5 minutes; target about 4:15)

**Status: the video is NOT recorded yet.** Its URL in [SUBMISSION.md](SUBMISSION.md) stays PENDING until it is.

## Ground rules for the recording

- **Two kinds of material, always labelled on screen:**
  - **Retained and dated:** the comparison `evidence/phase3/compare/0.1.8-vs-0.1.15/` (generated 2026-10-29 14:25 UTC,
    `report.json` sha256 `8b82e734…0fc93`), and the accepted model run `evidence/phase5/analysis/openai-attempt-5/`
    (2026-10-29 18:44 UTC). **Attempt-5 analyzed exactly that retained report.** Never present it as an analysis of
    a comparison generated during the recording.
  - **Generated live (optional):** a new `compare` into `demo/compare` (gitignored). Call it "a new comparison, run
    now". It is a different report file from the one attempt-5 analyzed, even if its verdict is the same.
- **No live `analyze` in the default plan.** It is a real, billed agent turn, possibly several provider requests, and
  its output can differ. If you add one, show whatever it returns, accepted or not, label it with its own date and
  directory, and review its rationales on camera.
- **Disclose cuts.** If venv installs or other waiting time are cut, say so in the narration or on screen ("install
  time cut").
- **Before recording (not shown):** `.venv` installed per the README. If you will run `compare` live, run it once
  beforehand into a scratch directory, so its per-version venvs are cached (about 30 s afterwards).

## 1. The problem (0:00–0:25)

Say: "OpenMinion ships fast. Before I upgrade my agent's SDK, I want evidence that the APIs and basic turns my agent
relies on still work. And if a model summarizes that evidence, I want it unable to invent facts. MinionScout does
both: check your OpenMinion SDK upgrade with evidence."

## 2. The comparison and its limited verdict (0:25–1:20)

Optional, live (label it "new comparison, run now"):

```powershell
.venv\Scripts\python -m upgrade_scout compare --baseline 0.1.8 --candidate 0.1.15 --output-dir demo/compare
```

Show the four probe stages per version running as bounded processes; cut and disclose any install wait.

Then switch to the **retained** comparison that attempt-5 analyzed, and recheck it live (offline, seconds):

```powershell
.venv\Scripts\python -m upgrade_scout recheck evidence/phase3/compare/0.1.8-vs-0.1.15/report.json
```

Show:

1. `"matches_stored_comparison": true`: the verdict is recomputed from the raw per-version evidence;
2. the `source_sha256` `8b82e734…`, the same hash shown later in attempt-5's `analysis.md`;
3. in `evidence/phase3/compare/0.1.8-vs-0.1.15/report.md`:
   - **"Verdict: compatible"**, with "This covers only the probes listed under Scope";
   - the Scope lines;
   - the *Coverage gaps* section: "None: every export root and entry point was measured in both versions.";
   - echo `tool_calls` 0;
   - the minimal config `rejected_invalid_channel` on **both** versions (finding F1).

Say: "Compatible means compatible within these probes only. Echo makes no model call, so this proves nothing about
models or tool use."

## 3. The exact evidence attempt-5 used (1:20–1:50)

Open `evidence/phase5/analysis/openai-attempt-5/worker/request.json` and scroll to `facts_payload`. Show:

- the `report_sha256`, the same as the recheck;
- the grouped sections: `verdict`, 5 `scope_rules`, 11 `observations` and 3 `next_check_options`, each with an id and
  application-written text.

Say: "The application builds this from the validated comparison. The model gets it only by calling a tool."

## 4. Real tool execution (1:50–2:20)

- `worker/approvals.jsonl`: one `allow_once` for `comparison_evidence` with args `{}`. The approval callback allows
  nothing else.
- `worker/tool_calls.jsonl`: one line, written by the tool's own Python body, with `returned` = 1 verdict, 5 scope
  rules, 11 observations and 3 options.
- `analysis.md`, *Model run* table:
  - configured `openai` / `gpt-4.1-mini`, next to the runtime metadata (`brain-orchestrator`);
  - Python-side tool invocations 1 and runtime-reported `tool_calls` 1;
  - the elapsed time and the runtime-reported usage.

## 5. Model prioritization, and the human review (2:20–3:10)

In `evidence/phase5/analysis/openai-attempt-5/analysis.md`:

1. **Analysis status: success**, and the *application-generated* factual report. Say: "the model wrote none of this."
2. **Model contribution:**
   - key observations ranked R0, B1, G1, C0, X1 and X2, resolved to the application's own statements;
   - next checks ranked: validate with a real provider, test the uncovered building blocks, set `default_channel`;
     each with a *Model rationale (model-written)*.
3. **The human review.** Point at check 3's "potentially impacting upgrade smoothness". Say: "Every automatic check
   passed, but this clause implies an upgrade effect. The factual report shows 0.1.8 rejects that config too. So the
   rationales still need a human reader, and the tool labels them that way."

## 6. Finding F9 and its verified workaround (3:10–3:55)

1. `evidence/phase5/analysis/openai-attempt-4/analysis.md` (retained; **rejected**): `FAILED (selection_invalid)`.
   The model returned ids that do not exist (O1–O3, C1–C3), and validation kept them out.
2. `evidence/phase5/sdk-observations/f9-tool-result-truncation.txt`: the SDK cut the 4294-character tool result to 1200
   characters, so the model saw only V1 and S1–S4.
3. `evidence/phase5/transport-verification/summary.txt` (**MOCKED provider**, labelled so in the file): with the fix,
   the real SDK delivered 20 of 20 facts and options; attempt-4's old string delivered 5 of 20.
4. Then attempt-5, the first live run with the fix, was accepted.

Say: "We found this from failed runs, fixed it with a structured return and a preflight that refuses oversized
payloads, verified it offline, and only then ran another live analysis."

## 7. Close (3:55–4:15)

Point to `docs/WHAT_WE_LEARNED.md`:

- F9: tool results are cut silently;
- F1: the minimal config is rejected by `Agent.run`;
- F7: an approval prompt comes back as reply text;
- F8: the instructions budget;
- F5 and F6: `output_type` and lost run identity.

Then point to `docs/BUILDING_BLOCKS_TESTED.md`.

Say: "One accepted run of one model; the scope is stated in every report."
