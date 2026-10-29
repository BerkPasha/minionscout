# Reference: commands, verdicts, analysis rules

The detailed reference for MinionScout, moved out of the README so the README stays short. Paths are
relative to the repository root.

**Setup** is in the [README](../README.md#quickstart): `python -m venv .venv`, then
`.venv\Scripts\python -m pip install -e ".[dev]"`. In the synopses below, `python` means the venv's interpreter: on
Windows, write `.venv\Scripts\python` (or activate the venv first).

The workflow:

```text
compare ──> report.json + per-version raw evidence           deterministic; the verdict is authoritative
recheck ──> recompute a saved report from its raw evidence    offline
analyze ──> analysis.json + analysis.md                       OpenMinion Agent + @tool + structured output
```

Requirements:

- Python 3.11 or newer. Verified only on Python 3.13.5 on Windows 11; Linux and macOS have not been tested.
- The controller environment pins `openminion==0.1.15` (`pyproject.toml`). `compare` installs each compared version
  into its own venv and never changes the controller.
- `compare` needs network access to PyPI. `analyze` needs a model provider and its credential.
- `requirements-lock.txt` holds the exact package set of the controller environment that produced the retained
  evidence. A clean `pip install -e ".[dev]"` on 2026-10-29 resolved the same set except for a newer patch:
  `pydantic 2.14.2` and `pydantic_core 2.50.2`, against 2.14.1 and 2.50.1 in the lock. That install passed the suite
  ([CLEAN_INSTALL.md](../evidence/phase6/CLEAN_INSTALL.md)).

## 1. Deterministic comparison (`compare`)

```bash
python -m upgrade_scout compare --baseline 0.1.8 --candidate 0.1.15 --output-dir <dir>
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--baseline`, `--candidate` | required | release versions such as `0.1.8`; anything else is rejected |
| `--output-dir` | `scout-reports/<baseline>-vs-<candidate>` | reports plus per-version evidence |
| `--state-root` | `%LOCALAPPDATA%\mus` on Windows, `~/.cache/minion-upgrade-scout` elsewhere | per-version venvs and temporary work dirs |
| `--install-timeout` / `--preflight-timeout` / `--probe-timeout` | 900 / 60 / 300 | external process deadlines, in seconds |
| `--recreate-envs` | off | rebuild the per-version venvs |

### What it does

1. **One venv per version**, with only `openminion==<version>` installed. This project is never installed there.
2. **One shared probe file run against each version.** `upgrade_scout/probe.py` runs as a separate, time-bounded
   process per stage, each with its own fresh work directory, OpenMinion home, and session. Model credentials are
   removed from the probes' environment.
   - `preflight`: the installed version, Python, platform, and a loopback `socket.socketpair()` and asyncio event loop.
   - `surface`: the exports of `openminion` and `openminion.api`, plus the signatures and parameters of 6 entry
     points. A missing symbol is recorded as evidence, not raised.
   - `echo_turn`: one `Agent.run` on the echo provider, using the scout's call shape (a forced `@tool`) with
     `default_channel: console`.
   - `minimal_config`: one `Agent.run` with the documented minimal config, which has no `default_channel`.
3. **`report.json` and `report.md`**, linking each version's raw evidence in `<output-dir>/<role>-<version>/`. Home
   paths are replaced with `~`.

### Reading a report

| Verdict | Exit | Meaning |
| --- | --- | --- |
| `compatible` | 0 | Every probe completed, everything was measured in both versions, and no regression was observed. This holds **only within the Scope listed in the report**. |
| `regressions_detected` | 1 | At least one regression was observed. This verdict takes precedence over incomplete measurements. |
| invalid | 2 | Bad arguments or an unusable output directory. Nothing was compared. |
| `inconclusive` | 3 | Something was incomplete: an environment failure, a probe stage that did not finish, a **coverage gap**, or the required echo contract failing on **both** versions. The tool never reports "compatible" in that case. |

- **Regressions:**
  - a removed export, or an import root that no longer imports;
  - an entry point that no longer exists (`AttributeError` or `ImportError`);
  - a removed parameter, or a parameter that became required;
  - an echo-contract failure on the candidate when the baseline met the contract;
  - the minimal config accepted on the baseline and rejected on the candidate.
- **Coverage gaps (not regressions):** an export root or entry point that could not be measured in one or both
  versions. Examples: it is unresolved in both, it is present only in the candidate, its signature cannot be
  introspected, or the root has no `__all__`. A gap makes the comparison incomplete, so the verdict is inconclusive
  unless an independent regression exists.
- **Echo contract.** On every version, the echo turn must satisfy all four checks:
  - `completed`: Agent.run returns with `run_state` `completed`;
  - `echoed_message`: the reply contains the probe message;
  - `echo_provider`: the runtime reports provider `echo`;
  - `session_preserved`: the requested session id is kept.

  Other differences (token counts, stats keys, result fields) are telemetry, reported as `changed`, not as
  regressions.
- **Signature differences** other than removals and newly required parameters, and **added exports**, are listed for
  review. They are not breaking-change claims.
- **Environment failures** are kept apart from **unfinished stages**: a probe that times out is not attributed to the
  SDK.
- **Echo proves nothing about models.** Echo probes prove neither real inference nor model-driven tool execution.

### Re-checking a saved comparison (`recheck`)

```bash
python -m upgrade_scout recheck evidence/phase3/compare/0.1.8-vs-0.1.15/report.json --output recheck.json
```

This recomputes the verdict from the saved raw stage evidence with the current logic, offline. It prints the stored
and recomputed verdicts, and exits with the recomputed exit code (2 if the input is invalid).

`matches_stored_comparison` is `true` only when every comparison field is identical. A schema-1 (Phase 2) report
cannot match, because it lacks the fields added in schema 2.

## 2. Model analysis (`analyze`)

```bash
python -m upgrade_scout analyze --report <comparison>/report.json --provider <provider> --model <model> \
    --output-dir <analysis-dir> [--deadline 600]
```

### What it does

1. **Validates the input before anything reaches a model.**
   - The report must be the current schema.
   - Its comparison fields must match a recomputation from its own raw evidence.
   - Its `scope` and `echo_contract` must equal this tool's definitions.
   - Each version summary (requested, installed and imported versions, Python, platform, environment) must match the
     raw `preflight`, `surface` and `environment` evidence. Each stage file must have been produced by that stage's
     probe, for that version.
   - Every evidence path must be a plain file inside the comparison directory, and it is hashed.
   - The facts are then built from the recomputed comparison and the raw records, never from report text.
2. **Writes the factual report itself (analysis schema 2).** Every factual statement is generated by this
   application from the validated comparison, never by the model:
   - the authoritative verdict;
   - a summary;
   - the core results, which are always shown: export changes, signature changes, coverage gaps, regressions, echo
     tool calls, and minimal-config behavior;
   - the scope limitations;
   - the known rough edges.

   The comparison is also turned into numbered facts, each with a **category**:
   - `verdict`: V1;
   - `scope_rule`: S1–S5. These describe what the probes cover; they are **not** measured results.
   - `observation`: P\* runs, R\* regressions, X\* exports, G\* signatures, C\* coverage gaps, N\* environment
     problems, B\* echo and minimal-config behavior. Absences are explicit observations (R0 no regressions, C0 no
     coverage gaps, N0 no environment problems), so nothing has to be inferred from a scope rule.

   From the evidence, it also derives the **applicable next checks**. For example, `review_signature_changes` exists
   only if signatures changed, and `fill_coverage_gaps` only if gaps were measured.
3. **Runs one OpenMinion `Agent` turn in a child process with an external deadline.** SDK initialization can stall
   before `Agent.run(timeout_seconds=...)` applies, so the process itself is bounded.
   - The agent has one `@tool`, `comparison_evidence`. It takes no arguments and is bound to the selected report, so
     the model cannot choose files or commands.
   - **The tool returns structured data**, grouped as `verdict`, `scope_rules`, `observations` and
     `next_check_options`, not one JSON string. The installed SDK cuts each string in a tool result to 1200
     characters (F9).
     - Before any model call, a preflight checks the payload against the pinned SDK's limits: strings up to 1200
       characters, lists and dicts up to 16 items, nesting under 8 levels.
     - If it would not fit, `analyze` exits 2 with `payload_exceeds_transport_limits` and names each location. It
       never trims.
   - The tool is required through `forced_tools`.
   - **Approval.** The SDK's default policy holds the tool for confirmation: an undeclared `@tool` is scoped
     `WRITE_SAFE` with unknown reversibility, which is accurate because its audit log is a local write. An approval
     callback grants `allow_once` only to `comparison_evidence` with exactly empty arguments, and denies everything
     else. Every decision goes to `worker/approvals.jsonl`.
   - Every execution of the tool's Python body is appended to `worker/tool_calls.jsonl`, independently of what the
     runtime reports.
   - **Instructions also travel in the run message.** In an offline capture, the installed SDK cut the per-run system
     prompt to its identity budget, and left it out of post-tool requests. The user message reached every request.
   - **The model's role is bounded.** Its reply must parse as the `ModelSelection` `output_type`:
     - `key_observations`: observation ids, ranked;
     - `relevant_limitations`: scope-rule ids;
     - `next_checks`: applicable option ids, ranked, each with a rationale.

     There is no verdict, no summary, and no free-standing factual statement. The application resolves every id to
     its canonical statement. The only model-written text kept is each check's **Model rationale**, which is labelled
     as a recommendation.
4. **Accepts the model's selection only if all of these hold:**
   - the provider is not `echo`;
   - the worker process finished before the deadline and exited with code 0. A result file left by a process that
     failed, could not start, or timed out is never trusted.
   - the turn completed;
   - the tool's Python body executed at least once;
   - the reply matches `ModelSelection` exactly. Extra fields, such as a verdict or a summary, are rejected.
   - every id exists, in the right category: a scope rule cannot be a key observation, and the verdict cannot be
     cited as evidence. No id repeats.
   - every next check is one of the applicable options;
   - no rationale claims compatibility for a non-compatible verdict;
   - the runtime-reported provider, if present, matches the configured one.

   Otherwise the analysis is `failed` and `model_selection` is `null`. The factual report is still written, because
   it does not depend on the model. The raw model output is always kept separately, in `worker/model_output.json`,
   marked `accepted: true` or `false`.

   | Checked automatically | Still needs human review |
   | --- | --- |
   | the input matches the raw evidence; the verdict and every measured result are application-rendered; schema, ids, categories and applicable checks; the scoped approval and observed tool execution; worker exit 0; the source hash | whether the model's ranking is sensible for your agent; the model-written rationales, which can still mislead; whether the offered checks are enough |
5. **Writes `analysis.json` and `analysis.md`.** They record:
   - the input report hash and the evidence hashes;
   - the SDK version;
   - the configured provider and model, labelled separately from the runtime metadata (which can report
     `brain-orchestrator`);
   - the runtime identifiers;
   - the tool invocation counts, both Python-side and runtime-reported;
   - the worker's elapsed seconds;
   - the runtime-reported usage. Missing telemetry is shown as such, never as zero.
   - the failure reasons.

   `analysis.md` runs in this order:
   1. the authoritative verdict;
   2. the echo limitation;
   3. the application-written factual report;
   4. the model contribution (ranking and labelled rationales), or the reasons it was not accepted;
   5. the run identity, tool execution, approvals and usage;
   6. the automatic and human-review checks;
   7. the facts supplied to the model.

   Earlier results in
   the output directory are deleted first, so a failed run never leaves a stale success behind. The output directory
   may not be inside the comparison directory, and the source report hash is checked again at the end.

### Exit codes

- `0`: success.
- `1`: the analysis ran and failed (provider error, deadline, tool not executed, or invalid output).
- `2`: it could not start (invalid report, a payload over the SDK's tool-result limits, missing credential, or bad
  arguments).

### Running it live

Five real OpenAI attempts have run from the operator's terminal. Attempts 1–4 were rejected; attempt-5
(`evidence/phase5/analysis/openai-attempt-5/`) was accepted (see [PROJECT_STATUS.md](../PROJECT_STATUS.md)). The
example below shows the pattern; give every run its own new output directory.

**What a live run costs.** `analyze` runs **one OpenMinion agent turn**, not one provider request.

- Within that turn, the SDK may send several requests to the provider: its own classification calls, the request in
  which the model calls the evidence tool, and the answer. An offline capture of one turn with a mocked provider
  recorded 8 (`evidence/phase5/sdk-observations/f9-tool-result-truncation.txt`).
- The `llm_calls` and token figures in `analysis.json` are **as reported by the runtime**. In that capture,
  `llm_calls` was 1 for 8 requests.
- They are neither a request count nor a billing figure; the provider's own usage records are authoritative.

Use one provider you have access to. For OpenAI, the variable is `OPENAI_API_KEY`. In Windows PowerShell 5.1, set it
for the current session only, without echoing it or putting it in the command history:

```powershell
$secure = Read-Host -AsSecureString "OpenAI API key"
$env:OPENAI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
Remove-Variable secure

.venv\Scripts\python -m upgrade_scout analyze `
  --report evidence/phase3/compare/0.1.8-vs-0.1.15/report.json `
  --provider openai --model gpt-4.1-mini `
  --output-dir scout-reports/analysis-openai --deadline 600
```

**The targeted live test (not run yet).** It runs the same `analyze` workflow on the retained report as an opt-in
pytest: another real, billed agent turn, with the same caveat. Its output goes to the `--basetemp` directory, not to
`evidence/`. It checks only the automatic criteria, so its rationales need a human review. In the same session, with
the key already set:

```powershell
$env:SCOUT_LIVE_PROVIDER = "openai"; $env:SCOUT_LIVE_MODEL = "gpt-4.1-mini"
.venv\Scripts\python -m pytest "tests/test_live.py::test_live_analysis_of_the_real_phase3_comparison" -v -p no:cacheprovider --basetemp "$env:LOCALAPPDATA\mus\pt-live"
```

| Provider | Variable | Model to try |
| --- | --- | --- |
| OpenRouter | `OPENROUTER_API_KEY` | `--provider openrouter --model openai/gpt-4.1-mini` |
| Groq | `GROQ_API_KEY` | `--provider groq --model llama-3.3-70b-versatile` |

`gpt-4.1-mini` and the OpenRouter and Groq models are the documented built-in defaults; their current availability
was not verified here.

The key is only checked for presence, removed from every saved file, and never printed.

**Cortensor.** The official guide (<https://www.openminion.com/docs/examples/providers/cortensor/>) documents two
routes:

- the hosted **Portal**: preset `cortensor-portal`, OpenAI-compatible, `https://api.cortensor.app/v1`;
- the direct **Router**: preset `cortensor-router`, `http://127.0.0.1:8080/api/v2/completions`.

Both use `CORTENSOR_API_KEY`, and the installed 0.1.15 lists both presets (`openminion setup --list-providers`).
`analyze` currently writes a plain `provider:` config, so its `--provider cortensor` targets the Router alias. Using
the Portal preset through `analyze` has not been implemented or verified.

## Other commands

```bash
python -m upgrade_scout surface        # installed SDK surface (JSON)
python -m upgrade_scout run            # one scout-agent turn on echo (no model inference)
```

## Tests

```powershell
.venv\Scripts\python -m pytest -q -p no:cacheprovider                   # everything offline: 157 passed, 2 skipped
.venv\Scripts\python -m pytest -q -p no:cacheprovider -m "not runtime"  # without the 7 tests that start an asyncio runtime
```

The tests are offline. `tests/test_compare.py` and `tests/test_analysis.py` use **synthetic** comparison fixtures and
**mocked** model results; both are labelled in the files and are never presented as SDK or model evidence.
`tests/test_tool_transport.py` sends the real Phase 3 evidence through the real SDK to a **mocked** local provider.
It checks that every fact and option reaches the provider request intact, with a negative control.
`tests/test_live.py` holds two opt-in real-model tests:

- the scout agent turn;
- the full `analyze` workflow on the real Phase 3 report, which asserts:
  - worker exit 0;
  - a completed turn;
  - at least one Python-side tool execution, returning all 11 observations and 3 next-check options;
  - an unchanged verdict;
  - an unchanged source hash.

They are skipped unless `SCOUT_LIVE_PROVIDER` and the provider key are set. The analysis test also needs
`SCOUT_LIVE_MODEL`.

## Known SDK behaviour (details in [WHAT_WE_LEARNED.md](WHAT_WE_LEARNED.md))

1. **`default_channel` is required.** The documented minimal config makes `Agent.run` fail with
   `inbound authenticity denied (reason=invalid_channel, mode=warn)`. This is observed on 0.1.8 and 0.1.15.
2. **`APIRuntime` creates `.openminion/` under the working directory.**
3. **`output_type` only validates the reply.** The installed SDK does not send the schema to the model, so `analyze`
   puts the JSON schema into the instructions.
4. **`AgentOutputValidationError` carries no run identity.** It has the reply text but no `run_id` or stats.
5. **Tool results are cut before the model sees them.** Each string is cut at 1200 characters, each list or dict at
   16 items (F9). That is why the evidence tool returns grouped, structured data, and why `analyze` refuses to
   start when the payload would not fit.
6. **Tools need approval.** Under the default policy, an `@tool` without a declared scope waits for confirmation;
   without an `approval_callback`, the confirmation prompt becomes the reply text (F7).

## Layout

```text
upgrade_scout/
  agent.py            the original scout agent and its @tool
  probe.py            the one probe implementation run in every comparison venv
  compare.py          comparison controller, verdict logic, recheck, report.json / report.md
  analysis.py         analyze controller: input validation, categorized facts, factual report, ModelSelection,
                      applicable next checks, success criteria, reports
  analysis_worker.py  child process: the analysis Agent turn with the evidence @tool
  surface.py, home.py, cli.py
tests/                offline tests; test_live.py needs credentials
docs/                 submission notes, demo script, judging notes, this reference
evidence/             retained runs, by phase:
  phase2/, phase3/compare/      real comparisons (phase3/compare/0.1.8-vs-0.1.15 is the one analyzed)
  phase3/, phase4/analysis/     early analyze runs (failed or blocked; kept as history)
  phase4/sdk-observations/      F1, F2 and long-home reproductions
  phase5/analysis/              the five real OpenAI attempts; attempt-5 is the accepted one
  phase5/sdk-observations/      F9 diagnosis
  phase5/transport-verification/  the F9 fix through the real SDK, with a MOCKED provider
  phase6/                       clean-install reproducibility check
```
