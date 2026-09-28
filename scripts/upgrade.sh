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
# Part of a release ships beside the images rather than inside them, so this
# refuses to run when the deployment files in this directory are not the ones
# from the version being applied — that is an upgrade whose first step was
# skipped, and nothing downstream can see it. --skip-file-check proceeds anyway,
# for a deployment that maintains those files itself.
#
# Keep DATA_ROOT OUTSIDE this directory. Deployments deliver files here by
# copying over the top of it, and persistent data must never sit in the path
# something might one day mirror or clean.

set -euo pipefail

ALLOW_DOWNGRADE=0
SKIP_FILE_CHECK=0
VERSION=""
while [ $# -gt 0 ]; do
    case "$1" in
        --allow-downgrade) ALLOW_DOWNGRADE=1; shift ;;
        --skip-file-check) SKIP_FILE_CHECK=1; shift ;;
        -*) printf 'unknown option: %s\n' "$1" >&2; exit 2 ;;
        *)  VERSION="$1"; shift ;;
    esac
done
[ -n "$VERSION" ] || {
    printf 'usage: upgrade.sh <version> [--allow-downgrade] [--skip-file-check]\n' >&2
    exit 2
}
VERSION="${VERSION#v}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

step() { printf '\n==> %s\n' "$*"; }

current_tag() {
    [ -f .env ] || return 0
    grep -E '^IMAGE_TAG=' .env | tail -1 | cut -d= -f2- || true
}

is_release() { printf '%s' "$1" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; }

# Images go back; a migrated schema does not. Rolling back a release that
# migrated needs a restore from the pre-upgrade snapshot, which this script
# cannot do for you — so going backwards is refused rather than half-performed.
#
# Only compared between two release versions. An RC or a `latest` install has no
# ordering to reason about, so it is left alone rather than guessed at.
CURRENT="$(current_tag)"
if [ "$ALLOW_DOWNGRADE" -eq 0 ] && is_release "$CURRENT" && is_release "$VERSION" \
        && [ "$CURRENT" != "$VERSION" ]; then
    OLDER="$(printf '%s\n%s\n' "$CURRENT" "$VERSION" | sort -V | head -1)"
    if [ "$OLDER" = "$VERSION" ]; then
        printf '\nRefusing to downgrade: this instance runs %s, you asked for %s.\n\n' \
            "$CURRENT" "$VERSION" >&2
        printf '  Re-pinning IMAGE_TAG moves the images back. It does not move the\n' >&2
        printf '  database back: a release that ran a migration has already changed\n' >&2
        printf '  the schema, and %s will not understand it.\n\n' "$VERSION" >&2
        printf '  To go back, restore the snapshot taken before you upgraded to %s:\n' "$CURRENT" >&2
        printf '    docs/self-hosting/backups-and-restore.md\n\n' >&2
        printf '  If you know this release carried no migration, or you have already\n' >&2
        printf '  restored the database, pass --allow-downgrade.\n' >&2
        exit 1
    fi
fi

# Every image, not only the one the data check runs from, and before anything
# else on the instance. install.sh pulls after it has recreated the stack, so a
# version that does not exist, or a release whose images did not all publish,
# used to take the instance down and only then fail. Pulling here means a bad
# tag is an upgrade that declines while the old one keeps serving, and it is not
# wasted work: install.sh finds these already local a moment later.
#
# It runs before the snapshot, so an upgrade that never starts leaves no dump
# behind, and before the deployment-file check below, which reads what this
# release expects out of the image it has just fetched.
step "Fetching the $VERSION images"
PULL_LOG="$(mktemp)"
trap 'rm -f "$PULL_LOG"' EXIT
set +e
IMAGE_TAG="$VERSION" docker compose pull --quiet >"$PULL_LOG" 2>&1
pull_status=$?
set -e
if [ "$pull_status" -ne 0 ]; then
    printf '\nUpgrade stopped: could not fetch every image for %s.\n\n' "$VERSION" >&2
    # Compose answers a failed pull by advising `docker compose build`, which on
    # a deployment either fails for want of a source tree or builds an image no
    # release ever published. Ours is the only advice worth following here.
    grep -v 'must be built from source' <"$PULL_LOG" | sed 's/^/  /' >&2 || true
    printf '\n  Check the version exists, and that this host can reach the\n' >&2
    printf '  registry. Nothing has been changed and the instance is still\n' >&2
    printf '  serving %s.\n' "${CURRENT:-the version it was on}" >&2
    exit 1
fi
printf '  pulled\n'

