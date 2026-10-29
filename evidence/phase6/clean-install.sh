#!/usr/bin/env bash
# Phase 6 clean-install reproducibility check (Windows 11, Git Bash). Offline except for the pip install.
#
# Copies exactly the files a first commit would contain (untracked, not ignored by .gitignore) to a new
# short directory, creates a fresh venv there with the README's install command, then runs `surface`,
# `recheck` of the retained Phase 3 comparison, and the offline test suite. The existing .venv and the
# per-version comparison venvs are not used or changed. No model call is made: provider keys are removed
# from the environment, so the two opt-in live tests skip.
#
# usage, from the repository root:  BASE_PY=<python 3.11+ exe> bash evidence/phase6/clean-install.sh
set -u
REPO="$(pwd)"
OUT="$REPO/evidence/phase6"
DEST_WIN="${LOCALAPPDATA}\\mus\\rc"
PT_WIN="${LOCALAPPDATA}\\mus\\rc-pt"
DEST="$(cygpath -u "$DEST_WIN")"
LOG="$OUT/clean-install.log"
: "${BASE_PY:?set BASE_PY to a Python 3.11+ interpreter}"
if [ -e "$DEST" ]; then echo "refusing: $DEST_WIN already exists" >&2; exit 2; fi

run() {  # record the exact command, its output and its exit code
  echo "\$ $*" >> "$LOG"
  "$@" >> "$LOG" 2>&1
  local code=$?
  echo "[exit $code]" >> "$LOG"
  echo >> "$LOG"
  return 0
}

: > "$LOG"
echo "# clean install, started $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"
run cmd //c ver
run "$BASE_PY" --version
run git --version
echo "\$ git status (summary)" >> "$LOG"
git rev-parse --verify HEAD >> "$LOG" 2>&1 || echo "no commits yet" >> "$LOG"
echo "files a first commit would contain: $(git ls-files -o --exclude-standard | wc -l)" >> "$LOG"
echo >> "$LOG"

# 1. a fresh copy of the would-be-committed tree
mkdir -p "$DEST"
echo "\$ git ls-files -o --exclude-standard -z | xargs -0 cp --parents -t <DEST>" >> "$LOG"
git ls-files -o --exclude-standard -z | xargs -0 cp --parents -t "$DEST"
echo "[exit $?] copied $(find "$DEST" -type f | wc -l) files" >> "$LOG"
echo >> "$LOG"
cd "$DEST" || exit 2
run sha256sum evidence/phase3/compare/0.1.8-vs-0.1.15/report.json

# 2. the README's install steps (the venv's python is called directly instead of activating the venv)
run "$BASE_PY" -m venv .venv
run .venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pip freeze --exclude-editable > "$OUT/clean-pip-freeze.txt" 2>&1
echo "\$ python -m pip freeze --exclude-editable > evidence/phase6/clean-pip-freeze.txt  [exit $?]" >> "$LOG"
echo "\$ diff requirements-lock.txt clean-pip-freeze.txt" >> "$LOG"
diff requirements-lock.txt "$OUT/clean-pip-freeze.txt" >> "$LOG" 2>&1 && echo "identical to requirements-lock.txt" >> "$LOG"
echo >> "$LOG"
run .venv/Scripts/python -c "import sys, openminion, upgrade_scout, pydantic; print(sys.version); print('openminion', openminion.__version__, openminion.__file__); print('upgrade_scout', upgrade_scout.__version__, upgrade_scout.__file__); print('pydantic', pydantic.VERSION)"
run .venv/Scripts/python -m pip --version

# 3. the checks
clean_env=(env -u OPENAI_API_KEY -u SCOUT_LIVE_PROVIDER -u SCOUT_LIVE_MODEL -u OPENMINION_HOME -u OPENMINION_DATA_ROOT)
echo "\$ python -m upgrade_scout surface > evidence/phase6/clean-surface.json" >> "$LOG"
"${clean_env[@]}" .venv/Scripts/python -m upgrade_scout surface > "$OUT/clean-surface.json" 2>> "$LOG"
echo "[exit $?]" >> "$LOG"; echo >> "$LOG"
run "${clean_env[@]}" .venv/Scripts/python -m upgrade_scout recheck evidence/phase3/compare/0.1.8-vs-0.1.15/report.json --output "$OUT/clean-recheck.json"
run "${clean_env[@]}" .venv/Scripts/python -m pytest -q -rs -p no:cacheprovider --basetemp "$PT_WIN"
run "${clean_env[@]}" .venv/Scripts/python -m pytest -q -rs -p no:cacheprovider -m "not runtime" --basetemp "$PT_WIN"
echo "# finished $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"

# home paths in the saved outputs become ~ (the same redaction the tool applies to its reports)
.venv/Scripts/python -c "
import sys
from pathlib import Path
from upgrade_scout.probe import redact
for name in sys.argv[1:]:
    path = Path(name)
    path.write_text(redact(path.read_text(encoding='utf-8', errors='replace')), encoding='utf-8')
" "$LOG" "$OUT/clean-surface.json" "$OUT/clean-recheck.json" "$OUT/clean-pip-freeze.txt"
