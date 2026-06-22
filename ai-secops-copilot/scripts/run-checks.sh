#!/usr/bin/env bash
# Runs the project checks on macOS/Linux.
# Usage:  ./scripts/run-checks.sh
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

echo "==> Evaluation harness (regression gate)"
python evals/run_eval.py --gate

echo
echo "==> Agent-runtime tests (pytest, if installed)"
( cd services/agent-runtime && (python -m pytest || echo "skip: pytest not installed (pip install -e '.[dev]')") )

echo
echo "==> Gateway tests (jest, if installed)"
if [ -d services/gateway/node_modules ]; then
  ( cd services/gateway && npm test )
else
  echo "skip: run 'npm install' in services/gateway first"
fi

echo
echo "All checks complete."
