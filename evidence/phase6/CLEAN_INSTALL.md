# Phase 6: clean-install reproducibility check (2026-10-29)

**Result:** every check passed. No release blocker was reproduced, and no code was changed.

## Environment

| Item | Value |
| --- | --- |
| OS | Microsoft Windows [Version 10.0.26200.9711] (Windows 11) |
| Base interpreter | Python 3.13.5 (`tags/v3.13.5:6cb20a2`, MSC v.1943, 64-bit), the system install the existing `.venv` was made from |
| pip in the new venv | 25.1.1 |
| Git | 2.53.0.windows.1. The repository has no commits yet. |
| Clean location | `%LOCALAPPDATA%\mus\rc` (a short path; it did not exist before the run) |
| Test basetemp | `%LOCALAPPDATA%\mus\rc-pt` |

## What was copied

Exactly the files a first commit would contain: untracked and not ignored by `.gitignore`
(`git ls-files -o --exclude-standard`).

- 216 files: the 214 project files plus this check's own `clean-install.sh` and the log being written.
- The excluded files include the existing `.venv`, `.git`, `.openminion/`, `.scout-home/`, `*.egg-info` and
  `__pycache__`.
- The copied `evidence/phase3/compare/0.1.8-vs-0.1.15/report.json` has sha256
  `8b82e734b19d99b00f4e2d0eca44807f0ffeb6efa3660fa1743afc68a8e0fc93`, the hash `openai-attempt-5` analyzed.

## Exact commands

The script is `evidence/phase6/clean-install.sh`, run from the repository root:

```bash
BASE_PY=<Python 3.13.5 python.exe> bash evidence/phase6/clean-install.sh
```

Its steps, each recorded with its full output and exit code in `clean-install.log`:

```text
git ls-files -o --exclude-standard -z | xargs -0 cp --parents -t <clean dir>
python -m venv .venv                                   # README install step 1 (base interpreter)
.venv/Scripts/python -m pip install -e ".[dev]"         # README install step 3 (the venv's python instead of activating it)
.venv/Scripts/python -m pip freeze --exclude-editable   # -> clean-pip-freeze.txt, diffed against requirements-lock.txt
.venv/Scripts/python -m upgrade_scout surface           # -> clean-surface.json
.venv/Scripts/python -m upgrade_scout recheck evidence/phase3/compare/0.1.8-vs-0.1.15/report.json --output clean-recheck.json
.venv/Scripts/python -m pytest -q -rs -p no:cacheprovider --basetemp <rc-pt>
.venv/Scripts/python -m pytest -q -rs -p no:cacheprovider -m "not runtime" --basetemp <rc-pt>
```

The checks ran with `OPENAI_API_KEY`, `SCOUT_LIVE_PROVIDER`, `SCOUT_LIVE_MODEL`, `OPENMINION_HOME` and
`OPENMINION_DATA_ROOT` removed from the environment. No model call was made.

## Results

| Check | Result | File |
| --- | --- | --- |
| install (`pip install -e ".[dev]"`) | exit 0. The editable install points at the clean copy; `openminion 0.1.15` was imported from the clean venv. | `clean-install.log` |
| dependency set vs `requirements-lock.txt` | identical except a patch-level drift: `pydantic 2.14.1 -> 2.14.2` and `pydantic_core 2.50.1 -> 2.50.2`, resolved from PyPI on the day. The suite passed with both: the existing `.venv` matches the lock. | `clean-pip-freeze.txt` |
| `upgrade_scout surface` | exit 0. `exports`, `sdk_version` and `signatures` are **equal** to the retained `evidence/sdk-surface-0.1.15.json`. | `clean-surface.json` |
| `upgrade_scout recheck` of the retained comparison | exit 0. Stored and recomputed: `compatible`, exit 0, complete; `verdict_changed: false`; **`matches_stored_comparison: true`** | `clean-recheck.json` |
| offline test suite | **157 passed, 2 skipped** (29.2 s). The 2 skips are the opt-in live tests (no key). | `clean-install.log` |
| offline suite without `runtime` tests | **150 passed, 2 skipped, 7 deselected** (19.6 s) | `clean-install.log` |

## Not covered here

- **`compare`:** it needs PyPI and creates per-version venvs. Its retained real runs are in `evidence/phase3/compare/`.
- **`analyze` and the live tests:** they need a provider key. They were not run, and no paid call was made.
- **Other platforms:** Linux and macOS were not tested.

## Redaction

- The script replaces the home directory with `~` in its outputs, using the tool's own `redact`.
- **Done after the run, outside the script:** `redact` does not recognize Git Bash's `/c/Users/<user>` form, so three
  log lines (two interpreter paths and one `--output` path) were rewritten to `~` with
  `sed -i 's#/c/Users/<user>#~#g' clean-install.log`. Nothing else in the log was changed.

The clean directory and its test basetemp were deleted after this record was written.
