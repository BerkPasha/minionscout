# What We Learned

These are findings from building MinionScout on OpenMinion 0.1.8 and 0.1.15.

- **Environment for every finding**, unless a finding says otherwise: Windows 11 (10.0.26200), Python 3.13.5, and
  `LongPathsEnabled=0`.
- **Reproduction commands** run from the repository root, in its `.venv`.
- **Upstream reports:** none has been filed.
- **What "candidate" means:** it marks something we observed but that the maintainers have not confirmed as a bug.

The findings fall into four groups:

1. Runtime findings: observed by running code.
2. Source-inspection observations: read in the installed package, not executed as a defect.
3. Application defects: bugs in *this* project, found and fixed.
4. Unanswered questions.

---

## 1. Verified runtime findings

### F1 (candidate): the documented minimal config makes `Agent.run` fail, while the CLI accepts it

- **Affects:** openminion 0.1.8 and 0.1.15.
- **Reproduce** with either of:
  - `python -m upgrade_scout compare --baseline 0.1.8 --candidate 0.1.15 --output-dir <dir>`, then look at
    `minimal_config.json`;
  - the steps in `evidence/phase4/sdk-observations/f1-cli-vs-sdk-minimal-config.txt`.
- **Config:** the Configuration page's "smallest useful config",
  `{"default_agent": "default", "agents": {"default": {"name": "default", "provider": "echo"}}}`.
- **Expected:** the page says OpenMinion fills in runtime, gateway and storage defaults around this shape, so an echo
  turn should complete.
- **Actual:**
  - `openminion run "hello cli"` succeeds and prints `default: hello cli (thinking=minimal)`.
  - `Agent().run(...)` raises a bare
    `RuntimeError: inbound authenticity denied (reason=invalid_channel, mode=warn)`, which is not one of the
    documented SDK exceptions.
  - Reading the 0.1.15 source shows why: `Agent` sends no channel, an agent's `default_channel` defaults to `""`, and
    the authenticity check rejects an empty channel in every mode.
- **Workaround:** add `"default_channel": "console"` to the agent; the scout does this.
- **Evidence:**
  - `evidence/phase4/sdk-observations/f1-cli-vs-sdk-minimal-config.txt`;
  - `evidence/phase3/compare/0.1.8-vs-0.1.15/baseline-0.1.8/minimal_config.json`, and the same file for the candidate.
- **Suggestion:** do one of these:
  - have `Agent` default the channel the way the CLI does;
  - add `default_channel` to the documented minimal config;
  - raise a typed SDK error that names the missing setting.

  Which one is intended is for the maintainers.

### F2 (observation): starting `APIRuntime` creates `.openminion/browser-playwright/...` under the working directory

- **Affects:** openminion 0.1.15.
- **Reproduce:** with `OPENMINION_HOME` and `OPENMINION_DATA_ROOT` set elsewhere, run this in an empty directory:

  ```bash
  python -c "from openminion import APIRuntime; APIRuntime.from_config_path(None).close()"
  ```

- **Expected:** if all state belongs under the configured home, the cwd stays clean.
- **Actual:** an empty `./.openminion/browser-playwright/{artifacts/{pdf,screenshots,traces},downloads}` tree appears
  in the cwd: 7 directories, no files. In a Phase 1 manual check, which has no retained file, importing openminion or
  constructing an `Agent` created none.
- **Workaround:** run from a scratch cwd, and gitignore `.openminion/`.
- **Evidence:** `evidence/phase4/sdk-observations/f2-runtime-creates-cwd-dirs.txt`.
- **Suggestion:** document the workspace-relative directories, or create them lazily under the data root.
  `DEFAULT_PLAYWRIGHT_WORKSPACE_*_SUBPATH` in `tools/browser/providers/playwright/constants.py` suggests this may be
  deliberate.

### F3 (observation): on echo, `forced_tools` does not lead to a tool call

- **Affects:** 0.1.8 and 0.1.15.
- **Observed:** with a `@tool` listed in `forced_tools`, the echo turn completes with `tool_calls=0`, and the tool's
  Python body never runs.
