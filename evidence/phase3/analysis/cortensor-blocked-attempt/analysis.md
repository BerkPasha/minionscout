# Upgrade brief: openminion 0.1.8 -> 0.1.15

**Analysis status: FAILED** (provider_error, tool_not_executed). No brief was accepted.

## Deterministic verdict (authoritative)

**compatible** (exit code 0, complete: True) from `report.json` sha256 `8b82e734b19d99b00f4e2d0eca44807f0ffeb6efa3660fa1743afc68a8e0fc93`. This verdict comes from the comparison, not from the model, and the model cannot change it.

> The comparison's echo-provider probes make no model call: they prove neither real model inference nor model-driven tool execution.

## Model run

| | |
| --- | --- |
| SDK | openminion 0.1.15 |
| configured provider | cortensor |
| configured model | gpt-oss-20b |
| runtime metadata: provider | None |
| runtime metadata: model (as reported; may not be a model id) | None |
| run_id / session_id | None / None |
| evidence tool `comparison_evidence` executed (Python-side invocations) | 0 |
| runtime-reported tool_calls | None |

## Why the analysis failed

- `provider_error`: The provider failed (ProviderError).
- `tool_not_executed`: The evidence tool's Python implementation never ran during the turn.
- detail: {'type': 'ProviderError', 'code': 'PROVIDER_ERROR', 'message': 'The configured model provider failed before it could return a decision (Cortensor request failed: session_id=1: cortensor request failed: [WinError 10061] Hedef makine etkin olarak reddettiğinden bağlantı kurulamadı). Please retry or switch models.'}

## Facts supplied to the model (deterministic)

Evidence paths are relative to the directory of `evidence\phase3\compare\0.1.8-vs-0.1.15\report.json`.

- **V1** Deterministic verdict for openminion 0.1.8 -> 0.1.15: compatible (exit code 0); comparison complete: True. (evidence: `report.json`)
- **S1** Conclusions cover only the probes listed here: the public exports of openminion and openminion.api, the signatures of 6 entry points, one echo-provider Agent.run with default_channel set, and the documented minimal config without default_channel. (evidence: `report.json`)
- **S2** The echo provider makes no model call. These results prove neither real model inference nor model-driven tool execution; the forced tool is attached, and tool_calls is recorded per version. (evidence: `report.json`)
- **S3** Added exports and signature differences are reported as facts. Only removed exports, entry points or parameters, and newly required parameters, count as API regressions; other signature changes need review. (evidence: `report.json`)
- **S4** An export root or entry point that could not be measured in a version is a coverage gap: the comparison is incomplete for it, and it is not counted as a regression. (evidence: `report.json`)
- **S5** Providers, network, memory, skills, tasks, delegation and permissions are not exercised. (evidence: `report.json`)
- **P1** The baseline requested openminion 0.1.8; installed 0.1.8; imported __version__ 0.1.8; Python 3.13.5 on Windows-11-10.0.26200-SP0; environment ok. (evidence: `baseline-0.1.8/environment.json`, `baseline-0.1.8/preflight.json`)
- **P2** The candidate requested openminion 0.1.15; installed 0.1.15; imported __version__ 0.1.15; Python 3.13.5 on Windows-11-10.0.26200-SP0; environment ok. (evidence: `candidate-0.1.15/environment.json`, `candidate-0.1.15/preflight.json`)
- **X1** Exports of openminion: 12 names in 0.1.8, 12 in 0.1.15; added none; removed none. (evidence: `baseline-0.1.8/surface.json`, `candidate-0.1.15/surface.json`)
- **X2** Exports of openminion.api: 15 names in 0.1.8, 15 in 0.1.15; added none; removed none. (evidence: `baseline-0.1.8/surface.json`, `candidate-0.1.15/surface.json`)
- **G1** Entry-point signatures identical in both versions: openminion.Agent, openminion.Agent.run, openminion.Agent.run_stream, openminion.tool, openminion.APIRuntime.from_config_path, openminion.APIRuntime.run_turn. (evidence: `baseline-0.1.8/surface.json`, `candidate-0.1.15/surface.json`)
- **B1** Echo contract (completed, echoed_message, echo_provider, session_preserved): baseline contract_met, candidate contract_met; failed checks {'baseline': [], 'candidate': []}; classification unchanged. (evidence: `baseline-0.1.8/echo_turn.json`, `candidate-0.1.15/echo_turn.json`)
- **B2** Echo telemetry (no model call): baseline llm_calls=1 tool_calls=0 input_tokens=0 output_tokens=0; candidate llm_calls=1 tool_calls=0 input_tokens=0 output_tokens=0. (evidence: `baseline-0.1.8/echo_turn.json`, `candidate-0.1.15/echo_turn.json`)
- **B3** Documented minimal config without default_channel: baseline rejected_invalid_channel, candidate rejected_invalid_channel (unchanged); candidate error: inbound authenticity denied (reason=invalid_channel, mode=warn). (evidence: `baseline-0.1.8/minimal_config.json`, `candidate-0.1.15/minimal_config.json`)
