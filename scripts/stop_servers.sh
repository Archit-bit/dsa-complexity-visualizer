#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/run"

stop_one() {
  local name="$1"
  local pid_file="$RUN_DIR/${name}.pid"

  if [[ ! -f "$pid_file" ]]; then
    echo "$name not running (no pid file)"
    return
  fi

  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [[ -n "${pid}" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" || true
    sleep 0.4
    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" || true
    fi
    echo "Stopped $name (pid=$pid)"
  else
    echo "$name already stopped"
  fi

  rm -f "$pid_file"
}

stop_one "complexity_web"
stop_one "visualizer_web"