- **Evidence:** the Echo turn observations in `evidence/phase3/compare/0.1.8-vs-0.1.15/report.md`.
- **Is this a bug?** No. It matches the docs' statement that echo does not prove tool use.
- **Phase 5, real model.** With OpenAI `gpt-4.1-mini` and an approval callback, the forced tool's Python body
  executed once each in attempts 2–5 (`evidence/phase5/analysis/openai-attempt-{2,3,4,5}/worker/tool_calls.jsonl`).
- **Still open:** whether a turn that ends without its `forced_tools` should say so in the result. No real run ended
  that way.

### F4 (observation): `AgentRunResult.metadata["model"]` is `"brain-orchestrator"`, with echo and with a real OpenAI model

- **Evidence:**
  - echo: `evidence/echo-run.json` (`runtime_model`);
  - real OpenAI `gpt-4.1-mini`: `evidence/phase5/analysis/openai-attempt-3/analysis.json`
    (`runtime.metadata_model`). In the same run, `metadata_provider` is `openai`.
- **Effect on the tool:** we label configured model identity separately from runtime metadata in every record.
- **Suggestion:** expose the provider's model id in the result metadata.

## 1b. Phase 5 live integration findings (real OpenAI `gpt-4.1-mini`, openminion 0.1.15, Windows 11)

These are integration findings. None is claimed as an SDK defect.

### F7: without an `approval_callback`, the default policy's confirmation request becomes the turn's reply text

- **Reproduce:** run `analyze` with the pre-fix worker. Evidence:
  `evidence/phase5/analysis/openai-attempt-1/worker/result.json` (`raw_text`).
- **Observed:**
  - the reply was "Policy confirmation required. comparison_evidence. Risk: write. Side effects: local.
    Reversibility: unknown. Reason: UNKNOWN_REVERSIBILITY. Choices: allow_once, allow_session, deny ...";
  - the tool did not run;
  - with `output_type` set, that prompt surfaced as `AgentOutputValidationError`.
- **Source:**
  - `@tool` without `min_scope` defaults to `WRITE_SAFE` (`tools/decorator.py`);
  - the policy confirms non-read tools with unknown reversibility (`modules/policy/runtime/service.py`);
  - with a callback, the runner asks it, and `True` grants once before the policy is re-evaluated
    (`modules/brain/runner/delegates.py`).
- **Expected vs actual:** a programmatic `Agent.run` caller might expect either a typed approval error or the tool to
  run. It received the confirmation prompt as ordinary reply text.
- **Workaround:** a narrow `approval_callback`, `make_approval_callback` in `upgrade_scout/analysis_worker.py`. It
  allows only the bound tool with empty arguments, and records each decision in `worker/approvals.jsonl`.
- **Suggestion:** in SDK mode, raise a typed "approval required" error, or document that `@tool` functions need an
  `approval_callback` or an explicit read scope to run under the default policy.

### F8: per-run `Agent.instructions` are cut to the identity budget and missing after a tool result

- **Observed in an offline capture.** A local fake OpenAI endpoint drove the real SDK and worker; see
  `tests/test_instruction_capture.py` and the attempt-2 entry in PROJECT_STATUS.md.
  - Only 880 of 2704 instruction characters reached the system prompt, ending in `...[truncated]` and followed by the
    SDK's persona wrapper.
  - The requests made after the tool result carried no analysis instructions.
  - The run's user message reached every request.
- **Source:** `_fit_to_budget` (`modules/context/pack/budgeting.py`), applied in `modules/context/pack/identity.py`.
  - The suspected `_follow_up_after_tool` path has no callers in 0.1.15.
  - Moving the instructions to the profile `system_prompt` did not change the captured requests.
- **Real-run link (inferred, not proven):** attempt 2's real reply was prose rather than JSON. After the instructions
  were repeated in the run message, attempt 3's real reply was schema-valid JSON.
- **Suggestion:** document the identity budget for `instructions`, or route per-run instructions outside the persona
  budget, and keep them on post-tool requests.

### F9: each string in a tool result reaches the model truncated to 1200 characters

- **Affects:** openminion 0.1.15, observed. The same constants and function are in the installed 0.1.8, by source
  inspection only.
