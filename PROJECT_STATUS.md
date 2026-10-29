# Project Status: MinionScout

*Named "Minion Upgrade Scout" until Phase 6; historical sections keep that name. The code keeps its
original package, module and CLI names.*

- **Last updated:** 2026-10-29
- **Phase:** 6, submission preparation. **Feature development is frozen.**
  - **Clean install reproduced** at a short path, with the documented commands (`evidence/phase6/CLEAN_INSTALL.md`):
    - `surface` matches the retained 0.1.15 surface;
    - `recheck` of the retained comparison gives `matches_stored_comparison: true`;
    - the offline suite: 157 passed, 2 skipped.

    No release blocker was found, and no code was changed.
  - Submission material: `docs/SUBMISSION.md`, a judge-oriented README, `docs/REFERENCE.md` (the detailed reference,
    moved out of the README), and a final `docs/DEMO_SCRIPT.md`.
  - **Publication:** the public GitHub repository <https://github.com/BerkPasha/minionscout> was created on
    2026-10-29, and the visible project name is now **MinionScout**.
    - A `.gitattributes` (`* -text`) stores every file byte-for-byte, so the published evidence keeps its sha256.
      Git's system config here has `core.autocrlf=true`, and 46 files contain CRLF.
    - Verification of the initial push: see *Publication* below.
- **Phase 5 result:**
  - **Live validation: SUCCESS in `openai-attempt-5`**, the first real run after the F9 transport fix.
    - Real OpenAI `gpt-4.1-mini`; `analysis/2`, `status: success`, `transport_problems: []`.
    - The evidence tool executed once, after one scoped `allow_once`.
    - The model's selection passed every automatic check.
    - The human factual review accepts it, with **one rejected clause** in one rationale (see *openai-attempt-5*
      below).
  - Attempts 1–4 were rejected and are preserved: attempts 1–3 under contract v1, attempt-4 under contract v2 before
    the transport fix.
  - **Analysis contract v2.** The application writes every factual statement; the model only ranks ids and gives
    labelled rationales.
  - **F9:** the SDK truncates each tool-result string to 1200 characters, so in attempts 2–4 the model saw only V1
    and S1–S4. The tool now returns grouped, structured data within the SDK's limits. This was verified offline with a
    MOCKED provider, and is consistent with attempt-5, where the model used ids the cut had hidden.
  - **The targeted live pytest has not been run yet.** Its command is under *openai-attempt-5*.
