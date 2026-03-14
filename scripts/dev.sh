#!/usr/bin/env bash
set -euo pipefail

# Start or stop the frontend dev server.
# Usage: ./scripts/dev.sh [start|stop]

FRONTEND_DIR="$(cd "$(dirname "$0")/../frontend" && pwd)"
PID_FILE="/tmp/memship-frontend-dev.pid"

case "${1:-start}" in
  start)
    if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
      echo "Frontend dev server already running (PID $(cat "$PID_FILE"))"
      exit 0
    fi

    if [[ ! -d "$FRONTEND_DIR" ]]; then
      echo "ERROR: frontend/ directory not found" >&2
      exit 1
    fi

    cd "$FRONTEND_DIR"

    if [[ ! -d "node_modules" ]]; then
      echo "Installing dependencies..."
      pnpm install
    fi

    echo "Starting frontend dev server..."
    pnpm dev &
    echo $! > "$PID_FILE"
    echo "Frontend dev server started (PID $!)"
    echo "Open http://localhost:3000"
    ;;

  stop)
    if [[ -f "$PID_FILE" ]]; then
      PID=$(cat "$PID_FILE")
      if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "Frontend dev server stopped (PID $PID)"
      else
        echo "Process $PID not running"
      fi
      rm -f "$PID_FILE"
    else
      echo "No PID file found. Server may not be running."
    fi
    ;;

  *)
    echo "Usage: $0 [start|stop]" >&2
    exit 1
    ;;
esac
