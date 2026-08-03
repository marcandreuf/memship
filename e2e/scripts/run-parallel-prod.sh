#!/bin/bash
# Run the cypress suite in parallel against a production frontend build.
#
# `next dev` compiles each route on first request. With several workers sharing
# one dev server that stall pushes navigations past their timeouts, so specs
# fail or survive only on retry, and which ones fail changes between runs.
# A production build serves prebuilt routes and removes the problem.
#
# Usage: ./scripts/run-parallel-prod.sh [threads]

set -e
cd "$(dirname "$0")/.."

THREADS=${1:-4}
FRONTEND_DIR="../frontend"
PORT=3000
SERVER_PID=""

# `lsof` cannot see the listener in every environment, so ask `ss` first and
# fall back to an actual request.
port_in_use() {
  if command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | grep -q ":$PORT "; then
    return 0
  fi
  curl -sf -o /dev/null --max-time 2 "http://localhost:$PORT/" 2>/dev/null
}

listeners_on_port() {
  ss -ltnp 2>/dev/null | grep ":$PORT " | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u
}

cleanup() {
  [ -n "$SERVER_PID" ] || return 0
  echo "-> Stopping production server (PID: $SERVER_PID)..."
  pkill -P "$SERVER_PID" 2>/dev/null || true
  kill "$SERVER_PID" 2>/dev/null || true
  wait "$SERVER_PID" 2>/dev/null || true

  # `pnpm start` re-parents `next-server`, so the port can still be held once
  # the wrapper is gone. Kill whatever is actually still listening.
  for _ in $(seq 1 10); do
    port_in_use || return 0
    for p in $(listeners_on_port); do
      kill "$p" 2>/dev/null || true
    done
    sleep 1
  done

  port_in_use && echo "WARNING: port $PORT is still held after teardown." || true
  return 0
}
trap cleanup EXIT INT TERM

if port_in_use; then
  echo "ERROR: port $PORT is already in use. Stop the dev server first:"
  echo "  ./scripts/dev.sh stop frontend"
  exit 1
fi

echo "-> Building the frontend..."
(cd "$FRONTEND_DIR" && pnpm build)

echo "-> Starting the production server on :$PORT..."
(cd "$FRONTEND_DIR" && pnpm start) &
SERVER_PID=$!

echo "-> Waiting for the server to accept requests..."
for _ in $(seq 1 60); do
  if curl -sf -o /dev/null "http://localhost:$PORT/en/login"; then
    echo "-> Server is up."
    break
  fi
  sleep 2
done

if ! curl -sf -o /dev/null "http://localhost:$PORT/en/login"; then
  echo "ERROR: the production server did not come up on :$PORT."
  exit 1
fi

# Report the suite's own result — the EXIT trap must not mask it.
set +e
./scripts/run-parallel.sh "$THREADS"
SUITE_EXIT=$?
set -e

exit "$SUITE_EXIT"
