#!/usr/bin/env bash
# Pre-commit CI checks — mirrors .github/workflows/{backend,frontend}-ci.yml lint jobs
# Called by Claude Code PreToolUse hook before git commit/push.
# Reads tool input JSON from stdin, exits 1 to block if checks fail.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
API_DIR="$REPO_ROOT/simplydigitals-aiarbitrageur-api"
UI_DIR="$REPO_ROOT/simplydigitals-aiarbitrageur-ui"

# Parse the bash command from Claude's tool input JSON
COMMAND=$(python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('command',''))" 2>/dev/null || echo "")

# Only intercept git commit/push
if ! echo "$COMMAND" | grep -qE '^git (commit|push)'; then
  exit 0
fi

echo "--- Running CI lint checks before git operation ---"
FAILED=0

# Determine which parts are staged/affected
STAGED=$(git -C "$REPO_ROOT" diff --cached --name-only 2>/dev/null || echo "")

run_backend_checks() {
  echo "[backend] Running ruff..."
  (cd "$API_DIR" && source .venv/bin/activate 2>/dev/null && ruff check . --select E,W,F,I,B,UP,N,ANN) || { echo "[backend] ruff FAILED"; return 1; }
  echo "[backend] Running mypy..."
  (cd "$API_DIR" && source .venv/bin/activate 2>/dev/null && mypy app/) || { echo "[backend] mypy FAILED"; return 1; }
  echo "[backend] OK"
}

run_frontend_checks() {
  echo "[frontend] Running ESLint..."
  (cd "$UI_DIR" && npm run lint --silent) || { echo "[frontend] ESLint FAILED"; return 1; }
  echo "[frontend] Running Prettier check..."
  (cd "$UI_DIR" && npm run format:check --silent) || { echo "[frontend] Prettier FAILED"; return 1; }
  echo "[frontend] OK"
}

if echo "$STAGED" | grep -q "simplydigitals-aiarbitrageur-api/"; then
  run_backend_checks || FAILED=1
fi

if echo "$STAGED" | grep -q "simplydigitals-aiarbitrageur-ui/"; then
  run_frontend_checks || FAILED=1
fi

if [ $FAILED -ne 0 ]; then
  echo ""
  echo "CI checks FAILED — fix the issues above before committing."
  exit 1
fi

echo "--- All CI checks passed ---"
exit 0
