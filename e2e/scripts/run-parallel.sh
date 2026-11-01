#!/bin/bash
# Run cypress tests in parallel
# Usage: ./scripts/run-parallel.sh [threads]
#
# `cypress/e2e/roles/` gets a worker of its own and runs serially on it.
#
# `roles-feature-flag.cy.ts` turns `features.custom_roles` off inside its tests
# and restores it only in `afterEach`. That flag is global `organization_settings`
# state, not per-worker: while it is off, `showUsersTab` in the settings page is
# false and the Accounts tab is absent for *every* session. A `role-assignment.cy.ts`
# running on another worker then times out on `cy.contains("button", "Accounts")`
# in its `beforeEach` and passes only on retry — observed 2026-09-16, the two
# specs overlapping between 08:27:57 and 08:28:20. See #58 and #117.
#
# Nothing outside `roles/` reads the flag, so confining that directory to a
# single serial worker is enough; the rest of the suite keeps the remaining
# threads and the wall clock is unchanged.
#
# The run fails if it leaves any screenshot. See `finish()` below.

set -e
cd "$(dirname "$0")/.."

THREADS=${1:-4}
SHOTS="cypress/screenshots"
BACKEND_COMPOSE="../backend/docker/docker-compose.yml"

# Every run starts from a freshly seeded dataset (#461). The seed writes
# registration windows relative to seed time and its "already seeded" guards
# never touch them again, so a reused database ages until the windows close and
# the eligibility specs fail on correct behaviour. A `seed demo` in between also
# replaces the fixed e2e passwords, after which every login fails and the
# per-address login throttle takes the whole suite down in `before each`.
# Reseeding removes both, and the accumulation across runs in #117 with them.
#
# This deletes the club data in the dev database. Super admins, system roles and
# payment providers survive. Set E2E_KEEP_DATA=1 to run against the data as is.
if [ "${E2E_KEEP_DATA:-0}" != "1" ]; then
  echo "-> Rebuilding the e2e dataset (seed --test --reset-club-data)..."
  SEED_LOG=$(mktemp -t e2e-seed-XXXXXX.log)
  if ! docker compose -f "$BACKEND_COMPOSE" exec -T api \
      python -m app.cli.seed --test --reset-club-data > "$SEED_LOG" 2>&1; then
    cat "$SEED_LOG"
    rm -f "$SEED_LOG"
    echo ""
    echo "ERROR: could not rebuild the e2e dataset. Is the backend running?"
    echo "  ./scripts/dev.sh start backend"
    echo "Or run against the current data with E2E_KEEP_DATA=1."
    exit 1
  fi
  grep -E "^  Deleted " "$SEED_LOG" || true
  rm -f "$SEED_LOG"
  echo ""
fi

# Cleared first so a previous run's screenshots cannot condemn this one.
rm -rf "$SHOTS"

# A test that fails and then passes on retry leaves a screenshot and nothing
# else. Its spec still reports `Failing: 0`, every worker still prints "All
# specs passed!", and the exit code is still 0 — the summary and the status
# agree on a pass that did not happen. That is how the shared-state collision
# in #117 stayed invisible: the only evidence the whole run produced was a file
# on disk that nothing looked at.
#
# So screenshots are part of the verdict, not a debugging aid. A file with no
# "attempt N" suffix is a retry-only pass, which is a failure to explain.
finish() {
  local code=$1
  if [ -d "$SHOTS" ] && [ -n "$(find "$SHOTS" -type f -print -quit 2>/dev/null)" ]; then
    echo ""
    echo "ERROR: the run left screenshots, so at least one test failed at least once."
    echo "A name with no 'attempt N' suffix failed and then passed on retry, which"
    echo "the summary above reports as a pass. Treat it as a failure to explain."
    echo ""
    find "$SHOTS" -type f | sed 's/^/  /'
    if [ "$code" -eq 0 ]; then
      code=1
    fi
  fi
  exit "$code"
}

ROLES_SPECS=$(find cypress/e2e/roles -name "*.cy.ts" -type f 2>/dev/null | sort | tr '\n' ' ')
POOL_SPECS=$(find cypress/e2e -name "*.cy.ts" -type f -not -path "cypress/e2e/roles/*" | sort | tr '\n' ' ')

ROLES_COUNT=$(echo $ROLES_SPECS | wc -w)
POOL_COUNT=$(echo $POOL_SPECS | wc -w)

# One thread means one process: hand everything to the pool, where the roles
# specs are serial with the rest by construction.
if [ "$THREADS" -le 1 ] || [ "$ROLES_COUNT" -eq 0 ]; then
  ALL_SPECS=$(find cypress/e2e -name "*.cy.ts" -type f | sort | tr '\n' ' ')
  echo "Running $(echo $ALL_SPECS | wc -w) spec files with $THREADS thread(s)..."
  echo ""
  set +e
  npx cypress-parallel -s cypress:run -t "$THREADS" --spec $ALL_SPECS
  ALL_EXIT=$?
  set -e
  finish "$ALL_EXIT"
fi

POOL_THREADS=$((THREADS - 1))
ROLES_LOG=$(mktemp -t cypress-roles-XXXXXX.log)

echo "Running $POOL_COUNT spec files in parallel with $POOL_THREADS threads,"
echo "plus $ROLES_COUNT roles spec files serially on a pinned worker..."
echo ""

# Started first so cypress-parallel's own `cleanResultsPath()` cannot race the
# pinned worker. The pinned worker deliberately uses cypress's default reporter:
# cypress-parallel's reporters write `runner-results/` and the weights file from
# `$PWD`, and a second writer there would corrupt the pool's summary.
(
  sleep 2
  npx cypress run --spec "$(echo $ROLES_SPECS | tr ' ' ',')"
) > "$ROLES_LOG" 2>&1 &
ROLES_PID=$!

set +e
npx cypress-parallel -s cypress:run -t "$POOL_THREADS" --spec $POOL_SPECS
POOL_EXIT=$?

wait "$ROLES_PID"
ROLES_EXIT=$?
set -e

echo ""
echo "===================== pinned roles worker ====================="
cat "$ROLES_LOG"
rm -f "$ROLES_LOG"

if [ "$POOL_EXIT" -ne 0 ]; then
  finish "$POOL_EXIT"
fi
finish "$ROLES_EXIT"
