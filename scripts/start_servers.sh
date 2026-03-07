#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/run"
LOG_DIR="$ROOT_DIR/logs"

mkdir -p "$RUN_DIR" "$LOG_DIR"

start_one() {
  local name="$1"
  local cmd="$2"
  local pid_file="$RUN_DIR/${name}.pid"
  local log_file="$LOG_DIR/${name}.log"

  if [[ -f "$pid_file" ]]; then
    local old_pid
    old_pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "${old_pid}" ]] && kill -0 "$old_pid" 2>/dev/null; then
      echo "$name already running (pid=$old_pid)"
      return
    fi
    rm -f "$pid_file"
  fi

  nohup bash -lc "$cmd" > "$log_file" 2>&1 &
  local new_pid=$!
  echo "$new_pid" > "$pid_file"
  echo "Started $name (pid=$new_pid, log=$log_file)"
}

start_one "complexity_web" "python3 '$ROOT_DIR/web_app/server.py'"
start_one "visualizer_web" "python3 '$ROOT_DIR/visualizer_app/server.py'"
