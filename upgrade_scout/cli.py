"""Command line entry point: python -m upgrade_scout {surface,run,compare,recheck,analyze}."""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

import openminion
from openminion import ProviderError, TurnTimeoutError

from .agent import DEFAULT_MESSAGE, run_scout
from .compare import EXIT_INCONCLUSIVE, EvidenceError, Timeouts, recheck, run_compare
from .home import missing_credential, openminion_env, write_config
from .surface import sdk_surface


def _cmd_surface(args: argparse.Namespace) -> int:
    print(json.dumps(sdk_surface(), indent=2, sort_keys=True))
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    key_env = missing_credential(args.provider)
    if key_env:
        print(
            f"error: provider '{args.provider}' needs {key_env} in the environment; it is not set.",
            file=sys.stderr,
        )
        return 2

    home = Path(args.home).resolve()
    config_path = write_config(home, provider=args.provider, model=args.model)
    record: dict[str, object] = {"sdk_version": openminion.__version__, "provider": args.provider}
    with openminion_env(home):
        try:
            result = run_scout(args.message, config_path=str(config_path))
        except ProviderError as exc:
            record.update(ok=False, error="ProviderError", code=exc.code, message=exc.message)
        except TurnTimeoutError as exc:
            record.update(ok=False, error="TurnTimeoutError", message=str(exc))
        else:
            record.update(
                ok=result.run_state == "completed",
                # As reported by the runtime; on echo "model" is "brain-orchestrator".
                runtime_provider=result.metadata.get("provider"),
                runtime_model=result.metadata.get("model"),
                run_state=result.run_state,
                session_id=result.session_id,
                run_id=result.run_id,
                stats=result.stats,
                text=result.text,
            )
    if args.provider == "echo":
        record["model_inference"] = "none: echo provider"
    else:
        record["model_inference"] = "succeeded" if record["ok"] else "failed"
    print(json.dumps(record, indent=2))
    return 0 if record["ok"] else 1


def _cmd_compare(args: argparse.Namespace) -> int:
    output_dir = args.output_dir or Path("scout-reports") / f"{args.baseline}-vs-{args.candidate}"
    timeouts = Timeouts(install=args.install_timeout, preflight=args.preflight_timeout, probe=args.probe_timeout)
    try:
        return run_compare(
            args.baseline, args.candidate, output_dir,
            state_root=args.state_root, timeouts=timeouts, recreate_envs=args.recreate_envs,
        )
    except Exception:  # noqa: BLE001 - an unfinished comparison must not exit 1 ("regressions")
        traceback.print_exc()
        print("error: the comparison did not finish; treat it as inconclusive", file=sys.stderr)
        return EXIT_INCONCLUSIVE


def _cmd_recheck(args: argparse.Namespace) -> int:
    try:
        summary = recheck(args.report)
    except (EvidenceError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(summary, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return summary["recomputed"]["exit_code"]


def _cmd_analyze(args: argparse.Namespace) -> int:
    from .analysis import EXIT_FAILED, run_analyze

    try:
        return run_analyze(args.report, args.provider, args.model, args.output_dir,
                           deadline_s=args.deadline, state_root=args.state_root)
    except Exception:  # noqa: BLE001 - an unfinished analysis must read as failed
        traceback.print_exc()
        print("error: the analysis did not finish; no model selection was accepted", file=sys.stderr)
        return EXIT_FAILED


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="upgrade_scout", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    surface = commands.add_parser("surface", help="print the installed SDK's public surface as JSON")
    surface.set_defaults(handler=_cmd_surface)

    run = commands.add_parser("run", help="run the scout agent once and print a JSON run record")
    run.add_argument("--provider", default="echo", help="OpenMinion provider name (default: echo)")
    run.add_argument("--model", help="model id for the provider (default: the provider's built-in default)")
    run.add_argument("--message", default=DEFAULT_MESSAGE, help="message to send to the agent")
    run.add_argument("--home", default=".scout-home", help="project-local OpenMinion home (default: .scout-home)")
    run.set_defaults(handler=_cmd_run)

    compare = commands.add_parser(
        "compare", help="compare two OpenMinion versions in isolated environments (no credentials needed)"
    )
    compare.add_argument("--baseline", required=True, help="baseline openminion version, e.g. 0.1.8")
    compare.add_argument("--candidate", required=True, help="candidate openminion version, e.g. 0.1.15")
    compare.add_argument("--output-dir", type=Path, help="default: scout-reports/<baseline>-vs-<candidate>")
    compare.add_argument("--state-root", type=Path,
                         help="where per-version venvs and work dirs live (default: a short user-local path)")
    compare.add_argument("--install-timeout", type=float, default=900, help="seconds per pip install")
    compare.add_argument("--preflight-timeout", type=float, default=60, help="seconds for the preflight stage")
    compare.add_argument("--probe-timeout", type=float, default=300, help="seconds per probe stage")
    compare.add_argument("--recreate-envs", action="store_true", help="delete and rebuild the version venvs")
    compare.set_defaults(handler=_cmd_compare)

    recheck_cmd = commands.add_parser(
        "recheck", help="recompute a saved comparison from its raw evidence with the current logic (offline)"
    )
    recheck_cmd.add_argument("report", type=Path, help="path to a comparison's report.json")
    recheck_cmd.add_argument("--output", type=Path, help="also write the summary JSON here")
    recheck_cmd.set_defaults(handler=_cmd_recheck)

    analyze = commands.add_parser(
        "analyze", help="write the factual upgrade report for a comparison and have an OpenMinion agent rank "
                        "its observations and next checks"
    )
    analyze.add_argument("--report", type=Path, required=True, help="a current-schema comparison report.json")
    analyze.add_argument("--provider", required=True, help="OpenMinion provider, e.g. openai, openrouter, groq")
    analyze.add_argument("--model", help="model id for the provider (required unless --provider echo)")
    analyze.add_argument("--output-dir", type=Path, required=True,
                         help="where analysis.json and analysis.md go (outside the comparison directory)")
    analyze.add_argument("--deadline", type=float, default=600,
                         help="seconds before the analysis worker process is killed (default 600)")
    analyze.add_argument("--state-root", type=Path, help="where the temporary OpenMinion home lives")
    analyze.set_defaults(handler=_cmd_analyze)
    return parser


def main(argv: list[str] | None = None) -> int:
    os.environ.setdefault("OPENMINION_LOG_LEVEL", "WARNING")
    args = build_parser().parse_args(argv)
    return args.handler(args)
