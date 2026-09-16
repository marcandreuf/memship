#!/bin/bash
# Run the cypress suite in parallel against the frontend artifact we actually ship.
#
# `next dev` compiles each route on first request. With several workers sharing
# one dev server that stall pushes navigations past their timeouts, so specs
# fail or survive only on retry, and which ones fail changes between runs.
# A production build serves prebuilt routes and removes the problem.
#
# The build is served the way `frontend/docker/Dockerfile` serves it — the
# standalone server, not `next start`. `next.config.ts` sets
# `output: "standalone"`, and Next refuses to combine that with `next start`:
# it warns and serves something no deployment runs. Assembling the layout the
# image assembles (`public/` and `.next/static/` beside the standalone root,
# then `node server.js`) is what makes a green suite evidence about the thing
# that ships rather than about a build only this script produces.
#
# Usage: ./scripts/run-parallel-prod.sh [threads]

set -e
cd "$(dirname "$0")/.."

THREADS=${1:-4}
FRONTEND_DIR="../frontend"
STANDALONE="$FRONTEND_DIR/.next/standalone"
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

  # Belt and braces: kill whatever is still listening, whoever parented it.
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

# `next build` leaves these outside the standalone root. The image copies them
# in at build time (`frontend/docker/Dockerfile`), and without them the server
# answers every asset and every static route with a 404.
echo "-> Assembling the standalone bundle..."
mkdir -p "$STANDALONE/public" "$STANDALONE/.next"
cp -r "$FRONTEND_DIR/public/." "$STANDALONE/public/" 2>/dev/null || true
rm -rf "$STANDALONE/.next/static"
cp -r "$FRONTEND_DIR/.next/static" "$STANDALONE/.next/static"

echo "-> Starting the production server on :$PORT..."
# Loopback rather than the image's 0.0.0.0 — same server and same code path,
# but a local test run has no reason to listen on the network.
(cd "$STANDALONE" && NODE_ENV=production PORT="$PORT" HOSTNAME=127.0.0.1 node server.js) &
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
