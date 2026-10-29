"""Two-version OpenMinion compatibility comparison: ``python -m upgrade_scout compare``.

Each SDK version gets its own virtual environment (only ``openminion==X`` is
installed, never this project), and every probe stage runs as a separate
``python -I probe.py STAGE`` process with an external timeout and its own fresh
working directory, OpenMinion home and session. The controller then compares
the per-version evidence and writes report.json and report.md.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from . import __version__
from .probe import ENTRY_POINTS, EXPORT_ROOTS, PROBE_SESSION_ID, STAGES, redact, write_text_atomic

PROBE_PATH = Path(__file__).with_name("probe.py")
# 2: coverage_gaps, the echo contract, and unresolved_in_* signature lists.
REPORT_SCHEMA = "minion-upgrade-scout/compare/2"
OUTPUT_MARKER = ".upgrade-scout-output"

EXIT_COMPATIBLE = 0
EXIT_REGRESSIONS = 1
EXIT_INVALID = 2
EXIT_INCONCLUSIVE = 3

VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
RUNTIME_STAGES = ("echo_turn", "minimal_config")

# Deepest file of the openminion 0.1.15 wheel below site-packages (measured in
# Phase 1). Without Windows long-path support, an install deeper than the limit
# fails with WinError 206.
DEEPEST_PACKAGE_PATH = 131
WINDOWS_PATH_LIMIT = 259 - 20  # MAX_PATH minus headroom for other versions

SCOPE = [
    "Conclusions cover only the probes listed here: the public exports of openminion and openminion.api, "
    f"the signatures of {len(ENTRY_POINTS)} entry points, one echo-provider Agent.run with default_channel set, "
    "and the documented minimal config without default_channel.",
    "The echo provider makes no model call. These results prove neither real model inference nor "
    "model-driven tool execution; the forced tool is attached, and tool_calls is recorded per version.",
    "Added exports and signature differences are reported as facts. Only removed exports, entry points or "
    "parameters, and newly required parameters, count as API regressions; other signature changes need review.",
    "An export root or entry point that could not be measured in a version is a coverage gap: the comparison "
    "is incomplete for it, and it is not counted as a regression.",
    "Providers, network, memory, skills, tasks, delegation and permissions are not exercised.",
]

# The echo turn must satisfy every check on a version; telemetry (token counts,
# stats keys, result fields) is reported but is not part of the contract.
ECHO_CONTRACT = {
    "completed": "Agent.run returned with run_state 'completed'",
    "echoed_message": "the reply text contains the probe message",
    "echo_provider": "the runtime reports provider 'echo'",
    "session_preserved": f"the result keeps the requested session id '{PROBE_SESSION_ID}'",
}

# Error types that mean a symbol is absent from the installed SDK. Any other
# resolution error (for example an unintrospectable signature) only means the
# symbol could not be measured.
_ABSENCE_ERRORS = {"AttributeError", "ImportError", "ModuleNotFoundError"}
_MODULE_ABSENCE_ERRORS = {"ImportError", "ModuleNotFoundError"}


@dataclass(frozen=True)
class Timeouts:
    venv: float = 300
    install: float = 900
    preflight: float = 60
    probe: float = 300


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


# --- bounded subprocesses ---------------------------------------------------------


def _tail(path: Path, lines: int = 30) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return text.splitlines()[-lines:]


def _redact_file(path: Path) -> None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    redacted = redact(text)
    if redacted != text:
        write_text_atomic(path, redacted)


def _kill_tree(proc: subprocess.Popen) -> None:
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=False,
            )
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()


def run_bounded(
    args: list[str],
    *,
    log_path: Path,
    timeout_s: float,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run args without a shell, output to log_path, killing the process tree at the timeout.

    Output goes to a file rather than a pipe: after a kill on Windows, reading a
    pipe that a grandchild still holds open can block forever.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {
        "command": [redact(str(a)) for a in args],
        "timeout_seconds": timeout_s,
        "log": log_path.name,
    }
    group = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if os.name == "nt" else {"start_new_session": True}
    )
    started = time.monotonic()
    with open(log_path, "wb") as log:
        try:
            proc = subprocess.Popen(
                args, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                cwd=cwd, env=env, **group,
            )
        except OSError as exc:
            record.update(status="error", returncode=None, error=redact(f"{type(exc).__name__}: {exc}"))
        else:
            try:
                returncode = proc.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                _kill_tree(proc)
                record.update(status="timeout", returncode=None)
            else:
                record.update(status="ok" if returncode == 0 else "failed", returncode=returncode)
    record["seconds"] = round(time.monotonic() - started, 3)
    _redact_file(log_path)
    record["log_tail"] = _tail(log_path)
    return record


# --- per-version environments -------------------------------------------------------


def default_state_root() -> Path:
    """A short, user-local path for comparison environments and work directories."""
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "mus"
    return Path.home() / ".cache" / "minion-upgrade-scout"


def env_python(env_dir: Path) -> Path:
    return env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _long_paths_enabled() -> bool:
    if os.name != "nt":
        return True
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem") as key:
            return winreg.QueryValueEx(key, "LongPathsEnabled")[0] == 1
    except OSError:
        return False


def check_path_length(env_dir: Path) -> dict[str, Any]:
    site_packages = env_dir / "Lib" / "site-packages"
    estimated = len(str(site_packages)) + 1 + DEEPEST_PACKAGE_PATH
    applies = os.name == "nt" and not _long_paths_enabled()
    return {
        "ok": not applies or estimated <= WINDOWS_PATH_LIMIT,
        "limit_applies": applies,
        "estimated_deepest_path_chars": estimated,
        "limit_chars": WINDOWS_PATH_LIMIT,
    }


def prepare_environment(
    version: str, env_dir: Path, evidence_dir: Path, timeouts: Timeouts, recreate: bool
) -> dict[str, Any]:
    """Create (or reuse) the venv for version and pip-install openminion==version into it."""
    env: dict[str, Any] = {"env_dir": redact(str(env_dir)), "path_check": check_path_length(env_dir)}
    if not env["path_check"]["ok"]:
        env.update(
            status="failed", failure="path_too_long",
            detail="The environment path is too deep for this SDK without Windows long-path support; "
                   "pass a shorter --state-root (for example C:\\mus).",
        )
        return env
    if recreate and env_dir.exists():
        shutil.rmtree(env_dir)
    python = env_python(env_dir)
    if python.exists():
        env["venv"] = {"status": "reused"}
    else:
        env["venv"] = run_bounded(
            [sys.executable, "-m", "venv", str(env_dir)],
            log_path=evidence_dir / "venv.log", timeout_s=timeouts.venv,
        )
        if env["venv"]["status"] != "ok":
            env.update(status="failed", failure=f"venv_{env['venv']['status']}")
            return env
    env["install"] = run_bounded(
        [str(python), "-m", "pip", "install", "--disable-pip-version-check", "--no-input",
         "--progress-bar", "off", f"openminion=={version}"],
        log_path=evidence_dir / "install.log", timeout_s=timeouts.install,
    )
    if env["install"]["status"] != "ok":
        env.update(
            status="failed", failure=f"install_{env['install']['status']}",
            detail="See install.log. If an earlier install was interrupted, retry with --recreate-envs.",
        )
        return env
    env["status"] = "ok"
    return env


def _worker_env() -> dict[str, str]:
    """The inherited environment without model credentials or OpenMinion overrides."""
    env = {
        name: value for name, value in os.environ.items()
        if not name.endswith("_API_KEY") and not name.startswith("OPENMINION_") and name != "GITHUB_TOKEN"
    }
    env["OPENMINION_LOG_LEVEL"] = "WARNING"
    return env


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def run_stage(
    stage: str, version: str, python: Path, workdir: Path, evidence_dir: Path, timeout_s: float,
    probe_path: Path = PROBE_PATH,
) -> dict[str, Any]:
    """Run one probe stage in its own process and classify how it ended."""
    workdir, evidence_dir = workdir.resolve(), evidence_dir.resolve()  # the worker runs in workdir
    workdir.mkdir(parents=True, exist_ok=False)
    output = evidence_dir / f"{stage}.json"
    output.unlink(missing_ok=True)
    process = run_bounded(
        [str(python), "-I", "-X", "utf8", str(probe_path), stage,
         "--requested-version", version, "--workdir", str(workdir), "--output", str(output)],
        log_path=evidence_dir / f"{stage}.log", timeout_s=timeout_s, cwd=workdir, env=_worker_env(),
    )
    _redact_file(output)  # before loading, so the record equals the evidence file
    data = _load_json(output)
    if process["status"] == "timeout":
        status = "timeout"
    elif process["status"] == "ok" and data is not None and data.get("complete"):
        status = "completed"
    else:
        status = "crashed"
    record: dict[str, Any] = {"status": status, "process": process, "evidence": output.name if data else None}
    if data is not None:
        record["result"] = data
        if status != "completed":
            record["last_step"] = data.get("current_step")
    return record


def _stage_blockers(version: str, preflight: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (blocks every later stage, blocks runtime stages) from the preflight stage."""
    if preflight["status"] != "completed":
        return None, f"preflight {preflight['status']}"
    data = preflight["result"]
    installed = data.get("installed_version")
    if installed != version:
        return f"installed openminion is {installed!r}, not the requested {version}", None
    if not data.get("socketpair", {}).get("ok") or not data.get("asyncio_loop", {}).get("ok"):
        return None, "loopback socketpair or asyncio event loop failed in preflight"
    return None, None


