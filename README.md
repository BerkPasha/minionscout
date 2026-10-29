# MinionScout

**Check your OpenMinion SDK upgrade with evidence.**

MinionScout compares two OpenMinion SDK releases with a deterministic, re-checkable probe suite. Then one OpenMinion
agent turn prioritizes that evidence for the developer, under rules that keep every fact application-written.

Built for Cortensor Hackathon #5 on the [OpenMinion](https://www.openminion.com/docs) 0.1 Python SDK (controller
pinned to `openminion==0.1.15`).

The code keeps its original names: the Python distribution `minion-upgrade-scout`, the module and CLI
`python -m upgrade_scout`, and the agent persona text. Historical records call the project "Minion Upgrade Scout".

> **Status (2026-10-29): the MVP is complete. The submission is not complete yet.**
>
> | Item | State |
> | --- | --- |
> | Real model-backed analysis | **verified success:** [`openai-attempt-5`](evidence/phase5/analysis/openai-attempt-5/analysis.md) (OpenAI `gpt-4.1-mini`, 2026-10-29), with one rationale clause rejected in human review |
> | Clean install | **recorded results:** [`evidence/phase6/CLEAN_INSTALL.md`](evidence/phase6/CLEAN_INSTALL.md) (157 passed, 2 skipped) |
> | Targeted live test (`tests/test_live.py`) | **not run** |
> | Demo video | **not recorded** |
> | Public repository | <https://github.com/BerkPasha/minionscout> (public; created 2026-10-29). Verification of the initial push is recorded in [PROJECT_STATUS.md](PROJECT_STATUS.md). |
> | License | **unresolved owner decision.** No license is selected. The hackathon rules ask for "properly licensed code and data", but do not mandate a `LICENSE` file or a particular license. |
>
> Details: [docs/SUBMISSION.md](docs/SUBMISSION.md).

## Quickstart

Windows PowerShell and Python 3.11+. This is verified on Windows 11 with Python 3.13.5; on macOS or Linux (untested),
use `.venv/bin/python`.

```powershell
git clone https://github.com/BerkPasha/minionscout.git
cd minionscout
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"

.venv\Scripts\python -m upgrade_scout surface        # the installed SDK's public surface, as JSON
.venv\Scripts\python -m upgrade_scout recheck evidence/phase3/compare/0.1.8-vs-0.1.15/report.json
                                                     # offline: "matches_stored_comparison": true, exit 0
.venv\Scripts\python -m pytest -q -p no:cacheprovider   # offline: 157 passed, 2 skipped (the opt-in live tests)
```

These steps were re-run in a fresh copy at a short path, where pytest used a short `--basetemp`. The commands and
results are in [`evidence/phase6/`](evidence/phase6/CLEAN_INSTALL.md).

**A new comparison** needs PyPI access. It creates one venv per version under `%LOCALAPPDATA%\mus`; the output goes
to `scout-reports/`, which is gitignored.

```powershell
.venv\Scripts\python -m upgrade_scout compare --baseline 0.1.8 --candidate 0.1.15
```

**A model analysis** runs one OpenMinion agent turn against a real, billed provider.

- One turn can involve several provider requests: the SDK's own classification calls, the tool call and the answer.
  An offline capture of one turn with a mocked provider recorded 8.
- The runtime's `llm_calls` statistic is not a request count or a billing figure; check the provider's usage
  dashboard for cost.

