"""Snapshot of the installed OpenMinion SDK's documented public surface."""

from __future__ import annotations

from typing import Any

from .probe import collect_surface


def sdk_surface() -> dict[str, Any]:
    """Return the installed SDK version, its public exports and key signatures.

    Uses the same defensive collection as the comparison probe; symbols that
    cannot be resolved are listed under "unresolved" instead of raising.
    """
    surface = collect_surface()
    snapshot = {key: surface[key] for key in ("sdk_version", "exports", "signatures")}
    for key in ("export_errors", "unresolved"):
        if surface[key]:
            snapshot[key] = surface[key]
    return snapshot
