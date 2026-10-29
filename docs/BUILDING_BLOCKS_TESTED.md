# Building Blocks Tested

This note covers MinionScout on OpenMinion 0.1.8 and 0.1.15, run on Windows 11 with Python 3.13.5.

Every row is based on retained evidence in this repository. "Not tested" means exactly that.

> **Live status (Phase 5).** Five real OpenAI `gpt-4.1-mini` `analyze` attempts ran
> (`evidence/phase5/analysis/openai-attempt-{1,2,3,4,5}/`).
>
> - **Attempt-5 was accepted.** It is the first model-backed analysis:
>   - the evidence tool executed once, after one scoped approval;
>   - the model's selection passed every automatic check;
>   - a human factual review accepted it, rejecting one clause of one rationale (see PROJECT_STATUS.md).
> - Attempts 1–4 were rejected. In attempts 2–4, the SDK cut the tool result to 1200 characters (F9), so the model saw
>   no observations. The tool now returns structured data within the SDK's limits.
> - The targeted live pytest has not been run yet.
>
> *Historical: before Phase 5, no real model had run, because no credential was available.*

## Summary

| Building block | What we used | Worked | Did not work, or not shown yet | Evidence |
| --- | --- | --- | --- | --- |
| Agent execution | `Agent(...)` as a context manager, and `Agent.run(message, timeout_seconds=)` | an echo-provider turn completed on 0.1.8 and 0.1.15, with `run_state=completed` | the documented minimal config fails (F1 in WHAT_WE_LEARNED) | `evidence/phase3/compare/0.1.8-vs-0.1.15/*/echo_turn.json` and `minimal_config.json` |
| Tools | `@tool`, `tools=[...]`, `forced_tools=[...]` | tools register; an undecorated callable is rejected with `TypeError` at construction. **With real `gpt-4.1-mini`, the forced `comparison_evidence` Python body executed once** each in attempts 2–5. Attempt-5's structured return held 1 verdict, 5 scope rules, 11 observations and 3 options, and the runtime reported `tool_calls=1` in attempts 3–5. | on echo, `tool_calls=0` even with `forced_tools`. **In attempts 2–4 the tool result reached the model cut to 1200 characters (F9)**, so only V1 and S1–S4 arrived. Since the structured return, the full evidence arrives: verified offline with a MOCKED provider (20 of 20 items intact), and consistent with attempt-5. | `evidence/phase5/analysis/openai-attempt-{2,3,4,5}/worker/tool_calls.jsonl`; `evidence/phase5/sdk-observations/f9-tool-result-truncation.txt`; `evidence/phase5/transport-verification/summary.txt`; `evidence/phase3/compare/0.1.8-vs-0.1.15/*/echo_turn.json` |
| Permissions and tool approval | the default action policy; `Agent.run(approval_callback=...)` | after the callback was added, the runtime asked it, and an `allow_once` for the exact call let the tool run (attempts 2–5; one approval each) | without a callback (attempt 1), the confirmation prompt "Policy confirmation required … UNKNOWN_REVERSIBILITY" came back **as the reply text** | `evidence/phase5/analysis/openai-attempt-1/worker/result.json`; `.../openai-attempt-{2,3,4,5}/worker/approvals.jsonl` |
| Structured output | `output_type=UpgradeBrief` (Pydantic, contract v1, attempts 1–3); now `output_type=ModelSelection` (contract v2, attempts 4 and 5) | the SDK raised `AgentOutputValidationError` on non-JSON replies (echo; attempts 1 and 2). **Real replies passed SDK validation** in attempts 3, 4 and 5. **Attempt-5's selection also passed every check of this tool and was accepted.** | attempt 3 failed this tool's verdict lock and contains factual errors; attempt 4 used ids that do not exist; both followed from F9. The schema is not sent to the model (F5); a rejected reply loses run identity (F6). | `worker/result.json` and `worker/model_output.json` in attempts 3–5 |
| Models and providers | echo; `cortensor` (router alias); `openai` | echo works; an unreachable Cortensor router raises `ProviderError` (`PROVIDER_ERROR`). **Real OpenAI turns completed**, as reported by the runtime: attempt 3 with 6223 input and 662 output tokens; attempt 4 with 8578 and 355; attempt 5 with 10107 and 560, accepted. | the runtime metadata reports `model=brain-orchestrator`, not the configured model id. Only OpenAI `gpt-4.1-mini` was run live; Cortensor was not. | `analysis.json` in attempts 3–5; `evidence/cortensor-run-attempt.json` |
| Context and system prompt | `Agent(instructions=...)` | in an offline request capture, the instructions reached the provider | cut to the identity budget (880 of 2704 characters), and absent from the requests after the tool result. The run message reached every request. | `tests/test_instruction_capture.py`; PROJECT_STATUS.md (attempt-2) |
| Sessions | `session_id=` on `Agent` | the requested session id is preserved in `AgentRunResult` on both versions; this is part of the echo contract | multi-turn memory is not tested | `evidence/phase3/compare/0.1.8-vs-0.1.15/report.md` (Echo contract table) |
| Permissions and channel authenticity | the default inbound authenticity policy, without our own config | with `default_channel: console`, turns pass | with no channel, turns are denied even in `mode=warn` (F1) | `evidence/phase4/sdk-observations/f1-cli-vs-sdk-minimal-config.txt` |
| Configuration and isolation | `OPENMINION_HOME`, `OPENMINION_DATA_ROOT`, `config_path=` | all state stayed out of `~/.openminion`, which was never created | `APIRuntime` still creates `.openminion/` under the cwd (F2) | `evidence/phase4/sdk-observations/f2-runtime-creates-cwd-dirs.txt` |
| Diagnostics and errors | `ProviderError` (`code`, `message`), `AgentOutputValidationError` (`raw_text`), `openminion setup --list-providers` | errors are typed and readable; the provider listing ran offline (its help text says it makes no network requests; this was not independently verified) | F1 surfaces as a bare `RuntimeError`, not a typed SDK error; `TurnTimeoutError` was never triggered | see F1 and F6 in WHAT_WE_LEARNED |
| Public API stability | `openminion.__all__`, `openminion.api.__all__`, 6 entry-point signatures | identical in 0.1.8 and 0.1.15: 12 and 15 exports, all signatures and parameters equal | n/a | `evidence/phase3/compare/0.1.8-vs-0.1.15/report.md` |
| Memory, skills, tasks, delegation, handoffs, streaming | none | not tested | not tested | — |

