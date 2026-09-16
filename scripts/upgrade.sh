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

# Ask the release whether it would refuse, while the old one is still serving.
#
# Migrations are applied by the API container on start, so without this the
# answer arrives after `up -d` has replaced the stack: the API crash-loops under
# `unless-stopped`, Caddy and the frontend stay up so members get errors rather
# than a maintenance page, and the instance is down until a person resolves the
# data. The check is the same one the migration runs; only the moment changes.
#
# RUN_MIGRATIONS=0 is load-bearing, not tidiness. The api service sets it to 1
# and the image's entrypoint runs `alembic upgrade head` when it is set, so
# without the override this would apply the very migration it is checking,
# against the live database, while the old stack is still serving.
#
# A pass means no migration's declared data precondition is violated. It is not
# a promise that the upgrade will succeed — disk, lock timeouts and a bug in a
# migration are all outside what any check can see from here.
if [ -f .env ] && [ -n "$(docker compose ps --quiet db 2>/dev/null)" ]; then
    step "Pre-upgrade checks — asking $VERSION about your data"
    IMAGE_TAG="$VERSION" docker compose pull api

    set +e
    IMAGE_TAG="$VERSION" docker compose run --rm --no-deps \
        -e RUN_MIGRATIONS=0 api python -m app.cli.preflight
    preflight_status=$?
    set -e

    case "$preflight_status" in
        0) ;;
        1)  printf '\nUpgrade stopped. Nothing has been changed and the instance is\n' >&2
            printf 'still serving the version it was.\n' >&2
            exit 1 ;;
        *)  printf '\nUpgrade stopped: the checks could not be run.\n' >&2
            printf 'That is not the same as passing. Resolve the error above, or\n' >&2
            printf 'investigate before continuing.\n' >&2
            exit 1 ;;
    esac
else
    step "No running database — first install, nothing to check"
fi

step "Applying $VERSION"
install_args=(--tag "$VERSION" --upgrade)
if [ -n "${DATA_ROOT:-}" ]; then
    install_args+=(--data-root "$DATA_ROOT")
fi
if [ -n "${DOMAIN:-}" ]; then
    install_args+=(--domain "$DOMAIN")
fi
./scripts/install.sh "${install_args[@]}"

step "Verifying"
./scripts/verify-deployment.sh "$VERSION"