- **Submission-ready: NO.** Still unmet:
  1. the **1–5 minute demo video** (not recorded);
  2. the submission pull request (the Hackathon #5 repository URL is not published yet).

  **Unresolved owner decision, not a stated qualification blocker:** licensing. No license is selected. The rules
  require "properly licensed code and data", but do not mandate a separate `LICENSE` file or a particular license.

  Recommended before submission: the targeted live pytest.

## Phase 6: release state (from the actual files and Git, 2026-10-29)

| Item | State | Decision needed from |
| --- | --- | --- |
| License | **none selected.** There is no `LICENSE` file, and `pyproject.toml` has no `license` field. Both hackathon pages (re-checked 2026-10-29) say only "Use properly licensed code and data, disclose external dependencies, keep secrets and private data out of public submissions". There is no explicit `LICENSE`-file or specific-license requirement. | the owner: an unresolved decision, not an established blocker |
| Git repository | branch `master`; remote `origin` = `https://github.com/BerkPasha/minionscout.git`; initial commit and push: see *Publication* below | — |
| Published files | 223: the 222 project files reviewed in Phase 6, plus `.gitattributes`. A scan found no home-directory paths, user names, e-mail addresses, hostnames or keys in their contents; the only key-like string is the labelled `sk-MOCKED-not-a-real-key-…` test value. `.venv/`, `.openminion/`, `.scout-home/`, `*.egg-info/`, `__pycache__/`, `demo/` and `scout-reports/` are gitignored. | — |
| Git identity | the existing global `user.name` and `user.email` were used for the commit, as the owner authorized; they are public in the commit metadata | — |
| Public repository URL | <https://github.com/BerkPasha/minionscout> (public) | — |
| Demo video URL | **none** (not recorded) | the owner |
| Submission (pull request) | re-checked 2026-10-29. Both pages: "Link your public project and submission materials in a pull request to the dedicated Hackathon #5 repository", whose URL "will be added before kickoff"; it is still not listed. The cutoff is on DoraHacks (`https://dorahacks.io/hackathon/2418/detail`). | the owner |
| Targeted live pytest | **not run** (another real, billed agent turn, possibly several provider requests); the command is under *openai-attempt-5* | the operator |

## Publication

- **Repository:** <https://github.com/BerkPasha/minionscout>, public, created 2026-10-29 under the owner's personal
  account.
- **Initial commit:** pushed to `master`. **When this commit was made, the push had not yet been verified against
  GitHub.** The verification is recorded in the following commit.
- **Not done:** the hackathon submission pull request and the demo video.

## `openai-attempt-5`: SUCCESS (first accepted model-backed analysis), preserved unchanged

The operator ran the attempt-5 command below in their terminal; `evidence/phase5/analysis/openai-attempt-5/`. Each
item was re-verified independently of `analysis.json`, from the raw worker files and a recomputation from the source
report.

**Structural validation (automatic, and re-checked):**

| Check | Result |
| --- | --- |
| 1. schema, status | `minion-upgrade-scout/analysis/2`; `status: success`; `failure_reasons: []`; `validation_problems: []`; `transport_problems: []` |
| 2. process and turn | `worker.status: ok`, `returncode: 0`, 19.1 s; `run_state: completed`; the reply text's JSON equals the parsed `output` |
| 3. approval | one `allow_once` for `comparison_evidence`, args `{}` (approval id `call_xm2iuC8wfsqsRBeBeqMgUkEh`); no other tool, no deny |
| 4. tool execution | **1** Python-side invocation; `returned: {"verdict": 1, "scope_rules": 5, "observations": 11, "next_check_options": 3}`; runtime `tool_calls=1` |
| 5. payload | `worker/request.json` `facts_payload` has the grouped keys and **equals** the payload rebuilt from the source report; the preflight re-run gives no problems |
| 6. selection | re-validating `worker/model_output.json` gives no problems. Observations R0, B1, G1, C0, X1, X2 (all `observation`); limitations S1–S5 (all `scope_rule`); checks `validate_with_real_provider`, `test_uncovered_building_blocks`, `set_default_channel` (all 3 applicable options); evidence ids S2, B1, B2, S5, B3, S1 (all observation or scope rule). `model_selection` equals the resolution of the raw output. |
| 7. factual report | `compatible`, equal to the deterministic verdict. No export changes (12 -> 12, 15 -> 15), 6 of 6 signatures identical, no gaps, 0 regressions, echo `tool_calls` 0/0, minimal config `rejected_invalid_channel` on both versions. `factual_report`, `facts` and `next_check_options` equal a recomputation; `recheck` matches. |
| 8. preservation | source `report.json` sha256 `8b82e734…0fc93` unchanged; attempts 1–4 byte-identical (7, 9, 9, 9 files); attempt-5's 9 files hashed after inspection |
| 9. metadata | configured `openai` / `gpt-4.1-mini`; runtime `provider=openai`, `model=brain-orchestrator`; `run_id 23ab8f8132a6407282c6da543f164d86`, `request_id cc41aca9d12f477cb411772697da191f`. Runtime-reported usage: `llm_calls=1` (not a request count), 10107 input and 560 output tokens, `duration_ms=13272`. |

**Did the full evidence reach the model?** The live request was not captured, so this is indirect.

- The model used 9 ids that attempt-4's cut had hidden: S5, R0, X1, X2, G1, C0, B1, B2 and B3.
- It used all 3 real option ids.
- Input tokens rose from 8578 (attempt-4) to 10107.

**Human factual review** (structural acceptance does not establish factual correctness):

- **Ranking of observations** (R0, B1, G1, C0, X1, X2): sensible for a compatibility question; none of these
  observations is misstated.
  - **Note:** B1 (the echo contract) is ranked second, although S2 says echo proves no inference.
  - **Note:** B3, the only known rough edge, is not among the key observations; it appears through the third next
    check, and the factual report lists it regardless.
- **Limitations:** all five scope rules, in id order, so they are not really prioritized. Valid, but uninformative.

| Next check (model rank) | Rationale (model-written) | Cited | Review |
| --- | --- | --- | --- |
| 1. `validate_with_real_provider` | "This check is important because the echo probes do not demonstrate real model inference or model-driven tool execution, which are critical for validating upgrade behavior in production-like scenarios." | S2, B1, B2 | **Supported.** S2 states it, and B2 shows 0 tool calls and 0 tokens on echo. B1 is a weak citation: it shows the echo contract was met, and does not support this claim. "Production-like" says such validation is still missing; it does not claim safety. |
| 2. `test_uncovered_building_blocks` | "Testing building blocks like memory, skills, tasks, delegation, and permissions is necessary because these aspects are not exercised by the existing probes, leaving gaps in coverage for the upgrade evaluation." | S5 | **Supported** by S5. Caveat: "gaps in coverage" means areas not exercised. It is not this tool's measured coverage gaps, which are none (C0). |
| 3. `set_default_channel` | "Setting default_channel on agents relying on the minimal config matters since the candidate version rejects the documented minimal config due to invalid_channel errors, potentially impacting upgrade smoothness." | B3, S1 | **Recommendation and premise supported:** B3 shows the candidate rejects it with `invalid_channel`. **Rejected clause: "potentially impacting upgrade smoothness."** B3 shows the baseline rejects it too ("unchanged"), so it is not an effect of the upgrade. An agent that ran on 0.1.8 already had to set `default_channel`. The rationale omits this. |

- **Verdict of the review:**
  - no rationale states a measured result that its cited facts do not contain. The rejected clause is a hedged,
    misleading implication, not a false measurement;
  - no claim of safety for arbitrary agents, real providers or production use.
  - The run is accepted as the first model-backed analysis, with the rejected clause recorded here. The clause stays
    visible, labelled *model-written*, in `analysis.md`, because evidence is never edited.
- **Not checked automatically:** the rejected clause passed every automatic check. This is why `analysis.md` lists
  rationale review under "Still needs human review".

**The targeted live test (not run; the operator's terminal only).** It runs one more real, billed agent turn, which
may involve several provider requests (`llm_calls` is not a request count). It writes to a temporary directory, not to
`evidence/`. Run it in the same PowerShell window, where `OPENAI_API_KEY` is already set:

```powershell
$env:SCOUT_LIVE_PROVIDER = "openai"; $env:SCOUT_LIVE_MODEL = "gpt-4.1-mini"
.venv\Scripts\python -m pytest "tests/test_live.py::test_live_analysis_of_the_real_phase3_comparison" -v -p no:cacheprovider --basetemp "$env:LOCALAPPDATA\mus\pt-live"
"pytest exit=$LASTEXITCODE"
```

`--basetemp` points at a separate short directory, so the next offline test run does not clear its output
(`...\mus\pt-live\test_live_analysis_of_the_rea0\analysis\`). The test checks the automatic criteria only, including
the transport counts; its rationales would need the same human review.

## Transport fix for F9 (verified offline with a MOCKED provider; live run consistent, see attempt-5)

**The defect.** In attempts 2–4, `comparison_evidence` returned its payload as one JSON string. The pinned SDK cuts
every string in a tool result to 1200 characters, so the model received V1 and S1–S4 and nothing else (F9).

**The change.**

- **`analysis.tool_payload`** now builds grouped, structured data:
  - `summary`: one short sentence of counts;
  - `report_sha256`;
  - `verdict`: `{id, value, statement}`;
  - `scope_rules` and `observations`: lists of `{id, statement}`;
  - `next_check_options`: a list of `{id, action, applies_because}`.

  Every fact and option appears exactly once, with its canonical id and text. It raises if there is not exactly one
  verdict fact, or if a fact has an unknown category, rather than dropping it.
  - The `summary` key exists because, without one, the SDK writes its own summary of the tool result: a
    600-character cut copy of the payload.
- **`analysis_worker.comparison_evidence`** returns a copy of that dict (`evidence_result`), not `json.dumps(...)`.
  Its description now names the groups.
- **Audit counts** in `worker/tool_calls.jsonl` are taken from the returned value: `"returned": {"verdict": 1,
  "scope_rules": 5, "observations": 11, "next_check_options": 3}`. Attempts 1–4 recorded `facts_returned`.
- **Instructions** name the groups: ids from `observations`, ids from `scope_rules`, and checks from
  `next_check_options`.
- **Preflight (`transport_problems`).** It checks the payload against the pinned SDK's limits (0.1.15
  `modules/brain/constants.py`; a test asserts that the installed constants are still these values):
  - strings: at most 1200 characters;
  - lists and dicts: at most 16 items;
  - nesting depth: less than 8;
  - `summary`: at most 600 characters.

  If anything fails, `analyze` writes the deterministic factual report, records `payload_exceeds_transport_limits`
  and each offending location (for example `payload.observations: 17 items exceed 16`), and exits 2. This happens
  before the credential check, so no worker or model call starts. It never trims.
- **Unchanged:** the factual report, the `ModelSelection` contract and its validation (unknown ids are still
  rejected), the scoped approval, the external deadline, and the output schema `analysis/2`. `analysis.json` gains
  a `transport_problems` list.
- **Known limit:** at most 16 observations. This comparison has 11. A comparison with more observations, for example
  many regressions, is refused by the preflight instead of being cut.

**Verification, offline, MOCKED provider** (`tests/test_tool_transport.py`; evidence in
`evidence/phase5/transport-verification/`):

- **Inputs:** the real Phase 3 comparison. A test asserts that its 17 facts and 3 options are identical to what
  attempt-4 sent, and that attempt-4's string was 4294 characters.
- **The full path.** The real worker, its `@tool`-decorated `comparison_evidence`, the approval callback and the
  installed SDK ran one turn against a local fake OpenAI endpoint. All provider requests were recorded.
- **The honest mock.** It answers with a selection only if every fact and option arrived with its id and full text,
  and builds that selection from what arrived. Otherwise it answers in prose, which the SDK rejects. A unit test
  shows that dropping one observation or one option, or cutting one statement, makes it answer in prose.

| Run | Tool returned | Post-tool tool message | Expected vs received | Truncation markers | Worker |
| --- | --- | --- | --- | --- | --- |
| **fixed** (grouped dict) | `{"verdict": 1, "scope_rules": 5, "observations": 11, "next_check_options": 3}` | 4163 characters; `outputs` **identical** to the returned payload; the same in both post-tool requests | **20 of 20 intact**: V1, S1–S5, P1, P2, R0, X1, X2, G1, C0, N0, B1, B2, B3, `set_default_channel`, `validate_with_real_provider`, `test_uncovered_building_blocks` | none | `completed`; the selection built from the received ids passes `validate_selection` |
| **negative control** (attempt-4's exact 4294-character string) | `{"type": "str", "chars": 4294}` | 1362 characters | **5 of 20**: V1 and S1–S4 only; S5, all 11 observations and all 3 options missing | `...[truncated]` | `output_invalid`: the mock refused, listing the 15 missing ids |

- The installed compactor (`_compact_tool_message_value`) returns the grouped payload unchanged. On attempt-4's
  string it returns 1200 characters plus `...[truncated]`.
- For each synthetic over-limit payload (a 1201-character statement, 17 observations, nesting 8 deep), the preflight
  names the location, and the installed compactor really does alter that payload.
- An `analyze --provider echo` run on the real report, into a scratch directory, passed the preflight
  (`transport_problems: []`). The worker request carried the grouped payload; echo was rejected as always.

**Confirmed, and still unverified.**

- **Confirmed offline:** the evidence leaves the tool and reaches the post-tool provider request complete, through the
  installed SDK's real tool-message path.
- **Live, attempt-5 (indirect):** the model used previously hidden ids and all 3 options, and its selection was
  accepted.
- **Unverified:**
  - a live provider request body (live bodies are not captured);
  - one SDK difference: the completion-judgment request, which does not produce the selection, now carries
    `{tool_name, ok, verified}` for this tool instead of a 300-character cut copy. Attempt-5 completed, so it did not
    block that run. Its effect on other runs is not studied.

**Tests.**

- full suite: **157 passed, 2 skipped**;
- `-m "not runtime"`: **150 passed, 2 skipped, 7 deselected**;
- `tests/test_tool_transport.py`: **12 passed** (2 of them `runtime`: the full path and the negative control).

**Preserved:** attempts 1–4 are byte-identical (7, 9, 9 and 9 files), and the source `report.json` sha256 is
`8b82e734…0fc93`.

### Attempt-5: command and acceptance checklist (ran 2026-10-29; SUCCESS, see *openai-attempt-5* above)

Run it in the operator's PowerShell window, where `OPENAI_API_KEY` is set:

```powershell
.venv\Scripts\python -m upgrade_scout analyze --report evidence/phase3/compare/0.1.8-vs-0.1.15/report.json --provider openai --model gpt-4.1-mini --output-dir evidence/phase5/analysis/openai-attempt-5 --deadline 600
"analyze exit=$LASTEXITCODE"
```

Accept only if **all** of these hold in `evidence/phase5/analysis/openai-attempt-5/`:

1. `analysis.json`: `schema: minion-upgrade-scout/analysis/2`, `status: success`, `failure_reasons: []`,
   `transport_problems: []`.
2. `worker.status: ok`, `worker.returncode: 0`, `runtime.run_state: completed`.
3. `worker/approvals.jsonl`: only `allow_once` for `comparison_evidence` with args `{}`.
4. `worker/tool_calls.jsonl`: at least one line, each with `"returned": {"verdict": 1, "scope_rules": 5,
   "observations": 11, "next_check_options": 3}`.
5. `worker/request.json` `facts_payload` has the grouped keys, and `model_selection` cites only real ids.
6. `factual_report.verdict == input.deterministic_verdict == "compatible"`. The report shows:
   - no export changes;
   - 6 identical signatures;
   - no gaps;
   - 0 regressions;
   - echo `tool_calls` 0/0;
   - the minimal config `rejected_invalid_channel` on both versions.
7. `input.report_sha256` equals the current hash, and attempts 1–4 are unchanged.
8. **Human review** of every *Model rationale* against its cited facts:
   - the ranking is sensible;
   - no stated result is missing from the cited facts;
   - no safety, real-provider or production claims.
9. Record the configured model, the runtime metadata, the usage (runtime-reported; `llm_calls` is not a request
   count) and the elapsed time.

Then run `tests/test_live.py::test_live_analysis_of_the_real_phase3_comparison` in the same window, with
`--basetemp "$env:LOCALAPPDATA\mus\pt"`.

## Offline reliability fix: analysis contract v2 (`minion-upgrade-scout/analysis/2`)

**The failure class it prevents.** Attempt 3, in contract v1, let the model write the verdict string and the factual
statements. The verdict came back decorated, and the statements invented export and signature changes and coverage
gaps, while citing only known ids. A synthetic copy with only the verdict corrected passed the v1 validator.
*Found after attempt-4 (F9):* attempt 3's model never received the observations. The SDK cut the tool result after
S4, which is why it paraphrased the scope rules S3 and S4 as results. Contract v2 still keeps such statements out of
the report: in attempt-4, the invented ids were rejected.

**The change (`upgrade_scout/analysis.py`).** `compare.py` and the probes are unchanged.

- **Application-owned output.**
  - The authoritative verdict, the factual summary and the core results are rendered from the validated
    comparison. The core results are always shown: export changes, signature changes, coverage gaps, regressions,
    echo tool calls, and minimal-config behavior.
  - The scope limitations and known rough edges are also application-rendered (`factual_report`).
  - The model never repeats or rewrites any of these.
- **Fact categories.** `verdict` (V1), `scope_rule` (S1–S5) and `observation` (P/R/X/G/C/N/B). Absences are
  explicit observations: R0, C0 and N0.
- **Bounded model role.** The `ModelSelection` output type, with `extra="forbid"`, contains:
  - `key_observations`: observation ids, ranked;
  - `relevant_limitations`: scope-rule ids;
  - `next_checks`: ranked ids from the **applicable options** that `next_check_options` derives from the
    comparison. For example, `review_signature_changes` exists only if signatures changed, and
    `fill_coverage_gaps` only if gaps were measured.

  Each check carries a rationale and its observation or scope-rule evidence ids. The application resolves every id
  to its canonical statement. The model-written rationale is shown only under *Model rationale (model-written)*.
- **Rejected:** unknown ids, wrong-category ids, repeated ids or checks, inapplicable checks, unexpected fields (a
  `verdict` or `summary` from the model is a schema error), and a rationale that claims compatibility for a
  non-compatible verdict. That last one is the existing narrow guard; no prose regexes were added.
- **Raw output.** It is always kept separately, in `worker/model_output.json`, with `accepted: true|false`.
- **Unchanged:** the Agent, the evidence tool, the scoped approval callback, the external deadline, the instructions
  in the run message, and every process and tool-execution check.
- **Tests:**
  - `tests/test_factual_report.py` (18 new) checks each requirement: the verdict can't be changed by the model; scope
    rules aren't observations; no-change evidence renders no changes and no gaps; the minimal config stays visible;
    fabricated rationale text stays out of the factual report; ids resolve to canonical text; the attempt-3 class
    of output is rejected; and compatible, regression and inconclusive outcomes stay distinct.
  - The real attempt-3 output, with only its verdict corrected (a synthetic derivative), is now rejected as a schema
    error, and the factual report states the opposite of its claims.
  - `tests/test_analysis.py` and `tests/test_instruction_capture.py` were moved to contract v2.
- **Results:**
  - affected tests: 79 passed;
  - full suite: **145 passed, 2 skipped**;
  - `-m "not runtime"`: **140 passed, 2 skipped, 5 deselected**.

  The 2 skips are the opt-in live tests.
- **Preserved:** attempts 1–3 are byte-identical and stay rejected. The source report sha256 is unchanged
  (`8b82e734…0fc93`).

### Attempt-4: command and acceptance checklist (ran 2026-10-29; FAILED, see the next section)

Run it in the operator's PowerShell window, where `OPENAI_API_KEY` is set. This is a new attempt budget and needs your
explicit go-ahead.

```powershell
.venv\Scripts\python -m upgrade_scout analyze --report evidence/phase3/compare/0.1.8-vs-0.1.15/report.json --provider openai --model gpt-4.1-mini --output-dir evidence/phase5/analysis/openai-attempt-4 --deadline 600
"analyze exit=$LASTEXITCODE"
```

Accept only if **all** of these hold in `evidence/phase5/analysis/openai-attempt-4/`:

1. `analysis.json` has `schema: minion-upgrade-scout/analysis/2`, `status: success`, and `failure_reasons: []`.
2. `worker.status: ok` and `worker.returncode: 0`; `runtime.run_state: completed`.
3. `worker/approvals.jsonl` shows only `allow_once` for `comparison_evidence` with args `{}`, and no other tool.
4. `worker/tool_calls.jsonl` exists, and `tool_execution.python_invocations >= 1`.
5. `factual_report.verdict == input.deterministic_verdict == "compatible"`.
   - The factual report shows: no export changes, 6 identical signatures, no coverage gaps, 0 regressions, echo
     `tool_calls` 0/0, and the minimal config `rejected_invalid_channel` on both versions.
6. `input.report_sha256` still equals the current `report.json` hash, and attempts 1–3 are unchanged.
7. **Human review of the model's part:**
   - the ranking is sensible;
   - each *Model rationale* states no result that its cited facts do not contain;
   - no rationale implies safety for arbitrary agents, real providers, or production use.
8. Record the configured model and the runtime metadata, the usage (or "missing telemetry"), and the elapsed time.

Then run `tests/test_live.py::test_live_analysis_of_the_real_phase3_comparison` in the same window, with
`--basetemp "$env:LOCALAPPDATA\mus\pt"`.

### `openai-attempt-4` (first live contract-v2 run): FAILED (`selection_invalid`), preserved unchanged

The operator ran it in their terminal; `evidence/phase5/analysis/openai-attempt-4/`.

| Check | Result |
| --- | --- |
| 1. schema, status, failure reasons | `minion-upgrade-scout/analysis/2`; **`status: failed`**; `failure_reasons: ["selection_invalid"]`. **FAIL** |
| 2. worker and turn | `worker.status: ok`, `returncode: 0`, 21.0 s; `runtime.run_state: completed`. Pass |
| 3. approvals | one `allow_once` for `comparison_evidence`, args `{}` (approval id `call_xyAnzBSfGGPpFQQUZjx2nHPA`); no other tool. Pass |
| 4. tool execution | `tool_calls.jsonl`: **1** Python-side invocation, returning 17 facts; runtime `tool_calls=1`. Pass |
| 5. factual report | `compatible`, equal to `input.deterministic_verdict`. It shows no export changes (12 -> 12, 15 -> 15), 6 of 6 signatures identical, no coverage gaps, 0 regressions, echo `tool_calls` 0/0, and the minimal config `rejected_invalid_channel` on both versions. Recomputing `factual_report`, `facts` and `next_check_options` from the source report gives identical values, and `recheck` matches. Pass |
| 6. preservation | source `report.json` sha256 `8b82e734…0fc93` is unchanged; attempts 1–3 match their recorded hashes (7, 9 and 9 files). Pass |
| 7. human review | the selection was rejected; the review of the rationales is below. **FAIL** |
| 8. metadata | configured `openai` / `gpt-4.1-mini`; runtime `provider=openai`, `model=brain-orchestrator`. Usage as reported by the runtime: `llm_calls=1`, `input_tokens=8578`, `output_tokens=355`, `duration_ms=14223`. `llm_calls` is not a provider request count: the offline replay reported `llm_calls=1` for 8 captured requests. `run_id 717d4004ae8c4328bb8bb5b3f6d17999`, `request_id 5d887ab80ce24e81b6eee8c76556ba4f`. Recorded |

- **The rejected selection** (`worker/model_output.json`, `accepted: false`):
  - `key_observations`: O2, O1, O3. **None of these ids exists.**
  - `relevant_limitations`: S1, S2, S4, S3. These are valid scope-rule ids.
  - `next_checks`: C2, C1, C3. **None is an option.** The applicable options were `set_default_channel`,
    `validate_with_real_provider` and `test_uncovered_building_blocks`.

  Validation reported 9 problems: 3 unknown observation ids, 3 inapplicable checks, and 3 unknown evidence ids.
- **Root cause: the model never received the observations or the options (F9).**
  - The SDK builds the tool message with `_truncate_tool_message_text` (`modules/brain/loop/tools/messages.py`), and
    `TOOL_MESSAGE_STRING_LIMIT = 1200` (`modules/brain/constants.py`). These are the same in 0.1.8 and 0.1.15.
  - `comparison_evidence` returns its payload as **one 4294-character JSON string**, so the model saw the first 1200
    characters plus `...[truncated]`. That is V1 and S1–S4, with S4's statement ending exactly at character 1200.
    S5, all 11 observations and `next_check_options` were cut. *(Corrected after the transport fix: this line first
    said "S4 cut mid-sentence" and "12 observations". S4 was cut mid-sentence only in attempts 2 and 3.)*
  - **Verified offline:** `evidence/phase5/sdk-observations/f9-tool-result-truncation.txt`. It replays attempt-4's
    real request (instructions, message, facts payload) through the real worker and the installed SDK against the
    MOCKED endpoint from `tests/test_instruction_capture.py`. The tool message in the post-tool request is 1362
    characters, ends in `...[truncated]` after S4, and contains no X1, G1, B3 or `next_check_options`.
  - **Consistent with the real output:** the only real ids the model used are S1–S4, exactly the scope rules visible
    before the cut. It never used S5 or any observation id. It invented O1–O3 and C1–C3 for what it could not see.
  - **The same cut in attempts 2 and 3.** Their 3631-character payloads were cut inside S4's statement ("...not
    counted as a regressi"). Attempt 3 cited only
    V1 and S1–S4. Its "added exports and signature differences" and "coverage gaps exist" paraphrase S3 and S4,
    because no observation reached it.
  - **Why offline verification missed it.** `tests/test_instruction_capture.py` used a one-fact payload, far below
    the limit, and no test checked that the tool result reaches the provider request intact. That is an application
    defect: this tool did not account for a limit that is visible only in the SDK source. It is not claimed as an SDK
    defect; the limit looks like deliberate context budgeting.
  - Not verified: the live provider request bodies, which were not captured. The SDK's tool-message construction path
    is the same for the mocked and the real endpoint.
- **Contract v2 behaved as designed.** No invented statement reached the report: the factual report is identical to
  the one recomputed from the source, and the selection was rejected for unknown ids, before any human review.
- **Review of every model-written rationale against its cited facts.** None was accepted. Each is reviewed anyway:

  | Check | Rationale (model-written) | Cited | Review |
  | --- | --- | --- | --- |
  | C2 (not an option) | "Validating the handling of tool calls is crucial since the echo provider does not invoke a model call, and this check helps verify that the tool interactions remain consistent." | S2, O3 (unknown) | The premise matches S2. The intent is close to the real option `validate_with_real_provider`. Nothing false, but it cites a fact that does not exist. |
  | C1 (not an option) | "Ensuring the public exports and API signatures continue to work correctly covers the primary upgrade surface, as these are the main program interfaces affected by the upgrade." | S1, S3, O1 (unknown) | **Unsupported.** "Affected by the upgrade" implies change; X1, X2 and G1 show none. No applicable option exists for it. |
  | C3 (not an option) | "Reviewing changes to entry point signatures is recommended because added or removed parameters could impact API compatibility and are not automatically flagged as regressions." | S3, O2 (unknown) | **Contradicts its own citation.** S3 says removed and newly required parameters *are* counted as regressions. **Built on nothing:** G1 shows 0 changed signatures, so `review_signature_changes` was correctly not offered. |

  - The automatic checks would not have caught C3's contradiction of S3 if its ids had been valid. Human review of
    the rationales remains necessary.
  - The ranking cannot be judged: the model ranked ids for facts it never saw.
- **Not done:**
  - no attempt-5 was launched;
  - validation was not changed;
  - no code was changed;
  - the targeted live pytest was not run.
- **Proposed fix (HISTORICAL; implemented and verified offline, see the next section).**
- **Repository state:** `git init` only. No commits, no remote, nothing pushed or published, no upstream issues filed.

## Current status (Phase 5)

| What | Status | Evidence |
| --- | --- | --- |
| Deterministic comparison, 0.1.8 vs 0.1.15 | done, real: `compatible` **within its stated probe scope only** | `evidence/phase3/compare/0.1.8-vs-0.1.15/report.md` |
| Real model-backed `analyze` turns | 5 real OpenAI `gpt-4.1-mini` attempts: 1–3 under contract v1; 4 and 5 under contract v2; 5 after the transport fix | `evidence/phase5/analysis/openai-attempt-{1,2,3,4,5}/` |
| Model-driven execution of `comparison_evidence` (Python-side) | **observed: 1 invocation each in attempts 2–5**, 0 in attempt-1. Attempts 2 and 3 returned 14 facts, attempt-4 17 (one string), and attempt-5 1 verdict, 5 scope rules, 11 observations and 3 options (structured). Runtime `tool_calls=1` in attempts 3–5. | `worker/tool_calls.jsonl` and `worker/approvals.jsonl` in attempts 2–5 |
| What the model received from the tool | attempts 2–4: **only the first 1200 characters** (V1, S1–S4), because the SDK truncates each tool-result string (F9). Attempt-5 (structured return): the full payload. This was verified offline with a MOCKED provider (20 of 20 items intact), and is consistent with the live run (previously hidden ids used). | `evidence/phase5/sdk-observations/f9-tool-result-truncation.txt`; `evidence/phase5/transport-verification/summary.txt` |
| Accepted model contribution | **attempt-5: accepted** (automatic checks, plus human review with one rejected clause). Rejected: attempt-1 `output_invalid` (approval prompt), attempt-2 `output_invalid` (prose), attempt-3 `brief_invalid` (verdict field), attempt-4 `selection_invalid` (unknown ids O1–O3 and C1–C3). | `analysis.json` in each attempt directory |
| Structured output | real replies passed SDK validation in attempts 3, 4 and 5. Only attempt-5's also passed this tool's checks. | `worker/result.json` in attempts 3–5 |
| Targeted live pytest | **not run**; the command is under *openai-attempt-5* | `tests/test_live.py` |
| Judging notes | updated with attempt-5's evidence and its human review | `docs/` |
| Demo video | **not recorded** | `docs/DEMO_SCRIPT.md` |

## Phase 5 attempt log (attempts 1–4 rejected; attempt-5, recorded above, succeeded)

### `openai-attempt-1`: FAILED, preserved unchanged

- **Run:** operator terminal, `gpt-4.1-mini`, evidence in `evidence/phase5/analysis/openai-attempt-1/`.
- **Result:** the worker exited 0 after 10.9 s, and the analysis failed with `output_invalid` and
  `tool_not_executed`. Python-side tool invocations: **0**. The runtime returned no stats, which is missing
  telemetry, not zero usage.
- **Diagnosis, from `worker/result.json` `raw_text`.** The turn's reply was the runtime's own confirmation request:

  ```text
  Policy confirmation required.
  comparison_evidence
  Risk: write
  ...
  Reason: UNKNOWN_REVERSIBILITY
  ```

  - A `comparison_evidence` call was proposed and held for approval. No approval callback was supplied, so the prompt
    came back as the reply text and failed `UpgradeBrief` validation.
  - This is an **unhandled tool-approval flow**. It is not evidence about the model's brief, and it does not show
    successful inference or tool execution.
- **SDK source:**
  - `@tool` without `min_scope` defaults to `WRITE_SAFE` (`tools/decorator.py:228`).
  - The default policy requires confirmation for a non-read tool with unknown reversibility
    (`modules/policy/runtime/service.py:544`).
  - With `Agent.run(approval_callback=...)`, the runner asks the callback (`modules/brain/runner/delegates.py:294`).
    `False` becomes `DENY`. `True` grants once, and then the policy is evaluated again.
  - This is classified as an **SDK integration finding**, not an SDK defect. The classification is accurate, because
    the tool appends an audit line to `tool_calls.jsonl`, a local write.
- **Fix (`upgrade_scout/analysis_worker.py`, `make_approval_callback`).** The callback approves only
  `comparison_evidence` with exactly empty arguments (a one-time `allow_once`) and denies every other tool or
  argument.
  - Every decision is recorded in `worker/approvals.jsonl` and summarized in `analysis.json` (`approvals`).
  - SDK policies, the tool metadata, and all output validation and acceptance criteria are unchanged.
  - **Tests:**
    - allow;
    - deny for 5 other tool names;
    - deny for 5 unexpected-argument shapes;
    - the worker routing confirmations through the callback (mocked runtime);
    - that the installed `Agent.run` accepts `approval_callback`.
  - **Suites:** 126 passed, 2 skipped. With `-m "not runtime"`: 122 passed, 2 skipped, 4 deselected.
- **Unverified until attempt-2:** whether the real runtime invokes the callback, whether the tool body then
  executes, and whether the brief validates.

### `openai-attempt-2`: FAILED (`output_invalid`), preserved unchanged

- **What worked:**
  - the worker exited 0 (19.9 s);
  - `approvals.jsonl` shows one `allow_once` for `comparison_evidence` with args `{}`;
  - the tool's Python body **executed once** and returned 14 facts (`tool_calls.jsonl`).
- **What failed:** the reply was a prose upgrade brief, not `UpgradeBrief` JSON, so it was rejected. It also
  overclaimed ("safe path", "without disruption", "proceed with the upgrade"), which these probes do not establish.
  The runtime returned no stats, so usage is missing telemetry, not zero.
- **Offline request-capture diagnostic.** A local fake OpenAI endpoint (a mocked model) drove the real SDK, the real
  worker and the real approval callback, with the provider requests recorded. One turn made 8 provider requests.
  - **Confirmed: truncation.** `Agent.instructions` reached the system prompt only inside the SDK's identity section,
    cut to its budget: **880 of 2704 characters**, followed by `...[truncated]` and the persona wrapper. The cut fell
    inside the JSON schema, so the closing rules never arrived. Source: `_fit_to_budget` in
    `modules/context/pack/budgeting.py`, applied in `modules/context/pack/identity.py`.
  - **Confirmed: missing after the tool.** The requests made after the tool result (requests 5 and 6) had **no**
    analysis instructions in their system messages; they had an SDK "Tool-calling contract" instead.
  - **Not confirmed: the proposed cause.** `services/brain/post_execution/followup.py::_follow_up_after_tool` has no
    callers in installed 0.1.15. It is bound to the mixin and never invoked.
  - **Not confirmed: the proposed fix.** Adding the same instructions to the profile `system_prompt` produced the same
    8-request pattern: still truncated, still absent after the tool. It was not adopted.
  - **Confirmed: what does reach every request.** The run's **user message** reached all 8 requests verbatim,
    including the post-tool ones.
  - **Inferred, not proven for the real provider:** that the model produced prose because the JSON contract never
    reached its final request. Attempt-2 lost its runtime metadata (F6), so the request that produced its reply is
    unknown.
  - This is an SDK integration finding. No SDK defect is claimed: the identity budget may be intended for persona text.
- **Minimal change (`upgrade_scout/analysis.py`):**
  - `run_message()` repeats the full `instructions()` in the run message;
  - `Agent.instructions` is kept as it was;
  - one added instruction rule limits the brief to the probe scope (no "safe", "disruption-free", arbitrary-agent,
    real-provider, or production claims).
  - `UpgradeBrief`, the citation checks, the approval restrictions, and the deterministic verdict are unchanged.
- **Regression test:** `tests/test_instruction_capture.py`, marked `runtime`, with a mocked model.
  - Through the real SDK, the tool runs once and every post-tool request carries the full instructions verbatim; the
    turn then completes with SDK-validated output.
  - A negative control with the pre-fix message makes it fail at the post-tool assertion.
- **Suites:** 127 passed, 2 skipped. With `-m "not runtime"`: 122 passed, 2 skipped, 5 deselected. Attempts 1 and 2
  are byte-identical.

### `openai-attempt-3` (the last corrective retry): FAILED (`brief_invalid`), preserved unchanged

- **Process and turn:**
  - the worker exited with status `ok` and exit code 0 after 15.3 s;
  - the runtime reported `run_state: completed`;
  - runtime identifiers: `run_id d0a21ff10d824f47af7099adc30e7362`, `request_id b84626b35bf441df9dd224764c1a66ba`,
    `execution_id 74553f11e311414889d03968d84c2574`, `invocation_id fa24407cae5f4d408fe5093ef514177a`.
- **Provider and model.** Configured: `openai`, `gpt-4.1-mini`. Runtime metadata: `provider=openai`,
  `model=brain-orchestrator`. The runtime metadata does not name the model.
- **Approval and tool:**
  - one `allow_once` for `comparison_evidence` with args `{}` (approval id `call_IdCpe7WSxtOEXUpV7em17DTL`);
  - the Python body **executed once** and returned 14 facts;
  - the runtime reported `tool_calls=1`.
- **Usage, reported by the runtime:** `llm_calls=1`, `input_tokens=6223`, `output_tokens=662`,
  `cache_read_tokens=0`, `duration_ms=10447`.
- **Structured output.** The reply (`scout: {...}`) was accepted by the SDK as `UpgradeBrief`, so the worker status is
  `completed`. Every cited id (V1, S1, S2, S3, S4) is a supplied fact.
- **Rejected by the verdict lock.** The `verdict` field was `"compatible (exit code 0); comparison complete: True."`,
  not exactly `"compatible"`. The model copied the remainder of fact V1's sentence.
  - The instruction ("exactly the deterministic verdict in fact V1") is ambiguous given how V1 is worded. The exact
    value was also present in the tool result's top-level `verdict` field.
  - This is an **application prompt defect**, not an SDK finding.
- **Factual review of the rejected brief.** It would also have failed review:
  - **False:** the summary says there are "added exports and signature differences". X1 and X2 show none added, and
    G1 shows all 6 signatures identical.
  - **Overclaim:** "The upgrade proves compatibility" is unscoped.
  - **Misleading:** "capturing forced tool use", when echo's `tool_calls` was 0 (B2).
  - **Misleading:** "Coverage gaps exist". This comparison has none; S4 only defines what a gap is.
  - **Omission:** no rough edges, although B3 (minimal config rejected on both versions) is one.
  - **Built on nothing:** next checks 2 and 3 target signature changes and gaps that do not exist.
  - The model treated the S scope-rule facts as observations and never cited X, G or B.
  - *Found after attempt-4 (F9):* the X, G and B facts never reached the model. The SDK cut the tool result after S4,
    so the model could cite only V1 and S1–S4.
  - **Lesson:** valid citations do not make a statement true.
- **Source evidence is unchanged.** `report.json` sha256 `8b82e734…0fc93` equals the recorded input hash. All three
  attempt directories are byte-identical to their state when inspected.
- **Not done:**
  - no fourth attempt was launched;
  - validation was not changed;
  - the targeted live pytest was not run, because the instruction was to run it after a success.

### Possible next fixes after attempt-3 (HISTORICAL; superseded by analysis contract v2, above)

Both proposals were superseded in a stronger form:

1. **The verdict.** Instead of making the model's verdict unambiguous, the model no longer outputs a verdict; the
   application renders it.
2. **Scope rules vs observations.** The facts now carry categories, and absences are explicit observations
   (R0, C0, N0).

## Phase 5 first status note (HISTORICAL, written before attempt-1)

- **Credential check (2026-10-29, presence only):** none of the seven provider key variables is set in the Process,
  User or Machine scope, and Ollama is not reachable. No live attempt was made, and `evidence/phase5/` does not exist
  yet. No new missing-credential artifact was created.
- **Verified without a credential:**
  - the target `evidence/phase3/compare/0.1.8-vs-0.1.15/report.json` validates (14 facts, 11 evidence files) and is
    unchanged (sha256 `8b82e734b19d99b00f4e2d0eca44807f0ffeb6efa3660fa1743afc68a8e0fc93`);
  - the SDK parses the OpenAI config that `analyze` writes (`openminion config show` exit 0, key variable
    `OPENAI_API_KEY`);
  - test suite: 113 passed, 2 skipped; with `-m "not runtime"`, 109 passed, 2 skipped, 4 deselected;
  - the targeted live test, with `--basetemp` on a short path, skipped as expected.
- **Operator action.** Run everything in **one** PowerShell terminal: a variable set in another terminal does not
  reach an already-running process.

  ```powershell
  cd "<repository root>"
  $secure = Read-Host -AsSecureString "OpenAI API key"
  $env:OPENAI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)); Remove-Variable secure
  .venv\Scripts\python -m upgrade_scout analyze --report evidence/phase3/compare/0.1.8-vs-0.1.15/report.json --provider openai --model gpt-4.1-mini --output-dir evidence/phase5/analysis/openai-attempt-1 --deadline 600
  $env:SCOUT_LIVE_PROVIDER = "openai"; $env:SCOUT_LIVE_MODEL = "gpt-4.1-mini"
  .venv\Scripts\python -m pytest "tests/test_live.py::test_live_analysis_of_the_real_phase3_comparison" -v -p no:cacheprovider --basetemp "$env:LOCALAPPDATA\mus\pt"
  ```

  - **Never reuse an attempt directory.** `analyze` clears its output directory before each run. Any retry goes to
    `...-attempt-2`, and only after the failure in `attempt-1` has been diagnosed.
  - Delivery documents are updated only after a verified success.

## Status at a glance (HISTORICAL, as of Phase 4; superseded by "Current status (Phase 5)" above)

| What | Status at the end of Phase 4 | Evidence |
| --- | --- | --- |
| Deterministic comparison, 0.1.8 vs 0.1.15 | done, real: `compatible` within its stated scope | `evidence/phase3/compare/0.1.8-vs-0.1.15/report.md` |
| Recheck of every saved comparison | done: verdicts reproduce from raw evidence | `evidence/phase3/recheck/` |
| `analyze` workflow (Agent, `@tool`, `output_type`, external deadline) | implemented; verified offline and through real-SDK failure paths | `tests/test_analysis.py`; `evidence/phase4/analysis/echo-test-only/` |
| **Real model-backed analysis** | (as of Phase 4) **blocked: never run**. Superseded: three real OpenAI attempts ran in Phase 5. | `evidence/phase4/analysis/openai-blocked-missing-credentials/` |
| **Model-driven execution of `comparison_evidence`** | (as of Phase 4) **not observed: 0 Python-side invocations in every real run up to Phase 4**. Superseded: 1 invocation each in Phase 5 attempts 2 and 3. | `analysis.json`, `tool_execution.python_invocations` |
| Judging notes | written, from observed evidence only | `docs/BUILDING_BLOCKS_TESTED.md`, `docs/WHAT_WE_LEARNED.md`, `docs/DEMO_SCRIPT.md` |
| Demo video | not recorded; the script's live section is marked PENDING | `docs/DEMO_SCRIPT.md` |

## 1. Defects fixed in Phase 4 (application defects, shown with synthetic fixtures; not SDK findings)

The reproduction script ran against the `tests/test_analysis.py` helpers. The raw evidence and derived comparison
fields were left unchanged.

| Case | Before | After |
| --- | --- | --- |
| A1: `versions.candidate.installed_version` set to `"999.999.999"` | accepted; fact P2 said "installed 999.999.999" | rejected before any model call: `EvidenceError: versions.candidate does not match its raw evidence (fields: installed_version)` |
| A2: `scope[1]` replaced with "Real model inference and model-driven tool execution succeeded." | accepted; fact S2 presented the false claim | rejected before any model call: `EvidenceError: report scope differs from this tool's schema-2 probe definitions` |
| B: `judge(process={"status": "failed", "returncode": 7}, ...)`, with a valid mocked result and a tool call | `success` | `failed`, `failure_reasons=["worker_process_failed"]`, `brief=None` |

### What changed

- **`validate_inputs`.** Before any model call, it now requires:
  - `scope == SCOPE` and `echo_contract == ECHO_CONTRACT`. These are the definitions of the supported schema.
  - every version summary field to equal `version_facts()`, recomputed from the raw `preflight`, `surface` and
    `environment` evidence. The fields are requested, installed and imported versions, Python, platform,
    environment, and `evidence_dir`.
- **`load_records`.** It now checks that each stage file was written by that stage's probe, for that requested
  version, and that `evidence_dir` is `<role>-<version>`.
- **Facts.** `build_facts(comparison, records)` builds them from the *recomputed* comparison and the raw records, and
  never reads report text.
- **`judge`.** A brief requires `process.status == "ok"` and `returncode == 0`. Failed, error, and timeout states are
  rejected even when a result file exists. The mocked process fixtures now follow `run_bounded`'s contract:
  `{"status": "ok", "returncode": 0}`.
- **New `analysis.json` fields.** It records `elapsed_seconds`, and `usage`, which distinguishes missing telemetry
  (`available: false`) from reported zeros.
- **New tests:**
  - A1 and A2, each separately;
  - 4 more declaration mutations: `echo_contract`, Python, environment status, and a mismatched `requested_version`;
  - stage evidence from another version;
  - an unsafe stage evidence name;
  - facts built from validated data;
  - 4 process-contract cases, including the reviewer's exit 7;
  - a timed-out worker that left a result file;
  - usage semantics;
  - an opt-in live test of the real `analyze` workflow (`tests/test_live.py::test_live_analysis_of_the_real_phase3_comparison`).
- **Real evidence still validates.** The real Phase 3 report validates under the stricter rules, producing 14 facts
  from 11 evidence files. All four `recheck` runs keep their exit codes (0, 0, 3, 0).

## 2. Real end-to-end analysis: blocked (HISTORICAL, Phase 4; superseded by the Phase 5 attempt log)

- **Credential check, presence only.** `OPENAI`, `ANTHROPIC`, `OPENROUTER`, `GROQ`, `CEREBRAS`, `OLLAMA` and
  `CORTENSOR` `_API_KEY` are all unset in the process, User and Machine scopes. There is no `.env` in the repository,
  and Ollama is not reachable at `localhost:11434`.
- **The user reports hosted-provider access,** but no credential reached this environment. No live attempt was made,
  so there is no attempt evidence to diagnose and no retries were used.
- **Recorded in Phase 4.** Neither run below is a live attempt:

  | Run | Exit | Result | Python-side tool invocations | Evidence |
  | --- | --- | --- | --- | --- |
  | `analyze --provider openai --model gpt-4.1-mini` (no key) | 2 | `missing_credentials`; no worker started | 0 | `evidence/phase4/analysis/openai-blocked-missing-credentials/` |
  | `analyze --provider echo` (real SDK; **test evidence only**) | 1 | `echo_provider_is_not_a_model`, `output_invalid`, `tool_not_executed`; worker exited 0 after 6.1 s; usage "missing telemetry, not zero usage" | 0 | `evidence/phase4/analysis/echo-test-only/` |

- **The source comparison is unchanged.** `report.json` sha256 is
  `8b82e734b19d99b00f4e2d0eca44807f0ffeb6efa3660fa1743afc68a8e0fc93`, before and after.
- **Live validation, once a credential exists.** Follow README, *Running it live* (now in `docs/REFERENCE.md`): OpenAI
  uses the `OPENAI_API_KEY` variable, entered with a non-echoing PowerShell prompt and scoped to the session. The
  first attempt goes to `evidence/phase4/analysis/openai-live-attempt-1`. *(That directory was never created; the
  live attempts ran in Phase 5, under `evidence/phase5/analysis/`.)* A later attempt is made only after a concrete failure has been
  diagnosed, with at most two corrective retries, each in its own `...-attempt-N` directory.

  Success must show all of these in `analysis.json`:
  - `status: success`;
  - `worker.status: ok` and `worker.returncode: 0`;
  - `runtime.run_state: completed`;
  - `tool_execution.python_invocations >= 1`;
  - `brief.verdict == input.deterministic_verdict`;
  - an `input.report_sha256` that matches the current file.

  The brief's claims must then be checked by hand against the cited facts.

## 3. Cortensor documentation: corrected

My earlier statement that "no Cortensor provider guide or Portal endpoint is documented" was **wrong**. The guide is
at <https://www.openminion.com/docs/examples/providers/cortensor/>. It documents two routes, both using
`CORTENSOR_API_KEY`:

- the hosted **Portal**: preset `cortensor-portal`, OpenAI-compatible, `https://api.cortensor.app/v1`, model `oss-20b`;
- the direct **Router**: preset `cortensor-router`, `http://127.0.0.1:8080/api/v2/completions`, model `gpt-oss-20b`.

The guide does not say which release introduced them.

Three separate questions, answered separately:

- **Is it documented?** Yes, see above.
- **Does the installed SDK support it?**
  - Searching the installed sources (`grep -rIl --include=*.py 'cortensor-portal'` under `site-packages/openminion`)
    finds the presets in all three environments: the controller `.venv` (0.1.15), `mus/envs/0.1.15` and
    `mus/envs/0.1.8`. The files are `modules/llm/setup_catalog.py` (lines 129 and 144, with
    `_PRESET_ALIASES = {"cortensor": "cortensor-router"}`) and `cli/commands/setup.py`.
  - `openminion setup --list-providers`, run in an isolated home, lists both presets.
  - **This differs from the review note**, which found no preset strings. The commands above reproduce our
    observation.
  - The presets are applied through `openminion setup`. `analyze` writes a plain `provider:` config, so it reaches
    only the Router alias. Using Portal through `analyze` is not implemented or verified.
- **Are credentials available?** No `CORTENSOR_API_KEY` is set.

## 4. Judging material (`docs/`)

- **`BUILDING_BLOCKS_TESTED.md`:** one row per building block: what we used, what worked, what did not or is pending,
  and the evidence path.
- **`WHAT_WE_LEARNED.md`**, in four groups:
  - **Verified runtime findings:**
    - F1, the CLI accepting the minimal config while `Agent.run` rejects it (now with retained evidence);
    - F2, the cwd `.openminion/` (now with retained evidence);
    - F3 and F4;
    - what worked as documented;
    - environment observations.
  - **Source-inspection observations:** F5, F6, the Cortensor presets, and the docs version lag.
  - **Application defects:** Phases 2–4.
  - **Unanswered questions.**

  Each actionable item has the version and environment, a reproduction, expected versus actual behavior, a
  workaround, an evidence path, and a suggestion. Nothing is called a confirmed SDK bug.
- **`DEMO_SCRIPT.md`:** about 4 minutes. Its model-analysis section is explicitly **PENDING**.

### New Phase 4 observations, retained in `evidence/phase4/sdk-observations/`

- **`f1-cli-vs-sdk-minimal-config.txt`:** same config, fresh home, 0.1.15. `openminion run` exits 0, and
  `Agent.run` raises `invalid_channel`.
- **`f2-runtime-creates-cwd-dirs.txt`:** `APIRuntime` start and close creates 7 empty directories under the cwd.
- **`env-long-home-sqlite-backup.txt`:** in a deep `OPENMINION_HOME`, under the session temp dir, an SDK runtime
  start followed by `openminion run` exits 2 with `SQLite online backup failed ... policy.db: unable to open database
  file`. The same steps under a short home exit 0.
  - The longest existing file in that home was 255 characters, so path length is the likely cause. It is not
    verified, and it is **not** claimed as an SDK defect.
  - It also qualifies a Phase 1 note: the CLI's success with the minimal config was observed in a shallower home. It
    is confirmed again here in fresh short-path homes.

## Tests (exact results)

**Current, after the F9 transport fix:**

| Command | Result |
| --- | --- |
| `python -m pytest -q -rs -p no:cacheprovider` | **157 passed, 2 skipped, 0 failed** |
| `python -m pytest -q -rs -p no:cacheprovider -m "not runtime"` | **150 passed, 2 skipped, 7 deselected** |
| `python -m pytest -q -p no:cacheprovider tests/test_tool_transport.py` | **12 passed** |

**After analysis contract v2, before the transport fix:** 145 passed, 2 skipped. With `-m "not runtime"`: 140 passed,
2 skipped, 5 deselected.

**Earlier in Phase 5**, after the approval callback and the run-message change: 127 passed, 2 skipped. With
`-m "not runtime"`: 122 passed, 2 skipped, 5 deselected.

The 2 skipped are the opt-in live tests: this process has no key, which lives only in the operator's terminal.

**HISTORICAL, Phase 4:**

| Command | Result |
| --- | --- |
| `python -m pytest -v -rs -p no:cacheprovider` | **113 passed, 2 skipped, 0 failed** (23.52 s); saved to `evidence/phase4/pytest-phase4.txt` |
| `python -m pytest -q -rs -p no:cacheprovider -m "not runtime"` | **109 passed, 2 skipped, 4 deselected** (19.00 s) |
| focused Phase 4 tests (`-k` over the new test names) | **15 passed**, 32 deselected |

- **Skipped:** both opt-in live tests in `tests/test_live.py`, because no credential is available.
- **Deselected:** the 4 tests marked `runtime`.
- **Cases per file:**

  | File | Cases |
  | --- | --- |
  | `test_analysis.py` | 47 |
  | `test_compare.py` | 30 |
  | `test_workers.py` | 17 |
  | `test_sdk_smoke.py` | 8 |
  | `test_probe.py` | 8 |
  | `test_cli.py` | 3 |
  | `test_live.py` | 2 |

## Remaining user actions and unmet submission requirements (current)

1. **Done:**
   - an accepted live analysis (`openai-attempt-5`);
   - a clean-install reproduction (`evidence/phase6/`);
   - the submission material (`docs/SUBMISSION.md`, the README and the demo script).
2. **Optional but recommended: run the targeted live pytest** in the credential-bearing terminal (command under
   *openai-attempt-5*). It is one more real, billed agent turn, possibly several provider requests. Review its
   rationales the same way.
3. **Decide on licensing** (an owner decision). The rules ask for properly licensed code and data, but do not mandate
   a `LICENSE` file or a particular license.
4. **Done:** the first commit and the public repository (<https://github.com/BerkPasha/minionscout>). See
   *Publication* for its verification.
5. Keep the repository URL in the submission pull request.
6. **Record the 1–5 minute demo video** (`docs/DEMO_SCRIPT.md`). Publish it and fill in its URL.
7. **Submit by pull request** to the dedicated Hackathon #5 repository, once its URL is published (not listed as of
   2026-10-29). Check the cutoff on DoraHacks.
8. **Optional:** decide whether to report F1 upstream. docs.cortensor.network requires a fix PR for the bug bonus.

---

## History (condensed; all evidence preserved)

- **Phase 3.**
  - Fixed two comparison defects: coverage gaps now make a comparison inconclusive, and a 4-check echo contract was
    added.
  - Introduced report schema 2 and `recheck`.
  - Added `analyze` (Agent, `@tool comparison_evidence` with `forced_tools`, `output_type=UpgradeBrief`, a worker
    child process with an external deadline, and an independent `tool_calls.jsonl`).
  - Evidence: `evidence/phase3/` (the comparison, the recheck summaries, and three failed analysis attempts:
    `echo-test-only`, `cortensor-blocked-attempt`, `openai-missing-credentials`), and `pytest-phase3.txt`
    (98 passed, 1 skipped).
- **Phase 2.**
  - `compare`, with per-version venvs under `%LOCALAPPDATA%\mus` and one shared probe in bounded processes.
  - 0.1.8 vs 0.1.15: `compatible`. 0.1.15 vs 0.1.15: `compatible`. An artificial timeout run: `inconclusive`.
  - Two bugs in this tool fixed: a relative output path, and the OneDrive `PermissionError` retry.
  - Evidence: `evidence/phase2/`.
- **Phase 1.**
  - The scout agent, isolated from `~/.openminion` (which has never been created).
  - F1–F4.
  - Windows `LongPathsEnabled=0`, with the deepest package file 131 characters below `site-packages`.
  - Evidence: `evidence/*.json`, `evidence/pytest-phase1.txt`.

## Hackathon sources (attributed)

| Topic | [docs.cortensor.network](https://docs.cortensor.network/community-and-ecosystem/hackathon/hackathon-5) | [docs-v2.cortensor.network](https://docs-v2.cortensor.network/ecosystem/hackathon-5/) ("Last updated: 2026-10-07") |
| --- | --- | --- |
| Kickoff / deadline | October 16 / December 18, 2026 (Pacific Time) | TBD / TBD; build period "approximately 3–4 weeks" |
| Bonus | "...substantive fix PRs..."; a bug report without a fix PR does not qualify | "...reproducible bugs, fixes..."; no separate section |

**Both pages require** a real model-backed run in a 1–5 minute demo, plus the "Building Blocks Tested" and "What We
Learned" notes. **Both say** the submission repository URL "will be added before kickoff".

## Commands executed in Phase 4

```text
credential presence check: bash env + PowerShell [Environment]::GetEnvironmentVariable(User/Machine); .env search; curl localhost:11434   -> nothing available
python <scratch>/repro_phase4.py      # before: A1 ACCEPTED, A2 ACCEPTED, B success
                                      # after:  A1 REJECTED, A2 REJECTED, B failed [worker_process_failed]
WebFetch openminion.com/docs/examples/providers/cortensor/
grep -rIl 'cortensor-portal|cortensor-router|api.cortensor.app' in .venv, mus/envs/0.1.15 and mus/envs/0.1.8   -> present in all three
openminion setup --list-providers (isolated OPENMINION_HOME)                     -> lists cortensor-portal and cortensor-router
python -m upgrade_scout recheck evidence/{phase2/*,phase3/compare/*}/report.json -> exit 0, 0, 3, 0
python -m upgrade_scout analyze --report evidence/phase3/compare/0.1.8-vs-0.1.15/report.json --provider openai --model gpt-4.1-mini --output-dir evidence/phase4/analysis/openai-blocked-missing-credentials   -> exit 2
python -m upgrade_scout analyze --report ... --provider echo --output-dir evidence/phase4/analysis/echo-test-only --deadline 180   -> exit 1
F1/F2/long-home reproductions (see evidence/phase4/sdk-observations/*.txt)
python -m pytest -v -rs -p no:cacheprovider                                      -> 113 passed, 2 skipped
python -m pytest -q -rs -p no:cacheprovider -m "not runtime"                     -> 109 passed, 2 skipped, 4 deselected
```
