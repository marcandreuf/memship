#!/usr/bin/env bash
#
# The deployment scripts' shell tests.
#
#   ./tests/shell/run.sh                        # every file
#   ./tests/shell/run.sh test-upgrade-guards.sh # one of them
#   KEEP_SANDBOX=1 ./tests/shell/run.sh         # keep the scratch dirs to read
#
# These exercise scripts/install.sh and scripts/upgrade.sh — the guards that keep
# an upgrade from becoming an outage — against a stub `docker`. They need bash
# and nothing else: no bats, no containers, no network, no database. See lib.sh
# for why, and for what the harness gives a test file.
#
# `shellcheck` runs alongside these in CI, over the same scripts. It is a
# different question (is this bash correct) from the one here (does this logic
# hold), and both are cheap.

set -uo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" || exit 1

if [ $# -gt 0 ]; then
    FILES=("$@")
else
    FILES=(test-*.sh)
fi

failed=0
for file in "${FILES[@]}"; do
    printf '\n=== %s ===\n' "$file"
    bash "$file" || failed=1
done

if [ "$failed" -ne 0 ]; then
    printf '\nshell tests FAILED\n' >&2
    exit 1
fi
printf '\nshell tests passed\n'
