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
# Everything this checks, it checks before anything on the instance is replaced,
# and each refusal names the state it found: the version going backwards, the
# settings .env is missing, the free disk against what is wanted, the deployment
# files' checksums, and what the release's own migrations say about the data.
# --skip-disk-check is the escape hatch for a host whose storage df misreports.
#
# Keep DATA_ROOT OUTSIDE this directory. Deployments deliver files here by
# copying over the top of it, and persistent data must never sit in the path
# something might one day mirror or clean.

set -euo pipefail

ALLOW_DOWNGRADE=0
SKIP_FILE_CHECK=0
SKIP_DISK_CHECK=0
VERSION=""
while [ $# -gt 0 ]; do
    case "$1" in
        --allow-downgrade) ALLOW_DOWNGRADE=1; shift ;;
        --skip-file-check) SKIP_FILE_CHECK=1; shift ;;
        --skip-disk-check) SKIP_DISK_CHECK=1; shift ;;
        -*) printf 'unknown option: %s\n' "$1" >&2; exit 2 ;;
        *)  VERSION="$1"; shift ;;
    esac
done
[ -n "$VERSION" ] || {
    printf 'usage: upgrade.sh <version> [--allow-downgrade] [--skip-file-check]\n' >&2
    printf '                           [--skip-disk-check]\n' >&2
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

# Is the database up? Asked once, because three checks below branch on it and
# `docker compose ps` is not free. An existing .env alongside a running db is a
# running instance; anything else is a first install, which has no .env to
# compare, no dump to size and no data to check.
RUNNING=0
if [ -f .env ] && [ -n "$(docker compose ps --quiet db 2>/dev/null)" ]; then
    RUNNING=1
fi

env_value() {
    [ -f .env ] || return 0
    grep -E "^$1=" .env | tail -1 | cut -d= -f2- || true
}

# The data root, resolved the way db-backup.sh resolves it — environment first,
# then .env, then ./data — because the dump this sizes for lands wherever that
# script puts it.
DATA_ROOT="${DATA_ROOT:-$(env_value MEMSHIP_DATA_ROOT)}"
DATA_ROOT="${DATA_ROOT:-$REPO_ROOT/data}"
case "$DATA_ROOT" in
    /*) ;;
    *) DATA_ROOT="$REPO_ROOT/${DATA_ROOT#./}" ;;
esac

# ------------------------------------------------ settings this release expects
#
# A release that starts reading a new setting says so in its release notes, and
# the only thing enforcing that an operator read them is the operator. Nothing
# compares an instance's .env against what the release in this directory expects
# to find in it.
#
# "Expects" is narrow on purpose: the names install.sh writes into a .env it
# generates. That is the installer's own statement of what a deployment needs,
# it ships in this directory alongside the release, and a .env written by *this*
# install.sh has every one of them — so on an up-to-date instance this says
# nothing, which is the only way a check like this earns its place.
#
# Comparing against .env.example instead is the obvious idea and it is wrong:
# nearly everything documented there is optional and deliberately left unset by
# the installer, so it would report a dozen "missing" settings on every instance
# ever installed. A check that always fires is a check nobody reads.
#
# Almost everything found here is worth saying and not worth refusing over — an
# unset SMTP block is a documented state, not a broken one. IMAGE_TAG is the
# exception, and the reason this block refuses at all: install.sh applies a
# --tag with `sed s|^IMAGE_TAG=.*|...|`, and sed changes nothing when there is
# no line to change. An .env without it therefore accepts the new tag in
# silence and brings the stack up on ${IMAGE_TAG:-latest} — some other version
# entirely. verify-deployment.sh does catch that, but only once the stack has
# already been replaced by the wrong one.
#
# The heredoc's opening line is indented and its terminator is not, which is
# what the two patterns below are anchored on. backend/tests/unit/
# test_deployment_env.py reads the same heredoc to tie .env.example, the Compose
# file and the installer together, so a change to its shape already fails a test
# — but that test runs in another suite, so this reports rather than assumes.
installer_env_names() {
    awk '
        /cat > "\$ENV_FILE" <<EOF$/ { inside = 1; next }
        inside && /^EOF$/           { exit }
        inside && match($0, /^[A-Z][A-Z0-9_]*=/) { print substr($0, RSTART, RLENGTH - 1) }
    ' scripts/install.sh
}

if [ "$RUNNING" -eq 1 ]; then
    step "Checking .env carries what $VERSION expects"

    EXPECTED_NAMES="$(installer_env_names)"
    if [ -z "$EXPECTED_NAMES" ]; then
        # The heredoc was renamed or restructured. Saying nothing here would
        # turn this check into a permanent silent pass.
        printf '  cannot read install.sh'"'"'s .env template — skipping this check\n' >&2
    else
        PRESENT_NAMES="$(grep -oE '^[A-Z][A-Z0-9_]*=' .env | tr -d '=' | sort -u)"
        MISSING_NAMES=""
        for name in $EXPECTED_NAMES; do
            printf '%s\n' "$PRESENT_NAMES" | grep -qx "$name" \
                || MISSING_NAMES="$MISSING_NAMES $name"
        done

        case " $MISSING_NAMES " in
            *' IMAGE_TAG '*)
                printf '\nUpgrade stopped: .env has no IMAGE_TAG line.\n\n' >&2
                printf '  IMAGE_TAG is how a version is pinned, and applying one rewrites\n' >&2
                printf '  that line in place. With no line to rewrite the new tag is\n' >&2
                printf '  accepted and dropped, and the stack comes up on whatever\n' >&2
                printf '  `latest` points at rather than on %s.\n\n' "$VERSION" >&2
                # CURRENT is read from IMAGE_TAG, so in this branch it is
                # always empty and there is nothing to suggest. The running
                # containers know, though, and that is a better answer than a
                # file that has just been shown to be incomplete.
                printf '  The version to put there is the one serving right now. Ask it,\n' >&2
                printf '  then add the line and run this again:\n\n' >&2
                api_port="$(env_value API_PORT)"
                printf '    curl -s http://127.0.0.1:%s/api/v1/health\n' \
                    "${api_port:-8003}" >&2
                printf '    echo IMAGE_TAG=<that version> >> %s/.env\n\n' "$REPO_ROOT" >&2
                printf '  Nothing has been changed and the instance is still serving what\n' >&2
                printf '  it was.\n' >&2
                exit 1 ;;
        esac

        if [ -n "$MISSING_NAMES" ]; then
            printf '  .env does not mention:%s\n' "$MISSING_NAMES" >&2
            printf '  %s'"'"'s installer writes those into a .env it creates, so this one\n' "$VERSION" >&2
            printf '  predates them. Each falls back to a default, which may or may not\n' >&2
            printf '  be what you want — check the release notes. Continuing.\n' >&2
        else
            printf '  every setting the installer writes is present\n'
        fi
    fi
fi

# ---------------------------------------------------------------- disk headroom
#
# An upgrade writes two things before it changes anything: the incoming images,
# under Docker's data root, and the pre-upgrade dump, under the data root. This
# runs before both, because running out of room part-way through either is worse
# than a refusal — a pull that fills the filesystem Docker lives on takes the
# *running* instance down with it, since Postgres and Caddy are writing to the
# same disk.
#
# Two filesystems, and on a normal single-disk host they are the same one. That
# is why what goes where is accumulated per filesystem and compared once: two
# independent comparisons against one free figure would each pass while their
# sum does not.
#
# THE NUMBERS, and why they are what they are. A threshold that blocks a valid
# upgrade is worse than no check at all, so each is measured rather than picked:
#
#   Images. Measured on a clean host, Docker 29.8.1, amd64. The whole stack —
#   backend 624 MB, frontend 338 MB, postgres 417, redis 58, caddy 89 — occupies
#   1551 MB, so a first install budgets 1800. An upgrade re-pulls only what
#   changed, which is much less than the full set but far more than "a layer or
#   two": going 2.13.0 -> 2.14.0 added 771 MB on top of 2.13.0, because the
#   backend's dependency layer is rebuilt every release. So an upgrade budgets
#   1000 MB, ~30% over what was measured. Both figures ignore that the pull
#   leaves the *old* images in place, which is correct — nothing here prunes
#   them, and the free space they occupy was never ours to count.
#
#   Nothing at all when every image the target resolves to is already local.
#   Re-running this to re-apply configuration against the version already
#   installed is a documented gesture, and it pulls nothing.
#
#   The dump. Not estimated — read off this instance's own history. The largest
#   dump still inside db-backup.sh's ten-day retention window is the same
#   schema, the same data and the same compression as the one about to be
#   written, which makes it a far better predictor than anything derivable from
#   the database, and it is doubled to leave room for growth. When there is no
#   dump to learn from, this asks for nothing and says so. The obvious
#   substitute is pg_database_size, and it is not close: on a freshly seeded
#   demo instance it reported 12,016,999 bytes against a 29,353-byte dump, 409
#   times what was needed. It bounds the *uncompressed* dump, on a disk that
#   also holds the indexes and the free-space map. Requiring it would be exactly
#   the threshold that refuses an upgrade with ample room.
#
# --skip-disk-check proceeds anyway, for a host whose storage this cannot see —
# a network filesystem df misreports, or thin provisioning underneath.
IMAGE_BUDGET_FIRST_MB=1800
IMAGE_BUDGET_STEP_MB=1000

# Free bytes on the filesystem holding $1, and the device it is on, so two
# paths on one disk are charged once. Both empty when df cannot answer.
free_bytes() { df -PB1 "$1" 2>/dev/null | awk 'NR == 2 { print $4 }'; }
device_of()  { df -P "$1" 2>/dev/null | awk 'NR == 2 { print $1 }'; }
mount_of()   { df -P "$1" 2>/dev/null | awk 'NR == 2 { print $NF }'; }

human() {
    awk -v b="${1:-0}" 'BEGIN {
        if (b >= 1073741824)   printf "%.1f GB", b / 1073741824
        else if (b >= 1048576) printf "%.0f MB", b / 1048576
        else                   printf "%.0f KB", b / 1024
    }'
}

if [ "$SKIP_DISK_CHECK" -eq 0 ]; then
    step "Checking disk space"

    DOCKER_ROOT="$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || true)"
    DOCKER_ROOT="${DOCKER_ROOT:-/var/lib/docker}"

    # Every image this version resolves to, and whether each is already here.
    # `|| true` because a compose file this script is about to complain about
    # being stale is still the one that has to answer, and it may not.
    #
    # `sort -u`: api, celery-worker and celery-beat are the same image, so
    # compose lists the backend three times and an undeduplicated count says
    # "4 not yet local" about two images.
    IMAGES_NEEDED_MB=0
    TARGET_IMAGES="$(IMAGE_TAG="$VERSION" docker compose config --images 2>/dev/null \
        | sort -u || true)"
    IMAGES_ABSENT=0
    for ref in $TARGET_IMAGES; do
        docker image inspect "$ref" >/dev/null 2>&1 || IMAGES_ABSENT=$((IMAGES_ABSENT + 1))
    done
    if [ "$IMAGES_ABSENT" -gt 0 ]; then
        if [ "$RUNNING" -eq 1 ]; then
            IMAGES_NEEDED_MB="$IMAGE_BUDGET_STEP_MB"
        else
            IMAGES_NEEDED_MB="$IMAGE_BUDGET_FIRST_MB"
        fi
    fi

    # The dump, from the largest one this instance last wrote.
    DUMP_NEEDED_BYTES=0
    DUMP_BASIS="no snapshot is taken on a first install"
    if [ "$RUNNING" -eq 1 ]; then
        LAST_DUMP_BYTES="$(find "$DATA_ROOT/backups" -maxdepth 1 -name 'memship_*.sql.gz' \
            -printf '%s\n' 2>/dev/null | sort -n | tail -1)"
        if [ -n "$LAST_DUMP_BYTES" ]; then
            DUMP_NEEDED_BYTES=$((LAST_DUMP_BYTES * 2))
            DUMP_BASIS="twice the largest dump in $DATA_ROOT/backups ($(human "$LAST_DUMP_BYTES"))"
        else
            DUMP_BASIS="unknown — no previous dump to size it from"
        fi
    fi

    # Charge each requirement to the filesystem it lands on, then compare once
    # per filesystem. Keyed by device, so one disk holding both is one row.
    DOCKER_DEV="$(device_of "$DOCKER_ROOT")"
    DATA_DEV="$(device_of "$DATA_ROOT")"

    printf '  images:   %s (%s)\n' \
        "$(human $((IMAGES_NEEDED_MB * 1048576)))" \
        "$([ "$IMAGES_ABSENT" -gt 0 ] && printf '%s not yet local' "$IMAGES_ABSENT" \
            || printf 'all already local')"
    printf '  snapshot: %s (%s)\n' "$(human "$DUMP_NEEDED_BYTES")" "$DUMP_BASIS"

    disk_short=""
    check_fs() {
        # $1 label, $2 path, $3 bytes wanted
        local free mount
        free="$(free_bytes "$2")"
        mount="$(mount_of "$2")"
        if [ -z "$free" ]; then
            printf '  %s (%s): df cannot report free space — not checked\n' "$1" "$2" >&2
            return 0
        fi
        printf '  %s on %s: %s free, %s wanted\n' "$1" "${mount:-$2}" \
            "$(human "$free")" "$(human "$3")"
        [ "$free" -ge "$3" ] || disk_short="$disk_short $1"
    }

    if [ -n "$DOCKER_DEV" ] && [ "$DOCKER_DEV" = "$DATA_DEV" ]; then
        check_fs "images and snapshot" "$DOCKER_ROOT" \
            $((IMAGES_NEEDED_MB * 1048576 + DUMP_NEEDED_BYTES))
    else
        check_fs "images" "$DOCKER_ROOT" $((IMAGES_NEEDED_MB * 1048576))
        check_fs "snapshot" "$DATA_ROOT" "$DUMP_NEEDED_BYTES"
    fi

    if [ -n "$disk_short" ]; then
        printf '\nUpgrade stopped: not enough free disk for%s.\n\n' "$disk_short" >&2
        printf '  The figures above are what this needs and what is there. An\n' >&2
        printf '  upgrade that runs out part-way is worse than one that declines:\n' >&2
        printf '  the database and the proxy are writing to the same disk the pull\n' >&2
        printf '  fills, so it takes the running instance with it.\n\n' >&2
        printf '  Free some space, then run this again:\n\n' >&2
        printf '    docker image prune -a          # images no container uses\n' >&2
        printf '    du -sh %s/backups/*    # old dumps, oldest first\n' "$DATA_ROOT" >&2
        printf '\n  Nothing has been changed and the instance is still serving %s.\n\n' \
            "${CURRENT:-the version it was on}" >&2
        printf '  If df is wrong about this host — a network filesystem, or thin\n' >&2
        printf '  provisioning underneath — pass --skip-disk-check.\n' >&2
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
if [ "$RUNNING" -eq 1 ]; then
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
if [ "$RUNNING" -eq 1 ]; then
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