# Part of a release ships here beside the images rather than inside them:
# docker-compose.yml and the Caddyfile are read from this directory every time
# the stack comes up. Applying a version without refreshing them first — step one
# of the documented procedure — leaves the new backend running behind the old
# proxy configuration, and nothing downstream can tell: verify-deployment.sh asks
# the API its version, which comes from IMAGE_TAG, so a half-upgrade reports
# success just as loudly as a whole one.
#
# What the release expects those files to be travels in the image, as a label
# written when it was built, and is read back out of the copy just pulled. So
# the registry is the only thing this needs to reach — which an upgrade needs
# anyway. An earlier version of this check fetched the files from
# raw.githubusercontent.com, which made every upgrade depend on a host being
# able to reach GitHub, and turned a GitHub outage into an upgrade that stops.
#
# Checksums rather than a version stamp inside the files: a stamp is a second
# source of truth that has to be rewritten every release and is wrong on main in
# between.
#
# Three consequences worth naming. Files that did not change between two
# releases have the same checksum, so this says nothing on an upgrade whose
# deployment assets are identical — the common case, and it must not need the
# escape hatch. A release built before the label existed carries nothing to
# compare against, and is reported and allowed rather than refused, so older
# releases stay installable. And scripts/ ships beside the images too but is
# deliberately not checked: this script lives there, so it would be judging its
# own freshness, and a stale script is not the thing that silently breaks an
# instance. A stale proxy configuration is.
DEPLOYMENT_LABEL="org.memship.deployment-files"

STALE=""
MISSING=""
CHECKED=""

# The image the label is read from. Resolved through the on-disk compose file,
# which may itself be the stale thing being looked for — that is fine: the image
# name has to survive for the pull above to have worked at all, and if it did
# not, this stops at the pull rather than here.
API_IMAGE_REF="$(IMAGE_TAG="$VERSION" docker compose config --images 2>/dev/null \
    | grep 'memship-backend' | head -1 || true)"

# 0 everything matches, 1 something is stale or missing, 2 this release carries
# no manifest to compare against.
check_deployment_files() {
    local manifest entry f want got
    manifest="$(docker image inspect \
        --format "{{ index .Config.Labels \"$DEPLOYMENT_LABEL\" }}" \
        "$1" 2>/dev/null || true)"
    case "$manifest" in
        ''|'<no value>') return 2 ;;
    esac
    for entry in $manifest; do
        f="${entry%%:*}"
        want="${entry##*:}"
        CHECKED="$CHECKED $f"
        if [ ! -f "$f" ]; then
            MISSING="$MISSING $f"
            continue
        fi
        got="$(sha256sum <"$f" | cut -d' ' -f1)"
        [ "$got" = "$want" ] || STALE="$STALE $f"
    done
    [ -z "$MISSING$STALE" ] || return 1
    return 0
}

# Only between release versions. `latest` and an RC tag are not a release whose
# deployment files anyone can name.
if [ "$SKIP_FILE_CHECK" -eq 0 ] && is_release "$VERSION" && [ -n "$API_IMAGE_REF" ]; then
    step "Checking the deployment files are $VERSION's"
    set +e
    check_deployment_files "$API_IMAGE_REF"
    file_status=$?
    set -e

    case "$file_status" in
        0)  printf ' %s — as shipped in %s\n' "$CHECKED" "$VERSION" ;;
        2)  printf '  %s carries no deployment manifest, so there is nothing to\n' "$VERSION" >&2
            printf '  compare against. Releases built before this check existed do\n' >&2
            printf '  not have one. Continuing.\n' >&2 ;;
        *)  printf '\nUpgrade stopped: the deployment files here are not %s'"'"'s.\n\n' "$VERSION" >&2
            [ -z "$STALE" ]   || printf '  stale:%s\n' "$STALE" >&2
            [ -z "$MISSING" ] || printf '  missing:%s\n' "$MISSING" >&2
            printf '\n  Part of a release ships here beside the images — this Compose\n' >&2
            printf '  file and the Caddyfile — and the stack reads them from this\n' >&2
            printf '  directory every time it comes up. Applying %s over the top of\n' "$VERSION" >&2
            printf '  the previous release'"'"'s copies leaves the new backend running\n' >&2
            printf '  behind the old proxy configuration, and the verification at the\n' >&2
            printf '  end cannot see it: the API reports IMAGE_TAG, which would be\n' >&2
            printf '  right either way.\n\n' >&2
            printf '  Refresh this directory from the release, then run this again:\n\n' >&2
            printf '    curl -fsSL "https://github.com/marcandreuf/memship/archive/refs/tags/v%s.tar.gz" \\\n' "$VERSION" >&2
            printf '      | tar -xz -C %s --strip-components=1\n\n' "$REPO_ROOT" >&2
            printf '  Nothing has been changed and the instance is still serving %s.\n\n' \
                "${CURRENT:-the version it was on}" >&2
            printf '  If you maintain these files yourself, pass --skip-file-check.\n' >&2
            exit 1 ;;
    esac
fi

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
    step "Pre-upgrade checks — $VERSION"

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
