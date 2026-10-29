"""The one probe implementation that runs inside every per-version environment.

The comparison controller runs this file by path (``python -I probe.py STAGE ...``)
in a virtual environment that has only ``openminion`` installed, not this project.
It therefore imports nothing but the standard library at module level and imports
openminion lazily. Every lookup is defensive: a missing module, symbol or signature
is recorded as evidence instead of ending the probe.

Stages, each run in its own process by the controller:
  preflight       Python, platform, installed distribution version, loopback/asyncio
                  (does not import openminion)
  surface         public exports and entry-point signatures
  echo_turn       one Agent.run on the echo provider with default_channel set
  minimal_config  the documented minimal config, which omits default_channel

The output JSON is rewritten after every step, so a stage killed by the
controller's timeout still shows the step it was in.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import importlib
import importlib.metadata
import inspect
import json
import os
import platform
import re
import socket
import sys
import time
import traceback
from pathlib import Path
from typing import Any

PROBE_SCHEMA = 1
STAGES = ("preflight", "surface", "echo_turn", "minimal_config")

EXPORT_ROOTS = ("openminion", "openminion.api")

# label -> (module, attribute path). The same entry points Phase 1 recorded;
# "openminion.Agent" is the constructor signature.
ENTRY_POINTS = {
    "openminion.Agent": ("openminion", "Agent.__init__"),
    "openminion.Agent.run": ("openminion", "Agent.run"),
    "openminion.Agent.run_stream": ("openminion", "Agent.run_stream"),
    "openminion.tool": ("openminion", "tool"),
    "openminion.APIRuntime.from_config_path": ("openminion", "APIRuntime.from_config_path"),
    "openminion.APIRuntime.run_turn": ("openminion", "APIRuntime.run_turn"),
}

PROBE_MESSAGE = "upgrade scout probe turn"
PROBE_SESSION_ID = "upgrade-scout-probe"
TURN_TIMEOUT_SECONDS = 60


def redact(text: str) -> str:
    """Replace the user's home directory in text (plain or JSON-escaped) with ~."""
    home = str(Path.home())
    for variant in {home, home.replace("\\", "/"), home.replace("\\", "\\\\")}:
        text = re.sub(re.escape(variant), "~", text, flags=re.IGNORECASE)
    return text


def write_text_atomic(path: Path, text: str, attempts: int = 10) -> None:
    """Write text to path via a temporary file and os.replace.

    On Windows the replace fails with PermissionError while another process
    (a sync client or virus scanner, for example) briefly holds the target open,
    so it is retried with a short backoff before the error is allowed through.
    """
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    for attempt in range(attempts):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.1 * (attempt + 1))


def _error(exc: BaseException) -> dict[str, str]:
    return {"type": type(exc).__name__, "message": redact(str(exc))[:2000]}


def _traceback_tail(exc: BaseException, lines: int = 25) -> list[str]:
    formatted = "".join(traceback.format_exception(exc)).splitlines()
    return [redact(line) for line in formatted[-lines:]]


def resolve(module_name: str, attr_path: str = "") -> tuple[Any, dict[str, str] | None]:
    """Import module_name and walk attr_path; return (object, None) or (None, error)."""
    try:
        obj: Any = importlib.import_module(module_name)
    except BaseException as exc:  # noqa: BLE001 - any import failure is evidence
        return None, _error(exc)
    for part in filter(None, attr_path.split(".")):
        try:
            obj = getattr(obj, part)
        except AttributeError as exc:
            return None, _error(exc)
    return obj, None


def describe_signature(obj: Any) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    """Return the signature text and its parameters, or the reason it is unavailable."""
    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError) as exc:
        return None, _error(exc)
    params = []
    for p in sig.parameters.values():
        params.append({
            "name": p.name,
            "kind": p.kind.name,
            "has_default": p.default is not inspect.Parameter.empty,
            "default": None if p.default is inspect.Parameter.empty else repr(p.default),
            "annotation": None if p.annotation is inspect.Parameter.empty else str(p.annotation),
        })
    return {"text": str(sig), "parameters": params}, None


