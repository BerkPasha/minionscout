# OpenMinion compatibility report: 0.1.8 -> 0.1.15

**Verdict: compatible** (exit code 0). No regressions observed, and every probe completed. This covers only the probes listed under Scope.

Generated 2026-10-29T14:25:29+00:00 by minion-upgrade-scout 0.2.0.

## Scope

- Conclusions cover only the probes listed here: the public exports of openminion and openminion.api, the signatures of 6 entry points, one echo-provider Agent.run with default_channel set, and the documented minimal config without default_channel.
- The echo provider makes no model call. These results prove neither real model inference nor model-driven tool execution; the forced tool is attached, and tool_calls is recorded per version.
- Added exports and signature differences are reported as facts. Only removed exports, entry points or parameters, and newly required parameters, count as API regressions; other signature changes need review.
- An export root or entry point that could not be measured in a version is a coverage gap: the comparison is incomplete for it, and it is not counted as a regression.
- Providers, network, memory, skills, tasks, delegation and permissions are not exercised.

## Runs

| | baseline | candidate |
| --- | --- | --- |
| requested version | 0.1.8 | 0.1.15 |
| installed version | 0.1.8 | 0.1.15 |
| imported `__version__` | 0.1.8 | 0.1.15 |
| Python | 3.13.5 | 3.13.5 |
| platform | Windows-11-10.0.26200-SP0 | Windows-11-10.0.26200-SP0 |
| environment | ok | ok |
| preflight | completed | completed |
| surface | completed | completed |
| echo_turn | completed: completed | completed: completed |
| minimal_config | completed: raised | completed: raised |
| evidence | [baseline-0.1.8/](baseline-0.1.8/) | [candidate-0.1.15/](candidate-0.1.15/) |

## Regressions

None observed in the executed probes.

## Environment failures and incomplete stages

None.

## Coverage gaps

None: every export root and entry point was measured in both versions.

## Export changes

- `openminion`: added none; removed none
- `openminion.api`: added none; removed none

Added exports are additive and not treated as breaking.

## Signature changes

Unchanged: `openminion.Agent`, `openminion.Agent.run`, `openminion.Agent.run_stream`, `openminion.tool`, `openminion.APIRuntime.from_config_path`, `openminion.APIRuntime.run_turn`.

## Behavior

| probe | required | baseline | candidate | classification |
| --- | --- | --- | --- | --- |
| echo_turn | yes | contract_met | contract_met | unchanged |
| minimal_config | no (observed behavior) | rejected_invalid_channel | rejected_invalid_channel | unchanged |

Echo contract (required on every version; telemetry below is informational):

| check | meaning | baseline | candidate |
| --- | --- | --- | --- |
| completed | Agent.run returned with run_state 'completed' | True | True |
| echoed_message | the reply text contains the probe message | True | True |
| echo_provider | the runtime reports provider 'echo' | True | True |
| session_preserved | the result keeps the requested session id 'upgrade-scout-probe' | True | True |

Echo turn observations (echo provider, no model call):

| field | baseline | candidate |
| --- | --- | --- |
| run_state | completed | completed |
| text_contains_message | True | True |
| llm_calls | 1 | 1 |
| tool_calls | 0 | 0 |
| input_tokens | 0 | 0 |
| output_tokens | 0 | 0 |
| runtime_provider | echo | echo |

## Exit codes

- `0` compatible: every probe completed and no regression was observed
- `1` regressions_detected: at least one regression was observed (even if other stages are incomplete)
- `2` invalid: bad arguments or unusable output directory; nothing was compared
- `3` inconclusive: installation, environment, probe execution or coverage was incomplete, or the required echo contract failed on both versions
