#!/bin/bash
# Run cypress tests in parallel
# Usage: ./scripts/run-parallel.sh [threads]

set -e
cd "$(dirname "$0")/.."

THREADS=${1:-4}

# Find all spec files
SPECS=$(find cypress/e2e -name "*.cy.ts" -type f | sort | tr '\n' ' ')

SPEC_COUNT=$(echo $SPECS | wc -w)
echo "Running $SPEC_COUNT spec files in parallel with $THREADS threads..."
echo ""

npx cypress-parallel -s cypress:run -t "$THREADS" --spec $SPECS