Set the provider key in the session first, without echoing it ([how](docs/REFERENCE.md#running-it-live)). This
command analyzes the same retained report as attempt-5:

```powershell
.venv\Scripts\python -m upgrade_scout analyze --report evidence/phase3/compare/0.1.8-vs-0.1.15/report.json `
  --provider openai --model gpt-4.1-mini --output-dir scout-reports/analysis-openai --deadline 600
```

## Working example (retained evidence, 2026-10-29)

| Step | What happened | Evidence |
| --- | --- | --- |
| `compare 0.1.8 -> 0.1.15` | **`compatible` (exit 0), within the stated probe scope only**:<br>- no export changes (12 -> 12, 15 -> 15);<br>- 6 of 6 entry-point signatures identical;<br>- no coverage gaps;<br>- echo contract met on both versions;<br>- the documented minimal config rejected on both (`invalid_channel`, F1). | [`report.md`](evidence/phase3/compare/0.1.8-vs-0.1.15/report.md) (`report.json` sha256 `8b82e734…0fc93`) |
| `recheck` | the verdict recomputed from the raw per-version evidence matches the stored one | [`clean-recheck.json`](evidence/phase6/clean-recheck.json) |
| `analyze`, OpenAI `gpt-4.1-mini` | **success**:<br>- one scoped `allow_once`;<br>- **one real execution** of the evidence `@tool`, returning 1 verdict, 5 scope rules, 11 observations and 3 next-check options;<br>- the model ranked R0, B1, G1, C0, X1 and X2;<br>- its checks, in order: validate with a real provider, test the uncovered building blocks, set `default_channel`. | [`analysis.md`](evidence/phase5/analysis/openai-attempt-5/analysis.md), [`tool_calls.jsonl`](evidence/phase5/analysis/openai-attempt-5/worker/tool_calls.jsonl), [`approvals.jsonl`](evidence/phase5/analysis/openai-attempt-5/worker/approvals.jsonl) |
| human review | the automatic checks passed. **One rationale clause is rejected**: "potentially impacting upgrade smoothness" implies an upgrade-specific effect, but both SDK versions reject the minimal config (B3). | [PROJECT_STATUS.md](PROJECT_STATUS.md#openai-attempt-5-success-first-accepted-model-backed-analysis-preserved-unchanged) |

## How it uses OpenMinion

- **The subject.** Each SDK version is installed into its own venv and probed through its public API:
  - the exports of `openminion` and `openminion.api`;
  - the signatures of 6 entry points (`Agent`, `Agent.run`, `Agent.run_stream`, `tool`,
    `APIRuntime.from_config_path`, `APIRuntime.run_turn`);
  - an echo `Agent.run` with a forced `@tool`;
  - the documented minimal config.
- **The engine.** An OpenMinion `Agent` runs one turn:
  - with a no-argument `@tool` (`comparison_evidence`), required through `forced_tools`;
  - `Agent.run(timeout_seconds=..., approval_callback=...)`, with a callback that allows only that tool with empty
    arguments;
  - `output_type=ModelSelection` (Pydantic);
  - an isolated `OPENMINION_HOME` and config;
  - typed errors (`ProviderError`, `AgentOutputValidationError`);
  - an external process deadline.
- **The model's job is bounded.** It ranks observation ids, picks scope-rule ids, and ranks next checks chosen from
  options the application derived as applicable, each with a labelled rationale.
  - The application writes the verdict and every fact.
  - Unknown ids, wrong categories, inapplicable checks and extra fields are rejected.

## What the verdict means, and what it doesn't

- **`compatible` covers only the probes above.** Providers, network, memory, skills, tasks, delegation and permissions
  are not exercised.
- **Echo makes no model call,** so the comparison proves neither real inference nor model-driven tool execution. The
  analysis step is where a real model and real tool execution are observed.
- **A coverage gap** (something unmeasurable in a version) makes the verdict `inconclusive`, never `compatible`.

## Findings about OpenMinion (details in [docs/WHAT_WE_LEARNED.md](docs/WHAT_WE_LEARNED.md))

- **F9: tool results are cut silently.** Each string is cut at 1200 characters, each list or dict at 16 items.
  - Our evidence tool returned one 4294-character string, so in three real runs the model never saw the observations.
  - **The workaround:** a grouped, structured return plus a preflight that refuses oversized payloads. It is
    verified through the real SDK with a mocked provider
    ([20 of 20 items vs 5 of 20](evidence/phase5/transport-verification/summary.txt)), then accepted live in
    attempt-5.
- **F1: the documented minimal config fails in `Agent.run`** (`invalid_channel`), while the CLI accepts it. Set
  `default_channel`.
- **F7: without an `approval_callback`,** the default policy's confirmation prompt comes back as the reply text.
- **F8: per-run `instructions` are cut to an identity budget,** and are missing after a tool result. The tool repeats
  them in the run message.
- **F5 and F6:** `output_type` is not sent to the model, and a rejected reply loses its run identity.

## Limitations

- **One accepted real run, of one model** (`gpt-4.1-mini`). That is not a reliability measure. The model-written
  rationales still need a human reader.
- **The targeted live test has not been run.** Its command is in
  [docs/REFERENCE.md](docs/REFERENCE.md#running-it-live).
- **Verified only on Windows 11 with Python 3.13.5.**
- **The transport preflight is pinned to the 0.1.15 SDK limits.** A comparison with more than 16 observations (for
  example, many regressions) is refused rather than cut.
- **Cortensor:** `analyze --provider cortensor` targets the Router alias. The Portal preset is not wired in, and no
  Cortensor model run was made.

## Documentation

| File | For |
| --- | --- |
| [docs/SUBMISSION.md](docs/SUBMISSION.md) | the hackathon submission summary and pending items |
| [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) | the 1–5 minute demo plan |
| [docs/BUILDING_BLOCKS_TESTED.md](docs/BUILDING_BLOCKS_TESTED.md) | each OpenMinion building block: what worked, what did not, with evidence |
| [docs/WHAT_WE_LEARNED.md](docs/WHAT_WE_LEARNED.md) | the SDK findings (F1–F9), with reproductions, and this project's own defects |
| [docs/REFERENCE.md](docs/REFERENCE.md) | the full command reference, verdict rules, analysis acceptance rules and layout |
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | the development history, every attempt (including the 4 rejected ones) and the reviews |

## License

No license has been selected; this is an open owner decision, and there is no `LICENSE` file. The published Hackathon
#5 rules say "Use properly licensed code and data, disclose external dependencies, keep secrets and private data out of
public submissions". They do not require a separate `LICENSE` file or name a license. The external dependencies are
declared in `pyproject.toml` and pinned in `requirements-lock.txt`.