- **Source:** `action_result_to_tool_message` (`modules/brain/loop/tools/messages.py`) compacts a tool's outputs
  before they become the tool message. `modules/brain/constants.py` sets:
  - `TOOL_MESSAGE_STRING_LIMIT = 1200`: each string is cut there and gets `...[truncated]`;
  - `TOOL_MESSAGE_SEQUENCE_LIMIT = 16`: a list keeps 16 items, a dict 16 keys;
  - `TOOL_MESSAGE_DEPTH_LIMIT = 8`.

  The tool's Python body still returns the full value, and nothing tells the caller that the model saw less.
- **Reproduce (offline, mocked endpoint):**

  ```bash
  python evidence/phase5/sdk-observations/f9_capture_tool_result.py <repo> <out_dir>
  ```

  It replays `openai-attempt-4`'s real request through the real worker and installed SDK against a local fake OpenAI
  endpoint, and records every provider request. Output: `evidence/phase5/sdk-observations/f9-tool-result-truncation.txt`.
- **Observed:**
  - `comparison_evidence` returned a 4294-character JSON string;
  - the post-tool request's tool message was 1362 characters and ended `...[truncated]` right after S4's statement,
    whose last character is character 1200;
  - S5, every observation (P, R, X, G, C, N, B) and `next_check_options` were missing.
- **Effect on the real runs (consistent with the cut; the live request bodies were not captured):**
  - **Attempt-4:** the model used only S1–S4 among the real ids, and invented O1–O3 and C1–C3 for what it could not
    see. Rejected (`selection_invalid`).
  - **Attempt-3:** it cited only V1 and S1–S4.
  - In attempts 2 and 3, the cut fell inside S4's statement.
- **Expected vs actual:** a tool author might expect either the full result or a visible error. The model received a
  silently shortened result.
- **Workaround (implemented; verified offline with a MOCKED provider; attempt-5 succeeded live with it):**
  - The tool returns a dict that the compactor leaves alone: grouped lists of `{id, statement}`, each string under
    1200 characters and each list under 16 items. It includes its own short `summary`, because otherwise the SDK
    derives a 600-character cut copy of the payload as the summary.
  - Through the real SDK, all 20 facts and options reach the post-tool provider request intact. Returning
    attempt-4's exact string as a negative control delivers 5 of 20.
  - `analyze` refuses to start when a payload exceeds the pinned limits.
  - Evidence: `evidence/phase5/transport-verification/summary.txt`; tests: `tests/test_tool_transport.py`.
  - **Live, attempt-5 (indirect; the live request was not captured):** the model used ids the cut had hidden in
    attempt-4 (S5, R0, X1, X2, G1, C0, B1, B2, B3) and all 3 option ids, and its selection was accepted.
- **A side effect:** for a dict result, the SDK's completion-judgment request keeps only `{tool_name, ok, verified}`
  (`_closure_tool_result_snapshot` keeps a fixed set of keys). For a string result it carried a cut copy. Attempt-5
  completed regardless; beyond that run, the effect is not studied.
- **Suggestion:** document the limits for `@tool` authors, and report truncation in the run result (for example, a
  count in `stats`).
- **Not claimed as an SDK defect:** the limits look like deliberate context budgeting.

### Citation validity is not factual accuracy (attempt 3)

- **Observed:** the rejected attempt-3 brief cited only supplied fact ids. Yet it stated that "added exports and
  signature differences" exist (the facts show none), implied coverage gaps exist (there are none), and said the
  upgrade "proves compatibility" without scope.
- **Cause, corrected after attempt-4:** we first concluded that the model treated scope-rule facts (S3, S4) as
  observations. F9 shows it never received any observation: only V1 and S1–S3 in full, and S4 in part, survived the
  tool-result cut.
  Paraphrasing S3 and S4 was all it could do.
- **Lesson:** the brief needs both machine checks and a statement-by-statement human review. A test of the model
  path must also check what actually reaches the model, using a realistic payload.

### Worked as documented

- **An unreachable Cortensor router** raises `ProviderError`, with `code=PROVIDER_ERROR` and the underlying
  connection error, in about 10 s. Evidence: `evidence/cortensor-run-attempt.json` and
  `evidence/phase3/analysis/cortensor-blocked-attempt/analysis.json`.
- **A non-JSON reply** with `output_type` raises `AgentOutputValidationError`, and `raw_text` keeps the reply.
  Evidence: `evidence/phase4/analysis/echo-test-only/worker/result.json`.
