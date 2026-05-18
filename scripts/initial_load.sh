#!/usr/bin/env bash
# One-time initial bulk load of all EPO patent data.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

if [[ -f ".venv/bin/activate" ]]; then
    source .venv/bin/activate
fi

mkdir -p logs

export PYTHONPATH="$PROJECT_ROOT/src"
python -m orchestrator.cli --mode initial 2>&1 | tee -a logs/initial_load.log
