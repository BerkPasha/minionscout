# Upgrade analysis: openminion 0.1.8 -> 0.1.15

**Analysis status: success.** A real provider ran, the evidence tool executed, and the model's selection passed validation.

## Authoritative verdict (application-generated)

**compatible** (exit code 0, complete: True). No regressions observed, and every probe completed. This covers only the probes listed under Scope. From `report.json` sha256 `8b82e734b19d99b00f4e2d0eca44807f0ffeb6efa3660fa1743afc68a8e0fc93`; the model cannot change it.

> The comparison's echo-provider probes make no model call: they prove neither real model inference nor model-driven tool execution.

## Factual report (application-generated from the validated comparison; not model-written)

openminion 0.1.8 -> 0.1.15: compatible (exit code 0), within the probe scope listed below only. Exports: no additions or removals (openminion 12 -> 12, openminion.api 15 -> 15). Signatures: all 6 measured entry points identical. Coverage gaps: none. Regressions: 0. Echo turn: contract_met/contract_met, tool_calls 0/0 (echo makes no model call). Documented minimal config: baseline rejected_invalid_channel, candidate rejected_invalid_channel.

| core result | value | facts |
| --- | --- | --- |
| exports of `openminion` | 12 -> 12 names; added none; removed none | X1 |
| exports of `openminion.api` | 15 -> 15 names; added none; removed none | X2 |
| entry-point signatures | 6 identical; changed: none | G1 |
| coverage gaps | none | C0 |
| regressions | 0 | R0 |
| echo turn (no model call) | contract_met / contract_met; tool_calls 0 / 0 | B1, B2 |
| documented minimal config | rejected_invalid_channel / rejected_invalid_channel (inbound authenticity denied (reason=invalid_channel, mode=warn)) | B3 |

### Known rough edges (application-generated)

- Documented minimal config without default_channel: baseline rejected_invalid_channel, candidate rejected_invalid_channel (unchanged); candidate error: inbound authenticity denied (reason=invalid_channel, mode=warn). [B3]

### Scope limitations (application-generated)

- **S1** Conclusions cover only the probes listed here: the public exports of openminion and openminion.api, the signatures of 6 entry points, one echo-provider Agent.run with default_channel set, and the documented minimal config without default_channel.
- **S2** The echo provider makes no model call. These results prove neither real model inference nor model-driven tool execution; the forced tool is attached, and tool_calls is recorded per version.
- **S3** Added exports and signature differences are reported as facts. Only removed exports, entry points or parameters, and newly required parameters, count as API regressions; other signature changes need review.
- **S4** An export root or entry point that could not be measured in a version is a coverage gap: the comparison is incomplete for it, and it is not counted as a regression.
- **S5** Providers, network, memory, skills, tasks, delegation and permissions are not exercised.

## Model contribution (ranking and rationales only)

The model chose and ordered the ids below; every statement and action is application-written. Only the text marked *Model rationale* is model-written, and it is a recommendation, not a fact.

### Key observations, ranked by the model

1. No regressions were observed in the executed probes. [R0]
2. Echo contract (completed, echoed_message, echo_provider, session_preserved): baseline contract_met, candidate contract_met; failed checks {'baseline': [], 'candidate': []}; classification unchanged. [B1]
3. Entry-point signatures: 6 of 6 identical in both versions (openminion.Agent, openminion.Agent.run, openminion.Agent.run_stream, openminion.tool, openminion.APIRuntime.from_config_path, openminion.APIRuntime.run_turn); 0 changed. [G1]
4. No coverage gaps: every export root and entry point was measured in both versions. [C0]
5. Exports of openminion: 12 names in 0.1.8, 12 in 0.1.15; added: none; removed: none. [X1]
6. Exports of openminion.api: 15 names in 0.1.8, 15 in 0.1.15; added: none; removed: none. [X2]

### Limitations the model considered most relevant

- Conclusions cover only the probes listed here: the public exports of openminion and openminion.api, the signatures of 6 entry points, one echo-provider Agent.run with default_channel set, and the documented minimal config without default_channel. [S1]
- The echo provider makes no model call. These results prove neither real model inference nor model-driven tool execution; the forced tool is attached, and tool_calls is recorded per version. [S2]
- Added exports and signature differences are reported as facts. Only removed exports, entry points or parameters, and newly required parameters, count as API regressions; other signature changes need review. [S3]
- An export root or entry point that could not be measured in a version is a coverage gap: the comparison is incomplete for it, and it is not counted as a regression. [S4]
- Providers, network, memory, skills, tasks, delegation and permissions are not exercised. [S5]

### Next checks, ranked by the model

1. **Run your agent's own workflow with a real model provider on the candidate version.** (applies because the echo probes prove neither real inference nor model-driven tool execution)
   - *Model rationale (model-written):* This check is important because the echo probes do not demonstrate real model inference or model-driven tool execution, which are critical for validating upgrade behavior in production-like scenarios. [S2, B1, B2]
2. **Test the building blocks your agent uses that these probes do not exercise (memory, skills, tasks, delegation, permissions).** (applies because the probes cover only exports, signatures, an echo turn and the minimal config)
   - *Model rationale (model-written):* Testing building blocks like memory, skills, tasks, delegation, and permissions is necessary because these aspects are not exercised by the existing probes, leaving gaps in coverage for the upgrade evaluation. [S5]
3. **Set default_channel on agents that rely on the documented minimal config.** (applies because the candidate rejects the documented minimal config (invalid_channel))
   - *Model rationale (model-written):* Setting default_channel on agents relying on the minimal config matters since the candidate version rejects the documented minimal config due to invalid_channel errors, potentially impacting upgrade smoothness. [B3, S1]

Raw model output, as returned and separately identified: `worker/model_output.json`.