def collect_surface() -> dict[str, Any]:
    """Exports and entry-point signatures of the installed SDK, gathered defensively."""
    surface: dict[str, Any] = {
        "sdk_version": None,
        "exports": {},
        "export_errors": {},
        "signatures": {},
        "parameters": {},
        "unresolved": {},
    }
    version, error = resolve("openminion", "__version__")
    surface["sdk_version"] = version if error is None else None
    if error:
        surface["export_errors"]["openminion.__version__"] = error

    for root in EXPORT_ROOTS:
        names, error = resolve(root, "__all__")
        if error:
            surface["export_errors"][root] = error
        else:
            surface["exports"][root] = sorted(str(n) for n in names)

    for label, (module_name, attr_path) in ENTRY_POINTS.items():
        obj, error = resolve(module_name, attr_path)
        if error is None:
            described, error = describe_signature(obj)
        if error:
            surface["unresolved"][label] = error
            continue
        surface["signatures"][label] = described["text"]
        surface["parameters"][label] = described["parameters"]
    return surface


# --- stage helpers -------------------------------------------------------------


class _Recorder:
    """Accumulates one stage's result and rewrites the output file after each step."""

    def __init__(self, output: Path, stage: str, requested_version: str) -> None:
        self.output = output
        self.data: dict[str, Any] = {
            "probe_schema": PROBE_SCHEMA,
            "stage": stage,
            "requested_version": requested_version,
            "started_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
            "complete": False,
            "current_step": None,
        }
        self.flush()

    def step(self, name: str) -> None:
        self.data["current_step"] = name
        self.flush()

    def finish(self) -> None:
        self.data["current_step"] = None
        self.data["complete"] = True
        self.data["finished_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
        self.flush()

    def flush(self) -> None:
        write_text_atomic(self.output, redact(json.dumps(self.data, indent=2, sort_keys=True, default=str)) + "\n")


def _use_home(workdir: Path, config: dict[str, Any]) -> Path:
    """Create an OpenMinion home in workdir, point the env vars at it, return the config path."""
    home = workdir / "home"
    data_root = home / ".openminion"
    data_root.mkdir(parents=True, exist_ok=True)
    config_path = data_root / "agents.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    os.environ["OPENMINION_HOME"] = str(home)
    os.environ["OPENMINION_DATA_ROOT"] = str(data_root)
    os.environ.setdefault("OPENMINION_LOG_LEVEL", "WARNING")
    return config_path


def _summarize_result(result: Any) -> dict[str, Any]:
    stats = getattr(result, "stats", None)
    metadata = getattr(result, "metadata", None)
    text = getattr(result, "text", None)
    return {
        "result_type": type(result).__name__,
        "result_fields": sorted(n for n in vars(result) if not n.startswith("_"))
        if hasattr(result, "__dict__") else None,
        "run_state": getattr(result, "run_state", None),
        "session_id": getattr(result, "session_id", None),
        "has_run_id": bool(getattr(result, "run_id", None)),
        "text": text,
        "text_contains_message": isinstance(text, str) and PROBE_MESSAGE in text,
        "stats": stats if isinstance(stats, dict) else None,
        "runtime_provider": metadata.get("provider") if isinstance(metadata, dict) else None,
    }


def _run_turn(rec: _Recorder, config_path: Path, agent_kwargs: dict[str, Any]) -> None:
    """Construct an Agent, run one turn, and record the outcome or the exception."""
    rec.step("import")
    Agent, error = resolve("openminion", "Agent")
    if error:
        rec.data.update(outcome="import_error", error=error)
        return
    rec.step("agent_init")
    started = time.monotonic()
    try:
        agent = Agent(config_path=str(config_path), session_id=PROBE_SESSION_ID, **agent_kwargs)
    except BaseException as exc:  # noqa: BLE001
        rec.data.update(outcome="init_error", error=_error(exc), traceback_tail=_traceback_tail(exc))
        return
    rec.step("agent_run")
    try:
        with agent:
            result = agent.run(PROBE_MESSAGE, timeout_seconds=TURN_TIMEOUT_SECONDS)
    except BaseException as exc:  # noqa: BLE001
        rec.data.update(outcome="raised", error=_error(exc), traceback_tail=_traceback_tail(exc))
    else:
        summary = _summarize_result(result)
        completed = summary["run_state"] == "completed"
        rec.data.update(outcome="completed" if completed else "not_completed", result=summary)
    finally:
        rec.data["turn_seconds"] = round(time.monotonic() - started, 3)


# --- stages ---------------------------------------------------------------------


def stage_preflight(rec: _Recorder, workdir: Path) -> None:
    rec.data["python"] = {
        "version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "executable": sys.executable,
    }
    rec.data["platform"] = platform.platform()
    try:
        rec.data["installed_version"] = importlib.metadata.version("openminion")
    except importlib.metadata.PackageNotFoundError as exc:
        rec.data["installed_version"] = None
        rec.data["installed_version_error"] = _error(exc)

    # asyncio's Windows event loop needs socket.socketpair(); a hang here explains
    # a runtime that never starts, independently of OpenMinion.
    rec.step("socketpair")
    started = time.monotonic()
    try:
        a, b = socket.socketpair()
        with a, b:
            a.sendall(b"x")
            b.recv(1)
        rec.data["socketpair"] = {"ok": True, "seconds": round(time.monotonic() - started, 3)}
    except OSError as exc:
        rec.data["socketpair"] = {"ok": False, "error": _error(exc)}

    rec.step("asyncio_loop")
    try:
        import asyncio

        loop = asyncio.new_event_loop()
        loop.run_until_complete(asyncio.sleep(0))
        loop.close()
        rec.data["asyncio_loop"] = {"ok": True}
    except Exception as exc:  # noqa: BLE001
        rec.data["asyncio_loop"] = {"ok": False, "error": _error(exc)}


def stage_surface(rec: _Recorder, workdir: Path) -> None:
    rec.step("collect_surface")
    rec.data["surface"] = collect_surface()


def stage_echo_turn(rec: _Recorder, workdir: Path) -> None:
    # Same Agent call shape as upgrade_scout.agent.run_scout: a forced @tool.
    config = {
        "default_agent": "scout",
        "agents": {"scout": {"name": "scout", "provider": "echo", "default_channel": "console"}},
    }
    rec.data["config"] = config
    config_path = _use_home(workdir, config)
    tool, error = resolve("openminion", "tool")
    if error:
        rec.data.update(outcome="import_error", error=error)
        return

    def installed_sdk_surface() -> str:
        """Return the installed OpenMinion SDK version, public exports and key signatures as JSON."""
        return json.dumps(collect_surface(), sort_keys=True)

    try:
        decorated = tool(installed_sdk_surface)
    except BaseException as exc:  # noqa: BLE001
        rec.data.update(outcome="init_error", error=_error(exc), traceback_tail=_traceback_tail(exc))
        return
    _run_turn(rec, config_path, {
        "instructions": "Call installed_sdk_surface and summarize the result.",
        "tools": [decorated],
        "forced_tools": ["installed_sdk_surface"],
    })


def stage_minimal_config(rec: _Recorder, workdir: Path) -> None:
    # The "smallest useful config" from the OpenMinion Configuration docs.
    config = {"default_agent": "default", "agents": {"default": {"name": "default", "provider": "echo"}}}
    rec.data["config"] = config
    config_path = _use_home(workdir, config)
    _run_turn(rec, config_path, {})
    error = rec.data.get("error") or {}
    rec.data["invalid_channel_rejection"] = "invalid_channel" in error.get("message", "")


_STAGE_FUNCTIONS = {
    "preflight": stage_preflight,
    "surface": stage_surface,
    "echo_turn": stage_echo_turn,
    "minimal_config": stage_minimal_config,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one Upgrade Scout probe stage.")
    parser.add_argument("stage", choices=STAGES)
    parser.add_argument("--requested-version", required=True)
    parser.add_argument("--workdir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    workdir, output = args.workdir.resolve(), args.output.resolve()

    workdir.mkdir(parents=True, exist_ok=True)
    os.chdir(workdir)  # the runtime creates .openminion/ under the cwd
    rec = _Recorder(output, args.stage, args.requested_version)
    _STAGE_FUNCTIONS[args.stage](rec, workdir)
    rec.finish()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