- **An undecorated tool** is rejected with `TypeError` at `Agent` construction.
- **The public facade did not change from 0.1.8 to 0.1.15**: 27 exports and 6 entry-point signatures, including every
  parameter. Evidence: `evidence/phase3/compare/0.1.8-vs-0.1.15/report.md`.

### Environment observations (not SDK defects)

- **Deep venv paths.** The deepest file in the openminion package is 131 characters below `site-packages`. A venv
  whose site-packages path was about 175 characters failed to install with `WinError 206`.
  - That log was not retained. The `compare` path checks are in each `environment.json`.
  - **Suggestion:** shorter package paths. The deepest is
    `modules/controlplane/channels/telegram/storage/migrations/versions/...`.
- **Deep `OPENMINION_HOME`.** After an SDK runtime start in a deep home, `openminion run` exited 2 with
  `SQLite online backup failed ... policy.db: unable to open database file`. The same steps under a short home
  succeeded.
  - The longest existing file in the deep home was 255 characters, so path length is the likely cause. Which file the
    backup tried to create is not verified.
  - Evidence: `evidence/phase4/sdk-observations/env-long-home-sqlite-backup.txt`.
  - **Suggestion:** include the target path, and a long-path hint, in the error.
- **Reviewer's machine.** There, `socket.socketpair()` stalled, and so did asyncio startup. The cause is unknown, and
  it is not attributed to OpenMinion. On that machine, `compare` reports a preflight environment failure.

## 2. Source-inspection observations (installed 0.1.15, read rather than run as a defect)

### F5: `output_type` validates the reply after the turn; the schema is not sent to the model

- **Where:** `openminion/api/agent.py`. `_build_payload` builds the payload with no schema field. After the turn,
  `_coerce_output` validates the reply text with `model_validate_json`; if that fails, it retries with the first
  balanced JSON object found in the text.
- **Effect:** the caller must put the schema in the instructions; `analyze` does this.
- **Suggestion:** state this in the structured-output docs, or optionally pass the schema to providers that support
  structured output.

### F6: `AgentOutputValidationError` carries `raw_text` and `validation_error`, but no run identity or stats

- **Where:** `openminion/api/agent.py`, `class AgentOutputValidationError`.
- **Runtime corroboration:** in `evidence/phase4/analysis/echo-test-only/analysis.json`, the run identity is `null`,
  and usage is "missing telemetry, not zero usage".
- **Suggestion:** attach `run_id`, `session_id` and `stats` to the exception, so a rejected reply can still be traced
  and costed.

### Cortensor routes exist in the installed SDK, and the docs do not give a version

- **The guide.** <https://www.openminion.com/docs/examples/providers/cortensor/> documents two routes, both using
  `CORTENSOR_API_KEY`:
  - **Hosted Portal:** preset `cortensor-portal`, OpenAI-compatible, `https://api.cortensor.app/v1`, model `oss-20b`.
  - **Direct Router:** preset `cortensor-router`, at `http://127.0.0.1:8080/api/v2/completions`, model
    `gpt-oss-20b`.

  The page names 0.1.8 as the current preview but does not say which version introduced the presets.
- **Installed support.** Both presets are present in the installed **0.1.8 and 0.1.15**:
  - `modules/llm/setup_catalog.py`;
  - `_PRESET_ALIASES = {"cortensor": "cortensor-router"}`;
  - `openminion setup --list-providers` lists both.
  - `cli/commands/setup.py` labels Portal support "experimental hosted text, streaming, and native tool calls; ...
    requests do not automatically retry".

  A review note reported finding no such preset strings. Our search of the three installed environments found them;
  the search commands are in PROJECT_STATUS.md.
- **What we have not verified:** whether `analyze`'s plain `provider:` config can use the Portal preset (the preset is
  applied through `openminion setup`), or a working Portal credential. Documentation availability, installed support,
  and credential availability are separate questions. Only the first two are answered.

### Documentation version lag

- The API reference and quickstart (generated 2026-10-19) describe 0.1.8 as current. PyPI had 0.1.15 on 2026-10-29.
- **Suggestion:** stamp each docs page with the release it was generated from.

## 3. Application defects (this project; found, fixed, regression-tested)

