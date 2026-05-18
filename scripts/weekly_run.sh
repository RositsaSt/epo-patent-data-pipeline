#!/usr/bin/env bash
# Weekly EPO patent data pipeline runner.
# Intended to be called from cron:
#   0 2 * * 1 /absolute/path/to/scripts/weekly_run.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

if [[ -f ".venv/bin/activate" ]]; then
    source .venv/bin/activate
fi

mkdir -p logs

export PYTHONPATH="$PROJECT_ROOT/src"
python -m orchestrator.cli --mode weekly 2>&1 | tee -a logs/cron.log
