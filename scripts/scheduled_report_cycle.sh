#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

export PYTHONPATH=src

stop_collect() {
  local pid
  pid=$(ss -ltnp '( sport = :8000 )' 2>/dev/null | awk '/127.0.0.1:8000/ {print $NF}' | sed -n 's/.*pid=\([0-9]\+\).*/\1/p' | head -n1 || true)
  if [[ -n "${pid:-}" ]]; then
    kill "$pid" || true
    sleep 3
  fi
}

start_collect() {
  if ss -ltnp '( sport = :8000 )' 2>/dev/null | grep -q '127.0.0.1:8000'; then
    return 0
  fi
  nohup env PYTHONPATH=src venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > runtime/uvicorn.log 2>&1 &
  sleep 5
}

generate_reports() {
  local run_date="${1:-}"
  if [[ -n "$run_date" ]]; then
    env PYTHONPATH=src venv/bin/python -m app.cli.generate_scheduled_reports --run-date "$run_date"
  else
    env PYTHONPATH=src venv/bin/python -m app.cli.generate_scheduled_reports
  fi
}

status() {
  if ss -ltnp '( sport = :8000 )' 2>/dev/null | grep -q '127.0.0.1:8000'; then
    echo collecting
  else
    echo stopped
  fi
}

manifest() {
  cat runtime/reports/latest_manifest.json
}

case "${1:-}" in
  stop)
    stop_collect
    ;;
  start)
    start_collect
    ;;
  generate)
    generate_reports "${2:-}"
    ;;
  cycle-generate)
    stop_collect
    generate_reports "${2:-}"
    ;;
  status)
    status
    ;;
  manifest)
    manifest
    ;;
  *)
    echo "Usage: $0 {stop|start|generate [YYYY-MM-DD]|cycle-generate [YYYY-MM-DD]|status|manifest}" >&2
    exit 1
    ;;
esac
