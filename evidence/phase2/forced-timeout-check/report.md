# OpenMinion compatibility report: 0.1.15 -> 0.1.15

**Verdict: inconclusive** (exit code 3). The comparison is incomplete, so compatibility is not established.

Generated 2026-10-29T13:54:03+00:00 by minion-upgrade-scout 0.2.0.

## Scope

- Conclusions cover only the probes listed here: the public exports of openminion and openminion.api, the signatures of 6 entry points, one echo-provider Agent.run with default_channel set, and the documented minimal config without default_channel.
- The echo provider makes no model call. These results prove neither real model inference nor model-driven tool execution; the forced tool is attached, and tool_calls is recorded per version.
- Added exports and signature differences are reported as facts. Only removed exports, entry points or parameters, and newly required parameters, count as API regressions; other signature changes need review.
- Providers, network, memory, skills, tasks, delegation and permissions are not exercised.

## Runs

| | baseline | candidate |
| --- | --- | --- |
| requested version | 0.1.15 | 0.1.15 |
| installed version | 0.1.15 | 0.1.15 |
| imported `__version__` | None | None |
| Python | 3.13.5 | 3.13.5 |
| platform | Windows-11-10.0.26200-SP0 | Windows-11-10.0.26200-SP0 |
| environment | ok | ok |
| preflight | completed | completed |
| surface | timeout [last step: collect_surface] | timeout [last step: collect_surface] |
| echo_turn | timeout [last step: import] | timeout [last step: import] |
| minimal_config | timeout [last step: import] | timeout [last step: import] |
| evidence | [baseline-0.1.15/](baseline-0.1.15/) | [candidate-0.1.15/](candidate-0.1.15/) |

## Regressions

None observed in the executed probes.

## Environment failures and incomplete stages

- incomplete: baseline 0.1.15 `stage_timeout` in stage `surface`: collect_surface ([evidence](baseline-0.1.15/surface.log))
- incomplete: baseline 0.1.15 `stage_timeout` in stage `echo_turn`: import ([evidence](baseline-0.1.15/echo_turn.log))
- incomplete: baseline 0.1.15 `stage_timeout` in stage `minimal_config`: import ([evidence](baseline-0.1.15/minimal_config.log))
- incomplete: candidate 0.1.15 `stage_timeout` in stage `surface`: collect_surface ([evidence](candidate-0.1.15/surface.log))
- incomplete: candidate 0.1.15 `stage_timeout` in stage `echo_turn`: import ([evidence](candidate-0.1.15/echo_turn.log))
- incomplete: candidate 0.1.15 `stage_timeout` in stage `minimal_config`: import ([evidence](candidate-0.1.15/minimal_config.log))

## Export changes

Not compared: the surface stage did not complete for both versions.

## Signature changes

Not compared: the surface stage did not complete for both versions.

## Behavior

| probe | required | baseline | candidate | classification |
| --- | --- | --- | --- | --- |
| echo_turn | yes | None | None | not_comparable |
| minimal_config | no (observed behavior) | None | None | not_comparable |

## Exit codes

- `0` compatible: every probe completed and no regression was observed
- `1` regressions_detected: at least one regression was observed (even if other stages are incomplete)
- `2` invalid: bad arguments or unusable output directory; nothing was compared
- `3` inconclusive: installation, environment or probe execution did not complete
