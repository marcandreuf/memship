#!/usr/bin/env bash
#
# memship — install or upgrade an instance to a given version, and verify it.
#
#   ./scripts/upgrade.sh 2.7.0
#
# This is the whole upgrade procedure in one command: snapshot, apply, check.
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

# Snapshot before anything touches the database. A release that carries a schema
# migration cannot be rolled back by re-pinning IMAGE_TAG — the images go back,
# the migrated schema does not — so this snapshot is the only way out of a bad
# upgrade. If it fails, the upgrade does not happen.
#
# It is NOT a backup in the sense that matters for losing the host: db-backup.sh
# writes into $MEMSHIP_DATA_ROOT/backups, on this machine, beside the database it
# just dumped. It also captures no uploads and no .env. Saying "backing up" here
# would let a green deploy log stand in for disaster recovery, which it is not.
if [ -f .env ] && [ -n "$(docker compose ps --quiet db 2>/dev/null)" ]; then
    step "Pre-upgrade snapshot — rollback cover only, stays on this host"
    ./scripts/db-backup.sh
    printf '  This protects against a bad migration, not against losing this\n'
    printf '  machine. Off-host copies: docs/self-hosting/backups-and-restore.md\n'
else
    step "No running database — first install, nothing to snapshot"
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