def probe_version(
    role: str, version: str, *, state_root: Path, work_root: Path, evidence_dir: Path,
    timeouts: Timeouts, recreate: bool, log=_log,
) -> dict[str, Any]:
    """Install version into its own environment and run every probe stage against it."""
    evidence_dir.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {
        "role": role, "requested_version": version, "evidence_dir": evidence_dir.name, "stages": {},
    }
    log(f"[{role} {version}] preparing environment")
    env_dir = state_root / "envs" / version
    record["environment"] = prepare_environment(version, env_dir, evidence_dir, timeouts, recreate)
    all_blocked = None
    if record["environment"]["status"] != "ok":
        all_blocked = f"environment {record['environment']['failure']}"
    runtime_blocked = None
    for stage in STAGES:
        blocked = all_blocked or (runtime_blocked if stage in RUNTIME_STAGES else None)
        if blocked:
            record["stages"][stage] = {"status": "not_run", "reason": blocked}
            continue
        log(f"[{role} {version}] stage {stage}")
        timeout = timeouts.preflight if stage == "preflight" else timeouts.probe
        result = run_stage(stage, version, env_python(env_dir), work_root / role / stage, evidence_dir, timeout)
        record["stages"][stage] = result
        if stage == "preflight":
            all_blocked, runtime_blocked = _stage_blockers(version, result)
    (evidence_dir / "environment.json").write_text(
        json.dumps(record["environment"], indent=2) + "\n", encoding="utf-8"
    )
    return record


