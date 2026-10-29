"""Child process of ``analyze``: one OpenMinion Agent turn with the evidence tool.

The controller runs ``python -m upgrade_scout.analysis_worker REQUEST.json`` under
an external deadline, because SDK initialization can stall before Agent.run's
own timeout applies. The tool is bound to the facts in the request and takes no
arguments, so the model cannot choose files or commands. It returns them as
structured data that the controller checked against the SDK's tool-result limits.
Every execution of its Python body is appended to the tool log, with counts of
what it returned, independently of what the runtime reports.
"""

from __future__ import annotations

import copy
import datetime as _dt
import json
import sys
import traceback
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from .analysis import TOOL_NAME, ModelSelection, returned_counts
from .home import openminion_env, write_config
from .probe import write_text_atomic


def _sdk() -> SimpleNamespace:
    import openminion

    return SimpleNamespace(
        Agent=openminion.Agent, tool=openminion.tool, version=openminion.__version__,
        AgentOutputValidationError=openminion.AgentOutputValidationError,
        ProviderError=openminion.ProviderError, TurnTimeoutError=openminion.TurnTimeoutError,
    )


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="milliseconds")


def _runtime_identity(run: Any) -> dict[str, Any]:
    metadata = getattr(run, "metadata", None) or {}
    return {
        "id": getattr(run, "id", None),
        "run_id": getattr(run, "run_id", None),
        "session_id": getattr(run, "session_id", None),
        "run_state": getattr(run, "run_state", None),
        "metadata_provider": metadata.get("provider"),
        "metadata_model": metadata.get("model"),
        **{key: metadata.get(key) for key in ("request_id", "execution_id", "invocation_id")},
        "stats": getattr(run, "stats", None),
    }


def make_approval_callback(log_path: Path) -> Callable[[str, dict[str, Any], str], bool]:
    """Answer the SDK's tool confirmation for this workflow only, recording every decision.

    The SDK's default policy holds comparison_evidence for confirmation: an undeclared
    @tool is scoped WRITE_SAFE with unknown reversibility. That is accurate, because the
    tool appends an audit line to tool_calls.jsonl, a local write. Its only other effect
    is returning the bound, validated facts. This callback approves exactly that call with
    empty arguments; every other tool or argument is denied. Each approval is a one-time
    grant (the SDK's allow_once), and the SDK evaluates its policy again afterwards.
    """

    def approve(tool_name: str, args: dict[str, Any], approval_id: str) -> bool:
        if tool_name != TOOL_NAME:
            allowed, reason = False, f"only {TOOL_NAME} is authorized in this workflow"
        elif not isinstance(args, dict) or args:
            allowed, reason = False, "unexpected arguments; the evidence tool takes none"
        else:
            allowed, reason = True, ("bound evidence tool with empty arguments: returns the validated facts "
                                     "and appends its audit line (a local write)")
        entry = {
            "at": _now(), "tool": tool_name, "args": json.dumps(args, default=str, sort_keys=True)[:500],
            "approval_id": approval_id, "decision": "allow_once" if allowed else "deny", "reason": reason,
        }
        with log_path.open("a", encoding="utf-8") as log:
            log.write(json.dumps(entry) + "\n")
        return allowed

    return approve


def evidence_result(payload: dict[str, Any]) -> Any:
    """What comparison_evidence returns: a copy of the structured payload, never one JSON string.

    The SDK cuts each string in a tool result to 1200 characters before the model sees it;
    returned as one JSON string, the payload lost every observation in openai-attempt-4 (F9).
    """
    return copy.deepcopy(payload)


def execute(request: dict[str, Any], sdk: SimpleNamespace | None = None) -> dict[str, Any]:
    """Run the analysis turn described by request and return the worker result."""
    sdk = sdk or _sdk()
    tool_log = Path(request["tool_log"])
    payload = request["facts_payload"]

    def comparison_evidence() -> dict[str, Any]:
        """Return the selected comparison's verdict, scope rules, observations and next-check options. No arguments."""
        returned = evidence_result(payload)
        with tool_log.open("a", encoding="utf-8") as log:
            log.write(json.dumps({"tool": TOOL_NAME, "at": _now(), "returned": returned_counts(returned)}) + "\n")
        return returned

    result: dict[str, Any] = {"sdk_version": sdk.version, "started_at": _now()}
    home = Path(request["home"])
    config_path = write_config(home, provider=request["provider"], model=request.get("model"))
    with openminion_env(home):
        try:
            agent = sdk.Agent(
                instructions=request["instructions"],
                tools=[sdk.tool(comparison_evidence)],
                forced_tools=[TOOL_NAME],
                output_type=ModelSelection,
                config_path=str(config_path),
                session_id=request["session_id"],
            )
            with agent:
                run = agent.run(request["message"], timeout_seconds=request["turn_timeout"],
                                approval_callback=make_approval_callback(Path(request["approval_log"])))
        except sdk.AgentOutputValidationError as exc:
            # The SDK keeps only the reply text here; run identity and stats are not available.
            result.update(status="output_invalid", raw_text=exc.raw_text,
                          error={"type": "AgentOutputValidationError", "message": str(exc)[:2000]})
        except sdk.ProviderError as exc:
            result.update(status="provider_error",
                          error={"type": "ProviderError", "code": exc.code, "message": exc.message})
        except sdk.TurnTimeoutError as exc:
            result.update(status="turn_timeout", error={"type": "TurnTimeoutError", "message": str(exc)})
        except Exception as exc:  # noqa: BLE001 - every failure must end up in the result file
            result.update(status="error", error={"type": type(exc).__name__, "message": str(exc)[:2000]},
                          traceback_tail=traceback.format_exc().splitlines()[-20:])
        else:
            output = run.output
            result.update(
                status="completed", run_state=run.run_state, text=run.text,
                output=output.model_dump() if hasattr(output, "model_dump") else output,
                runtime=_runtime_identity(run),
            )
    result["finished_at"] = _now()
    return result


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    request = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    result = execute(request)
    write_text_atomic(Path(request["result_path"]), json.dumps(result, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
