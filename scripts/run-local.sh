#!/usr/bin/env bash
#
# run-local.sh — run CodeGuardian against a local git repo with NO GitHub token.
#
# This is the fastest way to *test* CodeGuardian: it runs the exact same
# entrypoint the Action runs (`python -m codeguardian`) in deterministic mode,
# computes the diff between two commits, and writes the report locally instead
# of posting to GitHub. No secrets, no network, no PR required.
#
# Usage:
#   scripts/run-local.sh [TARGET_REPO] [BASE_REF] [HEAD_REF]
#
#   TARGET_REPO  path to the git repo to analyze   (default: current directory)
#   BASE_REF     base commit/branch                (default: HEAD~1)
#   HEAD_REF     head commit/branch                (default: HEAD)
#
# Examples:
#   scripts/run-local.sh                      # analyze the last commit of cwd
#   scripts/run-local.sh ~/code/myapp main feature/login
#
# Output: prints the risk line + writes codeguardian-report.{json,md} and a job
# summary under a temp dir (path printed at the end).

set -euo pipefail

TARGET_REPO="${1:-$(pwd)}"
BASE_REF="${2:-HEAD~1}"
HEAD_REF="${3:-HEAD}"

# Resolve where CodeGuardian itself lives (the dir containing this script's repo).
CG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Pick a python: prefer CodeGuardian's venv, else `python3`.
if [[ -x "$CG_DIR/.venv/bin/python" ]]; then
  PY="$CG_DIR/.venv/bin/python"
else
  PY="python3"
fi

# Make sure CodeGuardian is importable (installed, or run from source).
if ! "$PY" -c "import codeguardian" 2>/dev/null; then
  export PYTHONPATH="$CG_DIR/src:${PYTHONPATH:-}"
fi

TARGET_REPO="$(cd "$TARGET_REPO" && pwd)"
BASE_SHA="$(git -C "$TARGET_REPO" rev-parse "$BASE_REF")"
HEAD_SHA="$(git -C "$TARGET_REPO" rev-parse "$HEAD_REF")"

OUT_DIR="$(mktemp -d)"
EVENT_PATH="$OUT_DIR/event.json"
REPO_FULL="local/$(basename "$TARGET_REPO")"

cat > "$EVENT_PATH" <<JSON
{
  "number": 1,
  "pull_request": {
    "number": 1,
    "title": "local run ${BASE_REF}...${HEAD_REF}",
    "base": { "sha": "${BASE_SHA}", "repo": { "full_name": "${REPO_FULL}" } },
    "head": { "sha": "${HEAD_SHA}", "repo": { "full_name": "${REPO_FULL}" } }
  }
}
JSON

echo "Analyzing ${REPO_FULL}  (${BASE_SHA:0:7}...${HEAD_SHA:0:7})"
echo

GITHUB_EVENT_PATH="$EVENT_PATH" \
GITHUB_EVENT_NAME="pull_request" \
GITHUB_REPOSITORY="$REPO_FULL" \
GITHUB_WORKSPACE="$TARGET_REPO" \
CODEGUARDIAN_OUT="$OUT_DIR" \
GITHUB_STEP_SUMMARY="$OUT_DIR/summary.md" \
  "$PY" -m codeguardian

echo
echo "Report written to: $OUT_DIR"
echo "  - $OUT_DIR/codeguardian-report.json"
echo "  - $OUT_DIR/codeguardian-report.md"
echo "  - $OUT_DIR/summary.md   (GitHub job-summary preview)"