# --- comparison ---------------------------------------------------------------------


def _result(record: dict[str, Any], stage: str) -> dict[str, Any] | None:
    stage_record = record["stages"].get(stage) or {}
    return stage_record.get("result") if stage_record.get("status") == "completed" else None


def _parameter_changes(before: list[dict], after: list[dict]) -> dict[str, Any]:
    old = {p["name"]: p for p in before}
    new = {p["name"]: p for p in after}
    variadic = {"VAR_POSITIONAL", "VAR_KEYWORD"}
    changes: dict[str, Any] = {
        "removed": sorted(set(old) - set(new)),
        "added_optional": sorted(n for n in set(new) - set(old) if new[n]["has_default"] or new[n]["kind"] in variadic),
        "added_required": sorted(n for n in set(new) - set(old) if not new[n]["has_default"] and new[n]["kind"] not in variadic),
        "modified": {},
    }
    for name in sorted(set(old) & set(new)):
        diff = {
            field: {"baseline": old[name][field], "candidate": new[name][field]}
            for field in ("kind", "default", "annotation") if old[name][field] != new[name][field]
        }
        if old[name]["has_default"] and not new[name]["has_default"]:
            changes["added_required"].append(name)
        if diff:
            changes["modified"][name] = diff
    positional = ("POSITIONAL_ONLY", "POSITIONAL_OR_KEYWORD")
    changes["positional_order_changed"] = (
        [p["name"] for p in before if p["kind"] in positional]
        != [p["name"] for p in after if p["kind"] in positional]
    )
    return changes


def _coverage_gap(target: str, symbol: str, b_error: Any, c_error: Any) -> dict[str, Any]:
    sides = [side for side, error in (("baseline", b_error), ("candidate", c_error)) if error is not None]
    return {"target": target, "symbol": symbol, "unmeasured_in": " and ".join(sides) or "unknown",
            "baseline_error": b_error, "candidate_error": c_error}


def _compare_surface(base: dict, cand: dict, report: dict) -> None:
    for root in EXPORT_ROOTS:
        b_names, c_names = base["exports"].get(root), cand["exports"].get(root)
        b_error, c_error = base["export_errors"].get(root), cand["export_errors"].get(root)
        if b_names is not None and c_names is not None:
            entry = {"added": sorted(set(c_names) - set(b_names)), "removed": sorted(set(b_names) - set(c_names))}
            for name in entry["removed"]:
                report["regressions"].append({"kind": "export_removed", "symbol": f"{root}.{name}"})
        else:
            entry = {"baseline_error": b_error, "candidate_error": c_error}
            # Only a root that imports on the baseline and is absent on the candidate is a
            # regression; anything else unmeasured (on either side) is a coverage gap.
            if b_names is not None and (c_error or {}).get("type") in _MODULE_ABSENCE_ERRORS:
                report["regressions"].append({"kind": "export_root_unavailable", "symbol": root, "detail": c_error})
            else:
                report["coverage_gaps"].append(_coverage_gap(
                    "export_root", root, None if b_names is not None else b_error or {"type": "unknown"},
                    None if c_names is not None else c_error or {"type": "unknown"}))
        report["exports"][root] = entry

    signatures = report["signatures"]
    for label in ENTRY_POINTS:
        b_sig, c_sig = base["signatures"].get(label), cand["signatures"].get(label)
        b_error, c_error = base["unresolved"].get(label), cand["unresolved"].get(label)
        if b_sig is not None and c_sig is not None:
            if b_sig == c_sig:
                signatures["unchanged"].append(label)
                continue
            changes = _parameter_changes(base["parameters"][label], cand["parameters"][label])
            signatures["changed"].append({"entry_point": label, "baseline": b_sig, "candidate": c_sig, **changes})
            for name in changes["removed"]:
                report["regressions"].append({"kind": "parameter_removed", "symbol": f"{label}({name})"})
            for name in changes["added_required"]:
                report["regressions"].append({"kind": "parameter_now_required", "symbol": f"{label}({name})"})
            continue
        if b_sig is not None:
            signatures["unresolved_in_candidate"].append({"entry_point": label, "error": c_error})
            if (c_error or {}).get("type") in _ABSENCE_ERRORS:
                report["regressions"].append({"kind": "entry_point_missing", "symbol": label, "detail": c_error})
                continue
        elif c_sig is not None:
            signatures["unresolved_in_baseline"].append({"entry_point": label, "error": b_error})
        else:
            signatures["unresolved_in_both"].append(label)
        report["coverage_gaps"].append(_coverage_gap(
            "entry_point", label, None if b_sig is not None else b_error or {"type": "unknown"},
            None if c_sig is not None else c_error or {"type": "unknown"}))