## Model run

| | |
| --- | --- |
| SDK | openminion 0.1.15 |
| configured provider | openai |
| configured model | gpt-4.1-mini |
| runtime metadata: provider | openai |
| runtime metadata: model (as reported; may not be a model id) | brain-orchestrator |
| run_id / session_id | 23ab8f8132a6407282c6da543f164d86 / upgrade-scout-analysis |
| tool approvals (allow_once / deny), see `worker/approvals.jsonl` | 1 / 0 |
| evidence tool `comparison_evidence` executed (Python-side invocations) | 1 |
| runtime-reported tool_calls | 1 |
| worker elapsed seconds (external process) | 19.058 |
| runtime-reported usage | llm_calls=1, input_tokens=10107, output_tokens=560, cache_read_tokens=0, tool_calls=1, duration_ms=13272 |

## Checks

Automatic:

- the comparison report matches its raw evidence, and its declarations match this tool's definitions
- the evidence payload fits the pinned SDK's tool-result limits (checked before any model call), so it is not cut on its way to the model
- the verdict and every measured result are rendered by this application, never by the model
- the reply matches ModelSelection exactly (extra fields such as a verdict or summary are rejected)
- key_observations are observation facts; relevant_limitations are scope-rule facts; ids exist
- every ranked next check is one of the options this application derived as applicable
- the evidence tool's Python body executed (tool_calls.jsonl), after a scoped allow_once approval
- a real provider ran, the worker exited 0, the turn completed, and the source report hash is unchanged

Still needs human review:

- whether the model's ranking of observations and next checks is sensible for your agent
- the model-written rationales, which are recommendations and may still be misleading
- whether the applicable next checks are sufficient; this tool only offers checks the evidence supports

## Facts supplied to the model (application-generated)

Evidence paths are relative to the directory of `evidence\phase3\compare\0.1.8-vs-0.1.15\report.json`.

- **V1** (verdict) Deterministic verdict for openminion 0.1.8 -> 0.1.15: compatible (exit code 0); comparison complete: True. (evidence: `report.json`)
- **S1** (scope_rule) Conclusions cover only the probes listed here: the public exports of openminion and openminion.api, the signatures of 6 entry points, one echo-provider Agent.run with default_channel set, and the documented minimal config without default_channel. (evidence: `report.json`)
- **S2** (scope_rule) The echo provider makes no model call. These results prove neither real model inference nor model-driven tool execution; the forced tool is attached, and tool_calls is recorded per version. (evidence: `report.json`)
- **S3** (scope_rule) Added exports and signature differences are reported as facts. Only removed exports, entry points or parameters, and newly required parameters, count as API regressions; other signature changes need review. (evidence: `report.json`)
- **S4** (scope_rule) An export root or entry point that could not be measured in a version is a coverage gap: the comparison is incomplete for it, and it is not counted as a regression. (evidence: `report.json`)
- **S5** (scope_rule) Providers, network, memory, skills, tasks, delegation and permissions are not exercised. (evidence: `report.json`)
- **P1** (observation) The baseline requested openminion 0.1.8; installed 0.1.8; imported __version__ 0.1.8; Python 3.13.5 on Windows-11-10.0.26200-SP0; environment ok. (evidence: `baseline-0.1.8/environment.json`, `baseline-0.1.8/preflight.json`)
- **P2** (observation) The candidate requested openminion 0.1.15; installed 0.1.15; imported __version__ 0.1.15; Python 3.13.5 on Windows-11-10.0.26200-SP0; environment ok. (evidence: `candidate-0.1.15/environment.json`, `candidate-0.1.15/preflight.json`)
- **R0** (observation) No regressions were observed in the executed probes. (evidence: `report.json`)
- **X1** (observation) Exports of openminion: 12 names in 0.1.8, 12 in 0.1.15; added: none; removed: none. (evidence: `baseline-0.1.8/surface.json`, `candidate-0.1.15/surface.json`)
- **X2** (observation) Exports of openminion.api: 15 names in 0.1.8, 15 in 0.1.15; added: none; removed: none. (evidence: `baseline-0.1.8/surface.json`, `candidate-0.1.15/surface.json`)
- **G1** (observation) Entry-point signatures: 6 of 6 identical in both versions (openminion.Agent, openminion.Agent.run, openminion.Agent.run_stream, openminion.tool, openminion.APIRuntime.from_config_path, openminion.APIRuntime.run_turn); 0 changed. (evidence: `baseline-0.1.8/surface.json`, `candidate-0.1.15/surface.json`)
- **C0** (observation) No coverage gaps: every export root and entry point was measured in both versions. (evidence: `baseline-0.1.8/surface.json`, `candidate-0.1.15/surface.json`)
- **N0** (observation) No environment failures or incomplete stages. (evidence: `report.json`)
- **B1** (observation) Echo contract (completed, echoed_message, echo_provider, session_preserved): baseline contract_met, candidate contract_met; failed checks {'baseline': [], 'candidate': []}; classification unchanged. (evidence: `baseline-0.1.8/echo_turn.json`, `candidate-0.1.15/echo_turn.json`)
- **B2** (observation) Echo telemetry (no model call): baseline llm_calls=1 tool_calls=0 input_tokens=0 output_tokens=0; candidate llm_calls=1 tool_calls=0 input_tokens=0 output_tokens=0. (evidence: `baseline-0.1.8/echo_turn.json`, `candidate-0.1.15/echo_turn.json`)
- **B3** (observation) Documented minimal config without default_channel: baseline rejected_invalid_channel, candidate rejected_invalid_channel (unchanged); candidate error: inbound authenticity denied (reason=invalid_channel, mode=warn). (evidence: `baseline-0.1.8/minimal_config.json`, `candidate-0.1.15/minimal_config.json`)
