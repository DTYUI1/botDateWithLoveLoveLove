#!/usr/bin/env bash
# Засидить БД фейковыми кандидатами для нагрузочного теста.
# Использует tests/load/seed_load_data.py.

set -euo pipefail

COUNT="${1:-100}"
REQUESTERS="${2:-0}"
LOG_DIR="$(dirname "$0")/results"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/seed.log"
PYTHON_BIN="${PYTHON_BIN:-}"

if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x ".venv/bin/python" ]]; then
    PYTHON_BIN=".venv/bin/python"
  else
    PYTHON_BIN="python"
  fi
fi

if [[ -z "${DATABASE_URL:-}" ]] && docker compose ps backend --status running >/dev/null 2>&1; then
  BACKEND_DATABASE_URL="$(docker compose exec -T backend printenv DATABASE_URL 2>/dev/null || true)"
  if [[ -n "$BACKEND_DATABASE_URL" ]]; then
    export DATABASE_URL="${BACKEND_DATABASE_URL/@db:/@localhost:}"
  fi
fi

echo "[seed] создаём $COUNT load-test кандидатов и $REQUESTERS requester-профилей → $LOG_FILE"
DEBUG=false PYTHONPATH=backend:. "$PYTHON_BIN" tests/load/seed_load_data.py \
  --count "$COUNT" \
  --requesters "$REQUESTERS" 2>&1 | tee "$LOG_FILE"
echo "[seed] готово ($(wc -l < "$LOG_FILE") строк в логе)"