_ECHO_FIELDS = ("run_state", "session_id", "has_run_id", "text_contains_message", "runtime_provider", "result_type")


def _echo_view(result: dict[str, Any]) -> dict[str, Any]:
    summary = result.get("result") or {}
    stats = summary.get("stats") or {}
    view = {field: summary.get(field) for field in _ECHO_FIELDS}
    view["stats_keys"] = sorted(stats)
    for key in ("llm_calls", "tool_calls", "input_tokens", "output_tokens"):
        view[key] = stats.get(key)
    view["result_fields"] = summary.get("result_fields")
    return view


def echo_contract(result: dict[str, Any]) -> dict[str, bool]:
    """Evaluate the ECHO_CONTRACT checks on one version's echo_turn result."""
    summary = result.get("result") or {}
    return {
        "completed": result.get("outcome") == "completed" and summary.get("run_state") == "completed",
        "echoed_message": summary.get("text_contains_message") is True,
        "echo_provider": summary.get("runtime_provider") == "echo",
        "session_preserved": summary.get("session_id") == PROBE_SESSION_ID,
    }


def _compare_echo(base: dict | None, cand: dict | None) -> dict[str, Any]:
    entry: dict[str, Any] = {"probe": "echo_turn", "required": True}
    if base is None or cand is None:
        entry["classification"] = "not_comparable"
        return entry
    b_checks, c_checks = echo_contract(base), echo_contract(cand)
    b_ok, c_ok = all(b_checks.values()), all(c_checks.values())
    entry["baseline"] = "contract_met" if b_ok else "contract_failed"
    entry["candidate"] = "contract_met" if c_ok else "contract_failed"
    entry["contract_checks"] = {"baseline": b_checks, "candidate": c_checks}
    b_view, c_view = _echo_view(base), _echo_view(cand)
    entry["observed"] = {"baseline": b_view, "candidate": c_view}
    if b_ok and c_ok:
        # Both meet the contract: remaining differences are telemetry, reported for review only.
        entry["differences"] = {
            key: {"baseline": b_view[key], "candidate": c_view[key]} for key in b_view if b_view[key] != c_view[key]
        }
        entry["classification"] = "changed" if entry["differences"] else "unchanged"
    elif b_ok:
        entry["classification"] = "regression"
        entry["note"] = "Echo contract failed on the candidate: " + ", ".join(
            name for name, ok in c_checks.items() if not ok)
        entry["candidate_error"] = cand.get("error")
    elif c_ok:
        entry["classification"] = "improved"
        entry["baseline_error"] = base.get("error")
    else:
        entry["classification"] = "failing_in_both"
        entry["baseline_error"], entry["candidate_error"] = base.get("error"), cand.get("error")
    return entry


def _minimal_outcome(result: dict[str, Any]) -> str:
    if result.get("outcome") == "completed":
        return "accepted"
    if result.get("invalid_channel_rejection"):
        return "rejected_invalid_channel"
    return f"other:{result.get('outcome')}"


def _compare_minimal(base: dict | None, cand: dict | None) -> dict[str, Any]:
    entry: dict[str, Any] = {"probe": "minimal_config", "required": False}
    if base is None or cand is None:
        entry["classification"] = "not_comparable"
        return entry
    b, c = _minimal_outcome(base), _minimal_outcome(cand)
    entry["baseline"], entry["candidate"] = b, c
    if b == c:
        entry["classification"] = "unchanged"
    elif c == "accepted":
        entry["classification"] = "fixed"
        entry["note"] = "The documented minimal config is now accepted (Phase 1 finding F1 no longer reproduces)."
    elif b == "accepted":
        entry["classification"] = "regression"
        entry["note"] = "The documented minimal config worked on the baseline and fails on the candidate."
    else:
        entry["classification"] = "changed"
    entry["baseline_error"], entry["candidate_error"] = base.get("error"), cand.get("error")
    return entry


