# Submission: MinionScout (Cortensor Hackathon #5)

**Check your OpenMinion SDK upgrade with evidence.**

> **Not yet submitted, and not submission-ready.** The items marked PENDING below must be completed by a person first.
> Licensing is an open owner decision, not a stated requirement for a `LICENSE` file.

| Item | Status |
| --- | --- |
| Real model-backed analysis | **VERIFIED SUCCESS:** [`openai-attempt-5`](../evidence/phase5/analysis/openai-attempt-5/analysis.md) (OpenAI `gpt-4.1-mini`, 2026-10-29). Every automatic check passed. The human factual review accepted it, with one rationale clause rejected. |
| Clean install | **RECORDED RESULTS:** [`evidence/phase6/CLEAN_INSTALL.md`](../evidence/phase6/CLEAN_INSTALL.md) (2026-10-29): install OK; `surface` equals the retained surface; `recheck` matches; 157 passed, 2 skipped |
| Targeted live test (`tests/test_live.py::test_live_analysis_of_the_real_phase3_comparison`) | **NOT RUN.** It is another real, billed agent turn, left to the operator ([command](REFERENCE.md#running-it-live)). |
| Demo video URL (1–5 minutes) | **PENDING: not recorded.** The plan is [DEMO_SCRIPT.md](DEMO_SCRIPT.md). |
| License | **UNRESOLVED OWNER DECISION:** no license is selected, and there is no `LICENSE` file. The rules say "Use properly licensed code and data, disclose external dependencies, keep secrets and private data out of public submissions". They do not explicitly mandate a separate `LICENSE` file or a particular license. |
| External dependencies | **disclosed:** `pyproject.toml` (`openminion==0.1.15`, `pytest` for dev) and `requirements-lock.txt` (the full pinned set). External services: PyPI (for `compare`) and the OpenAI API (for `analyze`, attempt-5). |
| Public repository URL | <https://github.com/BerkPasha/minionscout> (public; created 2026-10-29). Verification of the initial push is recorded in [PROJECT_STATUS.md](../PROJECT_STATUS.md). |
| Submission (pull request) | **PENDING.** Both official pages, re-checked 2026-10-29, say to "Link your public project and submission materials in a pull request to the dedicated Hackathon #5 repository". They also say "The repository URL will be added before kickoff"; it is not listed yet. The cutoff is on [DoraHacks](https://dorahacks.io/hackathon/2418/detail). |
| "Building Blocks Tested" and "What We Learned" notes | **written:** [BUILDING_BLOCKS_TESTED.md](BUILDING_BLOCKS_TESTED.md), [WHAT_WE_LEARNED.md](WHAT_WE_LEARNED.md) |

Hackathon pages: [docs.cortensor.network](https://docs.cortensor.network/community-and-ecosystem/hackathon/hackathon-5)
and [docs-v2.cortensor.network](https://docs-v2.cortensor.network/ecosystem/hackathon-5/). The first lists a
December 18, 2026 deadline; the second says TBD.

## The developer problem

OpenMinion is moving fast. On 2026-10-29, PyPI had 0.1.15, while the API reference (generated 2026-10-19) still
described 0.1.8 as current. An agent developer facing an SDK upgrade has to answer these questions:

- Do the APIs my agent calls still exist, with the same parameters?
- Does a basic turn still run?
- Does my config still load?

Doing this by hand is slow and not repeatable. Asking a model is fast but unreliable: in our own attempt 3, a model
summary invented export changes and coverage gaps that the evidence did not contain.

## The workflow (small and repeatable)

```text
compare  two SDK versions -> report.json + per-version raw evidence   deterministic; about 30 s here with cached venvs
recheck  report.json      -> verdict recomputed from the raw evidence  offline, seconds
analyze  report.json      -> analysis.json + analysis.md               one OpenMinion agent turn; 19-21 s in attempts 4-5
```

1. **`compare`** installs each version into its own venv and runs one shared probe file in bounded processes:
   - the public exports;
   - 6 entry-point signatures;
   - an echo `Agent.run` checked against a 4-point contract;
   - the documented minimal config.

   The verdict is `compatible`, `regressions_detected` or `inconclusive`, and it is valid only within that scope.
2. **`recheck`** recomputes the verdict from the saved raw evidence, so a report can be audited.
3. **`analyze`** validates the report against its raw evidence and writes the factual report itself. It then runs
   one OpenMinion agent turn that prioritizes the evidence: which observations matter most, and which applicable next
   checks to run first, with a reason for each.

## Meaningful OpenMinion usage

- **The SDK is the subject.** Its public surface and runtime behavior are measured across releases. That is how we
  found F1 (`Agent.run` rejects the documented minimal config).
- **The SDK is the engine.** The analysis is a real OpenMinion `Agent` turn:
  - a `@tool` (`comparison_evidence`), required through `forced_tools`;
  - an `approval_callback` that allows only that tool with empty arguments (F7 explains why it is needed);
  - `output_type` (a Pydantic `ModelSelection`);
  - an isolated `OPENMINION_HOME` and config;
  - typed errors;
  - an external deadline.
- **Grounding is enforced, not requested.** The model ranks ids; the application resolves each id to its own text.
  Unknown ids, wrong categories, inapplicable checks and extra fields are rejected.
- **We learned the SDK's transport limits the hard way.** The SDK silently cuts tool-result strings at 1200
  characters (F9). We diagnosed it from three failed real runs, fixed it with a structured return and a preflight,
  verified the fix through the real SDK, and then got an accepted live run.

## Setup and run

The setup is the same as in the [README Quickstart](../README.md#quickstart): Windows 11 and Python 3.11+, verified on
3.13.5.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m upgrade_scout surface
.venv\Scripts\python -m upgrade_scout recheck evidence/phase3/compare/0.1.8-vs-0.1.15/report.json
.venv\Scripts\python -m pytest -q -p no:cacheprovider
```

- **A new comparison** (`compare --baseline 0.1.8 --candidate 0.1.15`) needs PyPI.
- **A model analysis** needs a provider key and runs one OpenMinion agent turn against a real, billed provider.
  - That turn can involve several provider requests; an offline capture of one turn recorded 8.
  - The runtime's `llm_calls` is not a request count or a billing figure.
  - See [REFERENCE.md](REFERENCE.md#running-it-live).

## Evidence

| What | Where |
| --- | --- |
| **Accepted model-backed run** (2026-10-29, OpenAI `gpt-4.1-mini`) | [`analysis.md`](../evidence/phase5/analysis/openai-attempt-5/analysis.md) |
| Its scoped approval and its one real tool execution | [`approvals.jsonl`](../evidence/phase5/analysis/openai-attempt-5/worker/approvals.jsonl), [`tool_calls.jsonl`](../evidence/phase5/analysis/openai-attempt-5/worker/tool_calls.jsonl) |
| The exact evidence it was given (grouped tool payload) | [`request.json`](../evidence/phase5/analysis/openai-attempt-5/worker/request.json) (`facts_payload`) |
| The raw model output, kept separately | [`model_output.json`](../evidence/phase5/analysis/openai-attempt-5/worker/model_output.json) |
| The comparison it analyzed (`report.json` sha256 `8b82e734…0fc93`) | [`report.md`](../evidence/phase3/compare/0.1.8-vs-0.1.15/report.md) |
| Its verification and human factual review | [PROJECT_STATUS.md](../PROJECT_STATUS.md#openai-attempt-5-success-first-accepted-model-backed-analysis-preserved-unchanged) |
| F9 diagnosis, and the fix through the real SDK (**MOCKED** provider) | [`f9-tool-result-truncation.txt`](../evidence/phase5/sdk-observations/f9-tool-result-truncation.txt), [`transport-verification/summary.txt`](../evidence/phase5/transport-verification/summary.txt) |
| Clean install: `surface`, `recheck`, the offline suite | [`evidence/phase6/`](../evidence/phase6/CLEAN_INSTALL.md) |

**The four rejected real attempts are preserved unchanged** (`openai-attempt-1` to `-4`):

1. an unhandled approval prompt;
2. a prose reply;
3. a decorated verdict and invented facts;
4. invented ids.

Attempts 2–4 also show the F9 cut. Each cause is recorded in [PROJECT_STATUS.md](../PROJECT_STATUS.md).

## Findings (details and reproductions in [WHAT_WE_LEARNED.md](WHAT_WE_LEARNED.md))

None is claimed as a confirmed SDK bug, and none has been reported upstream.

- **F9:** each string in a tool result is cut silently at 1200 characters, and each list or dict at 16 items.
- **F1:** the documented minimal config fails in `Agent.run` (`invalid_channel`), while the CLI accepts it.
- **F7:** without an `approval_callback`, the policy's confirmation prompt becomes the reply text.
- **F8:** per-run `instructions` are cut to an identity budget and are missing after a tool result.
- **F5 and F6:** `output_type` is not sent to the model, and a rejected reply loses its run identity.
- **F2 and F4:** `APIRuntime` creates `.openminion/` in the cwd, and the runtime metadata names `brain-orchestrator`,
  not the model.

## Current limitations

- **One accepted real run, of one model.** That is not a reliability measure.
- **The human review of attempt-5 rejected one clause:** "potentially impacting upgrade smoothness". Both SDK versions
  reject the minimal config (B3), so it is not an upgrade effect. Model rationales need a human reader.
- **The targeted live test has not been run.**
- **Usage figures are as the runtime reports them.** Attempt-5's `llm_calls=1` and token counts come from the runtime;
  they are not a provider request count or a bill.
- **The probe scope is narrow:** exports, 6 signatures, one echo turn and the minimal config. `compatible` holds only
  within it. Providers, memory, skills, tasks, delegation and permissions are not exercised.
- **Verified only on Windows 11 with Python 3.13.5.** The transport preflight is pinned to the 0.1.15 SDK limits.
- **Cortensor:** only the Router alias is reachable through `analyze`, and no Cortensor model run was made.