| Phase | Defect | Fix | Regression test |
| --- | --- | --- | --- |
| 2 | A relative `--output-dir` was resolved against the worker's cwd | the controller passes absolute paths | `tests/test_workers.py::test_run_stage_accepts_a_relative_evidence_dir` |
| 2 | A transient `PermissionError [WinError 5]` on `os.replace` in a OneDrive folder | retry with backoff | `tests/test_probe.py::test_write_text_atomic_*` |
| 3 | A symbol unmeasured in both versions still counted as "complete / compatible" | coverage gaps make the verdict inconclusive | `tests/test_compare.py::test_entry_point_unresolved_in_both_versions_*` |
| 3 | An echo reply missing the message was only "changed" | a 4-check echo contract; a failure is a regression | `tests/test_compare.py::test_completed_echo_reply_without_the_message_breaks_the_contract` |
| 3 | The worker request file was path-redacted before the worker read it | the worker gets an unredacted temp copy | `tests/test_analysis.py::test_a_mocked_successful_worker_*` |
| 4 | `validate_inputs` accepted a false `installed_version` and a false scope line, and presented them as facts | declarations are checked against definitions; version summaries against raw evidence; facts are built from recomputed data | `tests/test_analysis.py::test_a_false_installed_version_*`, `::test_a_false_scope_statement_*` |
| 4 | `judge` accepted a brief from a worker process that exited 7 | require `status == "ok"` and exit code 0 | `tests/test_analysis.py::test_a_failed_worker_process_is_never_accepted_*` |
| 5 | No `approval_callback`, so the tool waited for a confirmation nobody could give (attempt 1) | a narrow callback, `allow_once` only for the bound tool with empty arguments | `tests/test_analysis.py::test_approval_*`, `::test_worker_routes_sdk_confirmations_through_the_callback` |
| 5 | Instructions sent only as `Agent.instructions`, which were truncated and missing after the tool (attempt 2) | the full instructions are repeated in the run message | `tests/test_instruction_capture.py` (with a negative control) |
| 5 | The model wrote the verdict and the factual statements (contract v1). In attempt 3 the verdict was decorated, invented changes and gaps were stated, and only known ids were cited | **analysis contract v2**: the application renders the verdict and every factual statement; the model only ranks categorized ids from applicable options and adds labelled rationales. **Verified offline. Its first live run (attempt-4) rejected the model's invented ids, as designed. Attempt-5, after the transport fix, was accepted; its human review rejected one rationale clause.** | `tests/test_factual_report.py` (including the real attempt-3 output with only its verdict corrected, now rejected) |

| 5 | `comparison_evidence` returned its 4294-character payload as one string, which the SDK cut to 1200 characters (F9); the model never saw the observations or the next-check options (attempts 2–4). The capture test used a one-fact payload, so it could not catch this. | structured, grouped return within the SDK's string, list and depth limits; a preflight that refuses to start when a payload would not fit, naming each location. **Verified offline with a MOCKED provider; attempt-5 succeeded live with it.** | `tests/test_tool_transport.py` (the real 17-fact payload through the real SDK, plus a negative control with attempt-4's exact string) |

All of these were shown with synthetic fixtures, mocked models, or real runs of this tool. They are not SDK findings.

## 4. Unanswered questions

1. Can a real model produce a selection that passes every check *and* a factual review?
   - **Answered once, for `gpt-4.1-mini`, in attempt-5.** With the full evidence, its selection passed every
     automatic check.
   - The human review accepted it, but **rejected one clause**: "potentially impacting upgrade smoothness" for
     `set_default_channel`. B3 shows the minimal-config rejection is unchanged from 0.1.8, so it is not an upgrade
     effect.
   - **Lesson:** structural acceptance does not establish factual correctness. Rationales still need a human
     reader.
   - One run of one model is not a measure of reliability; other models and repeated runs are untested.
2. **Answered for OpenAI in attempts 3, 4 and 5:** `metadata["provider"]` is `openai`, `metadata["model"]` is
   `brain-orchestrator`, and `stats["tool_calls"]` is 1. That matches the Python-side count. Other providers are
   untested. `stats["llm_calls"]` is not a provider request count: an offline replay reported 1 for 8 captured
   requests.
3. Should a turn that ends without its `forced_tools` say so in the result?
4. Is the cwd-relative `.openminion/` (F2) intended?
5. Which release introduced the Cortensor presets, and does an `agents.json` `provider: cortensor-portal` work
   without `openminion setup`?