def _failures(record: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    """Split one version's problems into environment failures and incomplete stages."""
    environment, incomplete = [], []
    where = {"role": record["role"], "version": record["requested_version"]}
    env = record["environment"]
    if env.get("status") != "ok":
        environment.append({**where, "kind": env.get("failure"), "detail": env.get("detail"),
                            "evidence": f"{record['evidence_dir']}/environment.json"})
    preflight = _result(record, "preflight")
    if preflight is not None:
        if preflight.get("installed_version") != record["requested_version"]:
            environment.append({**where, "kind": "version_mismatch",
                                "detail": f"installed {preflight.get('installed_version')!r}"})
        for check in ("socketpair", "asyncio_loop"):
            if not preflight.get(check, {}).get("ok"):
                environment.append({**where, "kind": f"{check}_failed", "detail": preflight.get(check)})
    for stage, stage_record in record["stages"].items():
        status = stage_record["status"]
        if status == "completed":
            continue
        item = {**where, "kind": f"stage_{status}", "stage": stage,
                "detail": stage_record.get("reason") or stage_record.get("last_step"),
                "evidence": f"{record['evidence_dir']}/{stage}.log" if status != "not_run" else None}
        # A preflight that hangs or crashes is an environment problem; any other
        # stage that did not finish is unattributed (SDK hang or environment).
        (environment if stage == "preflight" and status != "not_run" else incomplete).append(item)
    return environment, incomplete


def compare(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Compare two probe_version records. Pure: no I/O."""
    report: dict[str, Any] = {
        "regressions": [], "environment_failures": [], "incomplete": [], "coverage_gaps": [],
        "exports": {}, "signatures": {
            "unchanged": [], "changed": [], "unresolved_in_candidate": [],
            "unresolved_in_baseline": [], "unresolved_in_both": [],
        },
    }
    for record in (baseline, candidate):
        environment, incomplete = _failures(record)
        report["environment_failures"] += environment
        report["incomplete"] += incomplete

    b_surface, c_surface = _result(baseline, "surface"), _result(candidate, "surface")
    if b_surface and c_surface:
        _compare_surface(b_surface["surface"], c_surface["surface"], report)
    else:
        report["exports"] = report["signatures"] = None

    report["behavior"] = [
        _compare_echo(_result(baseline, "echo_turn"), _result(candidate, "echo_turn")),
        _compare_minimal(_result(baseline, "minimal_config"), _result(candidate, "minimal_config")),
    ]
    for entry in report["behavior"]:
        if entry["classification"] == "regression":
            report["regressions"].append({"kind": "behavior_regression", "symbol": entry["probe"],
                                          "detail": entry.get("note") or entry.get("candidate_error")})

    complete = (
        not report["environment_failures"] and not report["incomplete"] and not report["coverage_gaps"]
        and all(entry["classification"] not in ("not_comparable", "failing_in_both") for entry in report["behavior"])
    )
    report["complete"] = complete
    if report["regressions"]:
        report["verdict"], report["exit_code"] = "regressions_detected", EXIT_REGRESSIONS
    elif not complete:
        report["verdict"], report["exit_code"] = "inconclusive", EXIT_INCONCLUSIVE
    else:
        report["verdict"], report["exit_code"] = "compatible", EXIT_COMPATIBLE
    return report


# --- reports ------------------------------------------------------------------------


def version_facts(record: dict[str, Any]) -> dict[str, Any]:
    """The fields of a version summary that come from raw evidence."""
    preflight = _result(record, "preflight") or {}
    surface = (_result(record, "surface") or {}).get("surface") or {}
    return {
        "requested_version": record["requested_version"],
        "installed_version": preflight.get("installed_version"),
        "imported_version": surface.get("sdk_version"),
        "python": (preflight.get("python") or {}).get("version"),
        "platform": preflight.get("platform"),
        "environment": {key: record["environment"].get(key) for key in ("status", "failure", "env_dir")},
        "evidence_dir": record["evidence_dir"],
    }


def _version_summary(record: dict[str, Any]) -> dict[str, Any]:
    stages = {}
    for stage, stage_record in record["stages"].items():
        summary = {key: stage_record.get(key) for key in ("status", "reason", "last_step", "evidence") if stage_record.get(key)}
        result = stage_record.get("result") or {}
        if "outcome" in result:
            summary["outcome"] = result["outcome"]
        if "process" in stage_record:
            summary["seconds"] = stage_record["process"]["seconds"]
            summary["log"] = stage_record["process"]["log"]
        stages[stage] = summary
    return {**version_facts(record), "stages": stages}


def build_report(baseline: dict[str, Any], candidate: dict[str, Any], *, request: dict[str, Any]) -> dict[str, Any]:
    """The full report.json content for two probe_version records."""
    return {
        "schema": REPORT_SCHEMA,
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "tool_version": __version__,
        "controller": {"python": platform.python_version(), "platform": platform.platform()},
        "request": request,
        "scope": SCOPE,
        "echo_contract": ECHO_CONTRACT,
        "versions": {"baseline": _version_summary(baseline), "candidate": _version_summary(candidate)},
        **compare(baseline, candidate),
    }


_VERDICT_TEXT = {
    "compatible": "No regressions observed, and every probe completed. This covers only the probes listed under Scope.",
    "regressions_detected": "At least one regression was observed in the executed probes.",
    "inconclusive": "The comparison is incomplete (an environment failure, an unfinished stage, a coverage gap, "
                    "or a required probe failing on both versions), so compatibility is not established.",
}


def _problem_line(category: str, problem: dict[str, Any]) -> str:
    line = f"- {category}: {problem['role']} {problem['version']} `{problem['kind']}`"
    if problem.get("stage"):
        line += f" in stage `{problem['stage']}`"
    if problem.get("detail"):
        line += f": {problem['detail']}"
    if problem.get("evidence"):
        line += f" ([evidence]({problem['evidence']}))"
    return line


def render_markdown(report: dict[str, Any]) -> str:
    base, cand = report["versions"]["baseline"], report["versions"]["candidate"]
    out = [
        f"# OpenMinion compatibility report: {base['requested_version']} -> {cand['requested_version']}",
        "",
        f"**Verdict: {report['verdict']}** (exit code {report['exit_code']}). {_VERDICT_TEXT[report['verdict']]}",
        "",
        f"Generated {report['generated_at']} by minion-upgrade-scout {report['tool_version']}.",
        "",
        "## Scope",
        "",
        *[f"- {line}" for line in report["scope"]],
        "",
        "## Runs",
        "",
        "| | baseline | candidate |",
        "| --- | --- | --- |",
    ]
    rows = [
        ("requested version", "requested_version"), ("installed version", "installed_version"),
        ("imported `__version__`", "imported_version"), ("Python", "python"), ("platform", "platform"),
    ]
    for label, key in rows:
        out.append(f"| {label} | {base.get(key)} | {cand.get(key)} |")
    out.append(f"| environment | {base['environment']['status']} | {cand['environment']['status']} |")
    for stage in STAGES:
        cells = []
        for version in (base, cand):
            s = version["stages"][stage]
            cell = s["status"] + (f": {s['outcome']}" if "outcome" in s else "")
            cell += f" ({s['reason']})" if s.get("reason") else ""
            cell += f" [last step: {s['last_step']}]" if s.get("last_step") else ""
            cells.append(cell)
        out.append(f"| {stage} | {cells[0]} | {cells[1]} |")
    out.append(f"| evidence | [{base['evidence_dir']}/]({base['evidence_dir']}/) | "
               f"[{cand['evidence_dir']}/]({cand['evidence_dir']}/) |")

    out += ["", "## Regressions", ""]
    out += [f"- `{r['kind']}`: `{r['symbol']}`" + (f" ({r['detail']})" if r.get("detail") else "")
            for r in report["regressions"]] or ["None observed in the executed probes."]

    out += ["", "## Environment failures and incomplete stages", ""]
    out += [_problem_line("environment", p) for p in report["environment_failures"]]
    out += [_problem_line("incomplete", p) for p in report["incomplete"]]
    if not report["environment_failures"] and not report["incomplete"]:
        out.append("None.")

    out += ["", "## Coverage gaps", ""]
    out += [f"- `{gap['symbol']}` ({gap['target']}): not measured in {gap['unmeasured_in']}"
            for gap in report["coverage_gaps"]] or ["None: every export root and entry point was measured in both versions."]
    if report["coverage_gaps"]:
        out += ["", "A coverage gap makes the comparison incomplete; it is not counted as a regression."]

    out += ["", "## Export changes", ""]
    if report["exports"] is None:
        out.append("Not compared: the surface stage did not complete for both versions.")
    else:
        for root, entry in report["exports"].items():
            if "added" in entry:
                added = ", ".join(f"`{n}`" for n in entry["added"]) or "none"
                removed = ", ".join(f"`{n}`" for n in entry["removed"]) or "none"
                out.append(f"- `{root}`: added {added}; removed {removed}")
            else:
                out.append(f"- `{root}`: not comparable ({entry})")
        out.append("")
        out.append("Added exports are additive and not treated as breaking.")

    out += ["", "## Signature changes", ""]
    sigs = report["signatures"]
    if sigs is None:
        out.append("Not compared: the surface stage did not complete for both versions.")
    else:
        out.append(f"Unchanged: {', '.join(f'`{n}`' for n in sigs['unchanged']) or 'none'}.")
        for change in sigs["changed"]:
            out += ["", f"### `{change['entry_point']}`", "",
                    f"- baseline: `{change['baseline']}`", f"- candidate: `{change['candidate']}`"]
            for key in ("removed", "added_required", "added_optional"):
                if change[key]:
                    out.append(f"- {key.replace('_', ' ')}: {', '.join(f'`{n}`' for n in change[key])}")
            for name, diff in change["modified"].items():
                out.append(f"- `{name}` modified: " + "; ".join(
                    f"{field} `{d['baseline']}` -> `{d['candidate']}`" for field, d in diff.items()))
            if change["positional_order_changed"]:
                out.append("- positional parameter order changed (review positional callers)")
        for key in ("unresolved_in_candidate", "unresolved_in_baseline", "unresolved_in_both"):
            if sigs[key]:
                out.append(f"- {key.replace('_', ' ')}: {sigs[key]}")

    out += ["", "## Behavior", "", "| probe | required | baseline | candidate | classification |",
            "| --- | --- | --- | --- | --- |"]
    for entry in report["behavior"]:
        out.append(f"| {entry['probe']} | {'yes' if entry['required'] else 'no (observed behavior)'} | "
                   f"{entry.get('baseline')} | {entry.get('candidate')} | {entry['classification']} |")
    echo = report["behavior"][0]
    if echo.get("contract_checks"):
        out += ["", "Echo contract (required on every version; telemetry below is informational):", "",
                "| check | meaning | baseline | candidate |", "| --- | --- | --- | --- |"]
        for name, meaning in report["echo_contract"].items():
            out.append(f"| {name} | {meaning} | {echo['contract_checks']['baseline'][name]} | "
                       f"{echo['contract_checks']['candidate'][name]} |")
    if echo.get("observed"):
        out += ["", "Echo turn observations (echo provider, no model call):", "",
                "| field | baseline | candidate |", "| --- | --- | --- |"]
        for key in ("run_state", "text_contains_message", "llm_calls", "tool_calls",
                    "input_tokens", "output_tokens", "runtime_provider"):
            out.append(f"| {key} | {echo['observed']['baseline'][key]} | {echo['observed']['candidate'][key]} |")
    for entry in report["behavior"]:
        if entry.get("differences"):
            out.append("")
            out.append(f"{entry['probe']} differences: " + "; ".join(
                f"`{k}` {v['baseline']} -> {v['candidate']}" for k, v in entry["differences"].items()))
        if entry.get("note"):
            out += ["", f"{entry['probe']}: {entry['note']}"]

    out += [
        "", "## Exit codes", "",
        "- `0` compatible: every probe completed and no regression was observed",
        "- `1` regressions_detected: at least one regression was observed (even if other stages are incomplete)",
        "- `2` invalid: bad arguments or unusable output directory; nothing was compared",
        "- `3` inconclusive: installation, environment, probe execution or coverage was incomplete, "
        "or the required echo contract failed on both versions",
        "",
    ]
    return "\n".join(out)


# --- re-evaluating saved evidence ------------------------------------------------------

# The report fields that compare() derives from the evidence.
COMPARISON_FIELDS = (
    "regressions", "environment_failures", "incomplete", "coverage_gaps",
    "exports", "signatures", "behavior", "complete", "verdict", "exit_code",
)
_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.\-]+$")


class EvidenceError(ValueError):
    """A saved comparison or its evidence is missing, malformed or inconsistent."""


def evidence_file(report_dir: Path, *parts: str) -> Path:
    """Resolve a file named by a report, refusing anything but plain names inside report_dir."""
    for part in parts:
        if not isinstance(part, str) or not _SAFE_NAME.match(part) or part in (".", ".."):
            raise EvidenceError(f"unsafe evidence name in report: {part!r}")
    return report_dir.joinpath(*parts)


def load_report(report_path: Path) -> dict[str, Any]:
    report = _load_json(report_path)
    if report is None:
        raise EvidenceError(f"{report_path} is missing or is not a JSON object")
    for key in ("schema", "versions", "verdict", "exit_code"):
        if key not in report:
            raise EvidenceError(f"{report_path} has no {key!r}; it is not a comparison report")
    if not str(report["schema"]).startswith("minion-upgrade-scout/compare/"):
        raise EvidenceError(f"{report_path} has unknown schema {report['schema']!r}")
    return report


def load_records(report_path: Path, report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Rebuild the probe_version records of a saved comparison from its evidence files."""
    records = {}
    for role in ("baseline", "candidate"):
        summary = (report.get("versions") or {}).get(role)
        if not isinstance(summary, dict):
            raise EvidenceError(f"report has no {role} version summary")
        version = summary.get("requested_version")
        if not isinstance(version, str) or not VERSION_PATTERN.match(version):
            raise EvidenceError(f"{role}: invalid requested_version {version!r}")
        if summary.get("evidence_dir") != f"{role}-{version}":
            raise EvidenceError(f"{role}: evidence_dir {summary.get('evidence_dir')!r} is not {role}-{version}")
        environment = _load_json(evidence_file(report_path.parent, summary["evidence_dir"], "environment.json"))
        if environment is None:
            raise EvidenceError(f"{role}: environment.json is missing or unreadable")
        stages = {}
        for stage in STAGES:
            stage_summary = summary["stages"].get(stage)
            if not isinstance(stage_summary, dict) or "status" not in stage_summary:
                raise EvidenceError(f"{role}: no status for stage {stage}")
            stage_record = {k: stage_summary[k] for k in ("status", "reason", "last_step") if k in stage_summary}
            if stage_summary.get("evidence"):
                path = evidence_file(report_path.parent, summary["evidence_dir"], stage_summary["evidence"])
                data = _load_json(path)
                if data is None:
                    raise EvidenceError(f"{role}: {stage} evidence {path.name} is missing or unreadable")
                if data.get("stage") != stage or data.get("requested_version") != version:
                    raise EvidenceError(f"{role}: {path.name} was not produced by the {stage} probe for {version}")
                stage_record["result"] = data
                stage_record["evidence"] = stage_summary["evidence"]
            if stage_record["status"] == "completed" and not (stage_record.get("result") or {}).get("complete"):
                raise EvidenceError(f"{role}: {stage} is reported completed but its evidence is not complete")
            stages[stage] = stage_record
        records[role] = {
            "role": role, "requested_version": summary["requested_version"],
            "evidence_dir": summary["evidence_dir"], "environment": environment, "stages": stages,
        }
    return records


def recheck(report_path: Path) -> dict[str, Any]:
    """Recompute a saved comparison from its raw evidence with the current comparison logic."""
    report = load_report(report_path)
    records = load_records(report_path, report)
    fresh = compare(records["baseline"], records["candidate"])
    return {
        "source_report": report_path.name,
        "source_schema": report["schema"],
        "source_sha256": sha256_file(report_path),
        "stored": {key: report.get(key) for key in ("verdict", "exit_code", "complete")},
        "recomputed": {
            **{key: fresh[key] for key in ("verdict", "exit_code", "complete")},
            "regressions": fresh["regressions"],
            "coverage_gaps": fresh["coverage_gaps"],
            "environment_failures": fresh["environment_failures"],
            "incomplete": fresh["incomplete"],
            "behavior": [{k: b.get(k) for k in ("probe", "baseline", "candidate", "classification")}
                         for b in fresh["behavior"]],
        },
        "verdict_changed": fresh["verdict"] != report.get("verdict"),
        "matches_stored_comparison": all(fresh[key] == report.get(key) for key in COMPARISON_FIELDS),
    }


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _prepare_output_dir(output_dir: Path) -> str | None:
    """Make output_dir ready, clearing only what an earlier comparison wrote there."""
    if output_dir.exists() and any(output_dir.iterdir()):
        if not (output_dir / OUTPUT_MARKER).exists():
            return f"{output_dir} is not empty and was not created by a comparison; choose another --output-dir"
        for child in output_dir.iterdir():
            if child.name.startswith(("baseline-", "candidate-")) and child.is_dir():
                shutil.rmtree(child)
            elif child.name in ("report.json", "report.md"):
                child.unlink()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / OUTPUT_MARKER).write_text("written by python -m upgrade_scout compare\n", encoding="utf-8")
    return None


def run_compare(
    baseline: str, candidate: str, output_dir: Path, *, state_root: Path | None = None,
    timeouts: Timeouts = Timeouts(), recreate_envs: bool = False,
) -> int:
    for label, version in (("--baseline", baseline), ("--candidate", candidate)):
        if not VERSION_PATTERN.match(version):
            print(f"error: {label} must be a release version like 0.1.15, got {version!r}", file=sys.stderr)
            return EXIT_INVALID
    if min(asdict(timeouts).values()) <= 0:
        print("error: timeouts must be positive", file=sys.stderr)
        return EXIT_INVALID
    problem = _prepare_output_dir(output_dir)
    if problem:
        print(f"error: {problem}", file=sys.stderr)
        return EXIT_INVALID

    shown_output_dir, output_dir = output_dir, output_dir.resolve()
    state_root = (state_root or default_state_root()).resolve()
    work_root = state_root / "work" / uuid.uuid4().hex[:8]
    records = {}
    for role, version in (("baseline", baseline), ("candidate", candidate)):
        records[role] = probe_version(
            role, version, state_root=state_root, work_root=work_root,
            evidence_dir=output_dir / f"{role}-{version}", timeouts=timeouts,
            recreate=recreate_envs, log=_log,
        )
    shutil.rmtree(work_root, ignore_errors=True)

    report = build_report(records["baseline"], records["candidate"], request={
        "baseline": baseline, "candidate": candidate, "timeouts_seconds": asdict(timeouts),
        "state_root": redact(str(state_root)), "probe_session_id": PROBE_SESSION_ID,
    })
    (output_dir / "report.json").write_text(redact(json.dumps(report, indent=2)) + "\n", encoding="utf-8")
    (output_dir / "report.md").write_text(redact(render_markdown(report)), encoding="utf-8")
    _log(f"verdict: {report['verdict']} (exit {report['exit_code']}); report: {shown_output_dir / 'report.md'}")
    return report["exit_code"]
