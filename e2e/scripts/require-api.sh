#!/bin/bash
#
# Refuse to start a suite run when the API is not answering.
#
# `run-parallel-prod.sh` checked that port 3000 was free, built the frontend,
# served it and waited for `/en/login` — and never checked the API. With no
# backend the whole suite runs against a frontend whose every request fails,
# and the output is a few hundred spec failures instead of one line saying what
# is wrong (#385).
#
# That is a normal state to be in rather than an exotic one: `./scripts/dev.sh
# test` runs the backend suite in a throwaway container and tears it down,
# leaving `memship-db-test` and `memship-redis` up and **no API**. Starting the
# e2e suite straight afterwards looks like a catastrophic regression.
#
# Shared by both runners so the address cannot drift between them. Sourced for
# its message as much as its check: the frontend guard beside it already tells
# the reader exactly which command to run, and this matches it.
#
#   ./scripts/require-api.sh
#
set -euo pipefail

# The same address cypress.config.ts hands the specs as `API_URL`.
API_URL="${CYPRESS_API_URL:-http://localhost:8003/api/v1}"

if ! curl -sf -o /dev/null --max-time 5 "$API_URL/health"; then
    echo "ERROR: the API is not answering at $API_URL. Start the backend first:"
    echo "  ./scripts/dev.sh start backend"
    echo ""
    echo "Running the suite without it produces a few hundred spec failures"
    echo "rather than this one line, which is why the run stops here (#385)."
    exit 1
fi
