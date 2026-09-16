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

set -e
cd "$(dirname "$0")/.."

THREADS=${1:-4}

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
  exec npx cypress-parallel -s cypress:run -t "$THREADS" --spec $ALL_SPECS
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
  exit "$POOL_EXIT"
fi
exit "$ROLES_EXIT"
