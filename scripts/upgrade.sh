#!/usr/bin/env bash
#
# memship — install or upgrade an instance to a given version, and verify it.
#
#   ./scripts/upgrade.sh 2.7.0
#
# This is the whole upgrade procedure in one command: back up, apply, check.
# Run it by hand on the host, or let the deploy workflow run it for you — both
# do exactly the same thing, which is the point. What is automated and what an
# operator types must not drift apart.
#
# On a first install there is nothing to back up and no .env yet, so pass the
# two things install.sh needs to create one:
#
#   DOMAIN=memship.example.org DATA_ROOT=/home/you/memship-data ./scripts/upgrade.sh 2.7.0
#
# On an upgrade both are read from the existing .env and can be omitted; it
# never overwrites a .env that exists.
#
# Keep DATA_ROOT OUTSIDE this directory. Deployments deliver files here by
# copying over the top of it, and persistent data must never sit in the path
# something might one day mirror or clean.

set -euo pipefail

VERSION="${1:?usage: upgrade.sh <version>, e.g. 2.7.0}"
VERSION="${VERSION#v}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

step() { printf '\n==> %s\n' "$*"; }

# Back up before anything touches the database. A release that carries a schema
# migration cannot be rolled back by re-pinning IMAGE_TAG — the images go back,
# the migrated schema does not — so this backup is the only way out of a bad
# upgrade. If it fails, the upgrade does not happen.
if [ -f .env ] && [ -n "$(docker compose ps --quiet db 2>/dev/null)" ]; then
    step "Backing up the database"
    ./scripts/db-backup.sh
else
    step "No running database — treating this as a first install, nothing to back up"
fi

step "Applying $VERSION"
install_args=(--tag "$VERSION")
if [ -n "${DATA_ROOT:-}" ]; then
    install_args+=(--data-root "$DATA_ROOT")
fi
if [ -n "${DOMAIN:-}" ]; then
    install_args+=(--domain "$DOMAIN")
fi
./scripts/install.sh "${install_args[@]}"

step "Verifying"
./scripts/verify-deployment.sh "$VERSION"