## How the tool exercises these blocks

1. **`compare`.**
   - Installs each version into its own venv.
   - Runs one shared probe file (`upgrade_scout/probe.py`) in bounded processes.
   - Records the exports, the signatures, an echo turn checked against a 4-point contract, and the documented minimal
     config.
   - Produces a deterministic verdict.
2. **`analyze`.** Gives a real provider one `Agent` turn with a no-argument `@tool` bound to that comparison's
   validated facts. The application writes the verdict and every factual statement; the model's `ModelSelection`
   only ranks categorized ids and applicable next checks, with labelled rationales. It is accepted only if:
   - the tool's Python body is observed to execute, after a scoped approval;
   - the payload fits the SDK's tool-result limits;
   - every id exists in the right category, and every check is applicable.

   This is the part that tests model-driven tool use.
   - **Attempt-5:** model-driven tool execution and an accepted selection were observed.
   - Its human review found the ranking sensible. It rejected one clause: "potentially impacting upgrade
     smoothness", because the minimal-config rejection is unchanged from 0.1.8 (B3).
   - **Earlier attempts:**
     - Attempt 3 (contract v1) failed the verdict lock and contained factual errors.
     - Attempt-4 (contract v2) used ids that do not exist.
     - Both followed from F9: the model received only the first 1200 characters of the tool result.
