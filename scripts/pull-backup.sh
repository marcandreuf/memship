#!/usr/bin/env bash
#
# memship — pull a deployment's irreplaceable state off the server, onto the
# machine you run this from. This is the ONLY script here that runs on an
# administrator's workstation rather than on the instance.
#
#   ./scripts/pull-backup.sh ovh-vps-memship
#   ./scripts/pull-backup.sh ubuntu@203.0.113.10 --port 51337 --dump
#   ./scripts/pull-backup.sh ovh-vps-memship --with-data --dest ~/memship-backups
#
# It fetches, in this order:
#
#   .env          the generated secrets. SECRET_KEY and MEMSHIP_SECRET_KEY
#                 decrypt the payment-provider, SSO and mail credentials held
#                 in the database. Without this file a perfect database dump
#                 restores those as unreadable ciphertext.
#   backups/      the pg_dump archives db-backup.sh writes
#   storage/      uploads, and secret.key   (--with-data)
#   caddy/        TLS certificates          (--with-data)
#
# It deliberately does NOT copy $MEMSHIP_DATA_ROOT/postgres. Those files are
# owned by uid 70 mode 0700, so copying them would need sudo on the far side,
# and a file-level copy of a running database is not crash-consistent anyway.
# The pg_dump in backups/ is the consistent copy — that is what it is for.
# Nothing here needs root on either machine.
#
# This is a STARTING POINT, not a backup system. It has no schedule, no
# retention, no verification and no encryption at rest. Run it from cron on a
# machine that stays on, point --dest at storage that is itself backed up, and
# see docs/self-hosting/backups-and-restore.md.

set -euo pipefail

TARGET=""
PORT=""
REMOTE_PATH="/srv/openmemship/app"
DEST=""
DO_DUMP=0
WITH_DATA=0

die() { printf '\nError: %s\n' "$*" >&2; exit 1; }
info() { printf '  %s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }
warn() { printf '\n!!  %s\n' "$*" >&2; }

usage() {
    awk 'NR == 1 { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' "${BASH_SOURCE[0]}"
    exit 0
}

while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help) usage ;;
        --port) PORT="${2:?--port needs a value}"; shift 2 ;;
        --remote-path) REMOTE_PATH="${2:?--remote-path needs a value}"; shift 2 ;;
        --dest) DEST="${2:?--dest needs a value}"; shift 2 ;;
        --dump) DO_DUMP=1; shift ;;
        --with-data) WITH_DATA=1; shift ;;
        -*) die "unknown option: $1" ;;
        *) [ -z "$TARGET" ] || die "give exactly one ssh target"; TARGET="$1"; shift ;;
    esac
done

[ -n "$TARGET" ] || usage

command -v rsync >/dev/null 2>&1 || die "rsync is required on this machine."

SSH_OPTS=(-o BatchMode=yes)
[ -n "$PORT" ] && SSH_OPTS+=(-p "$PORT")
SSH_CMD="ssh $(printf '%s ' "${SSH_OPTS[@]}")"

DEST="${DEST:-./memship-backups/${TARGET//[^A-Za-z0-9._-]/_}}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

step "Checking $TARGET"
ssh "${SSH_OPTS[@]}" "$TARGET" "test -f '$REMOTE_PATH/.env'" \
    || die "no .env at $REMOTE_PATH on $TARGET. Pass --remote-path if the deployment lives elsewhere."

# Resolve the data root the way Compose does — from .env on the instance — so
# this script has no second copy of a setting that can drift.
DATA_ROOT="$(ssh "${SSH_OPTS[@]}" "$TARGET" \
    "grep -E '^MEMSHIP_DATA_ROOT=' '$REMOTE_PATH/.env' | tail -1 | cut -d= -f2-" || true)"
[ -n "$DATA_ROOT" ] || die "could not read MEMSHIP_DATA_ROOT from $REMOTE_PATH/.env"
info "data root: $DATA_ROOT"

if [ "$DO_DUMP" -eq 1 ]; then
    step "Taking a fresh dump on $TARGET"
    ssh "${SSH_OPTS[@]}" "$TARGET" "cd '$REMOTE_PATH' && ./scripts/db-backup.sh"
fi

mkdir -p "$DEST/env" "$DEST/dumps"
chmod 700 "$DEST/env"

step "Fetching .env"
rsync -a -e "$SSH_CMD" "$TARGET:$REMOTE_PATH/.env" "$DEST/env/env-$STAMP"
chmod 600 "$DEST/env/env-$STAMP"
info "$DEST/env/env-$STAMP"

step "Fetching database dumps"
rsync -a --info=stats1 -e "$SSH_CMD" "$TARGET:$DATA_ROOT/backups/" "$DEST/dumps/"
info "$(find "$DEST/dumps" -name '*.sql.gz' | wc -l | tr -d ' ') dump(s) in $DEST/dumps"

if [ "$WITH_DATA" -eq 1 ]; then
    step "Fetching uploads and certificates"
    rsync -a --info=stats1 -e "$SSH_CMD" "$TARGET:$DATA_ROOT/storage/" "$DEST/storage/"
    rsync -a --info=stats1 -e "$SSH_CMD" "$TARGET:$DATA_ROOT/caddy/" "$DEST/caddy/"
    info "$DEST/storage, $DEST/caddy"
else
    info "skipping uploads and certificates — pass --with-data to include them"
fi

printf '\nPulled to %s\n' "$DEST"

warn "What you just copied decrypts and contains everything.

    env/env-$STAMP holds the keys, and dumps/ holds every member record. This
    directory now deserves the same protection as the server it came from:
    keep it off shared storage, and make sure whatever backs THIS machine up
    is somewhere you would still trust with it.

    A copy on one workstation is one disk failure from nothing. Put the .env
    in a password manager as well, and point --dest at storage that is itself
    backed up."
