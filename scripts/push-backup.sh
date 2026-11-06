#!/usr/bin/env bash
#
# memship — push this instance's irreplaceable state to another machine. Runs
# ON the instance, from cron; pull-backup.sh is its workstation-side twin.
#
#   ./scripts/push-backup.sh              # fresh dump, then push it
#   ./scripts/push-backup.sh --no-dump    # push the newest dump already on disk
#
# The destination is BACKUP_TARGET, read from the environment or from .env:
#
#   ssh://user@host[:port]/absolute/path   rsync over SSH. The far side needs a
#                                          shell and rsync, nothing else.
#   s3://bucket[/prefix]                   any S3-compatible object store,
#                                          through the aws-cli image — Docker is
#                                          already on this host, an AWS CLI is not.
#
# Each run writes one snapshot, memship-<UTC stamp>/, holding the three things
# that cannot be reconstructed if this host is lost:
#
#   db.sql.gz   a pg_dump, taken by db-backup.sh
#   env         .env. SECRET_KEY and MEMSHIP_SECRET_KEY decrypt the payment,
#               SSO and mail credentials inside the dump.
#   storage/    uploads, plus session.key and secret.key, which hold those keys
#               instead when .env leaves them blank
#
# It deliberately does NOT copy $MEMSHIP_DATA_ROOT/postgres: a file copy of a
# running database is not crash-consistent. The dump is the consistent copy.
#
# A snapshot only counts once all of it has arrived. Over SSH it is written as
# memship-<stamp>.partial and renamed at the end, and `latest` then points at it;
# on S3 a COMPLETE object is uploaded last. A run that fails part-way leaves an
# incomplete snapshot that restore ignores and a later run prunes.
#
# Snapshots older than BACKUP_RETENTION_DAYS (default 30) are removed from the
# destination after a successful push, never the one just written. That is
# separate from the 10 days of local dumps db-backup.sh keeps.
#
# Any failure exits non-zero with the reason on stderr, so a stopped backup is
# not mistaken for a working one. Run it from cron with MAILTO set, and see
# docs/en/self-hosting/backups-and-restore.md for the target setup and restore.
#
# Settings, all optional except BACKUP_TARGET:
#
#   BACKUP_RETENTION_DAYS        days of snapshots kept at the destination
#   BACKUP_SSH_KEY               identity file for the ssh:// target
#   BACKUP_S3_ACCESS_KEY_ID      credentials for the s3:// target
#   BACKUP_S3_SECRET_ACCESS_KEY
#   BACKUP_S3_REGION             default us-east-1
#   BACKUP_S3_ENDPOINT           for a non-AWS store (MinIO, Backblaze, OVH…)
#   BACKUP_AWS_CLI_IMAGE         the image the s3:// target runs

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$REPO_ROOT/.env"
DEFAULT_AWS_CLI_IMAGE="amazon/aws-cli:2.27.0"

DO_DUMP=1

die() { printf '\nError: %s\n' "$*" >&2; exit 1; }
usage_error() { printf '\nError: %s\n\nSee the header of scripts/push-backup.sh.\n' "$*" >&2; exit 2; }
info() { printf '  %s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }

while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help)
            awk 'NR == 1 { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' "${BASH_SOURCE[0]}"
            exit 0 ;;
        --no-dump) DO_DUMP=0; shift ;;
        *) usage_error "unknown argument: $1" ;;
    esac
done

# setting <NAME> — the environment first, then .env, the way Compose resolves
# it, so cron and an operator's shell read the same value.
setting() {
    local value="${!1:-}"
    if [ -z "$value" ] && [ -f "$ENV_FILE" ]; then
        value="$(grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- || true)"
        value="${value%\"}"; value="${value#\"}"
        value="${value%\'}"; value="${value#\'}"
    fi
    printf '%s' "$value"
}

# ------------------------------------------------------------------ settings

TARGET="$(setting BACKUP_TARGET)"
[ -n "$TARGET" ] || usage_error "BACKUP_TARGET is not set. Add it to .env, e.g.
    BACKUP_TARGET=ssh://backup@backup.example.org/srv/memship-backups
    BACKUP_TARGET=s3://my-bucket/memship"

RETENTION_DAYS="$(setting BACKUP_RETENTION_DAYS)"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
case "$RETENTION_DAYS" in
    ''|*[!0-9]*|0) usage_error "BACKUP_RETENTION_DAYS must be a whole number of days, 1 or more (got '$RETENTION_DAYS')." ;;
esac

# Every remote path below ends up inside a command the far side's shell runs, so
# it is held to characters that cannot mean anything to that shell.
SAFE_PATH='^/[A-Za-z0-9._/-]*[A-Za-z0-9._-]$'

case "$TARGET" in
    ssh://*)
        KIND=ssh
        rest="${TARGET#ssh://}"
        authority="${rest%%/*}"
        RPATH="/${rest#*/}"
        [ "$authority" != "$rest" ] || usage_error "BACKUP_TARGET needs a path: ssh://user@host/absolute/path"
        RPATH="${RPATH%/}"
        [[ "$RPATH" =~ $SAFE_PATH ]] && [ "$RPATH" != "/" ] \
            || usage_error "the path in BACKUP_TARGET must be absolute and use only letters, digits, . _ - and / (got '$RPATH')."
        RPORT=""
        if [[ "$authority" =~ ^(.+):([0-9]+)$ ]]; then
            authority="${BASH_REMATCH[1]}"
            RPORT="${BASH_REMATCH[2]}"
        fi
        [[ "$authority" =~ ^([A-Za-z0-9._-]+@)?[A-Za-z0-9.-]+$ ]] \
            || usage_error "cannot read a host out of BACKUP_TARGET '$TARGET'."
        RHOST="$authority"
        ;;
    s3://*)
        KIND=s3
        rest="${TARGET#s3://}"
        rest="${rest%/}"
        BUCKET="${rest%%/*}"
        PREFIX=""
        [ "$BUCKET" = "$rest" ] || PREFIX="${rest#*/}"
        [[ "$BUCKET" =~ ^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$ ]] \
            || usage_error "'$BUCKET' is not a valid bucket name."
        [ -z "$PREFIX" ] || [[ "/$PREFIX" =~ $SAFE_PATH ]] \
            || usage_error "the prefix in BACKUP_TARGET may use only letters, digits, . _ - and / (got '$PREFIX')."
        S3_BASE="s3://$BUCKET${PREFIX:+/$PREFIX}"
        ;;
    *)
        usage_error "BACKUP_TARGET must start with ssh:// or s3:// (got '$TARGET')."
        ;;
esac

DATA_ROOT="$(setting MEMSHIP_DATA_ROOT)"
DATA_ROOT="${DATA_ROOT:-$REPO_ROOT/data}"
case "$DATA_ROOT" in
    /*) ;;
    *) DATA_ROOT="$REPO_ROOT/${DATA_ROOT#./}" ;;
esac

[ -f "$ENV_FILE" ] || die "no .env at $ENV_FILE. Without it the dump cannot be decrypted after a restore."
[ -d "$DATA_ROOT/storage" ] || die "no storage directory at $DATA_ROOT/storage."

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
SNAP="memship-$STAMP"
CUTOFF="$(date -u -d "-$RETENTION_DAYS days" +%Y%m%dT%H%M%SZ)"
SNAP_NAME='^memship-([0-9]{8}T[0-9]{6}Z)(\.partial)?$'

# What the failure message says depends on how far the run got: a failure while
# pruning comes after a complete snapshot, and saying otherwise would send
# someone to repair a backup that worked.
PHASE="before anything was pushed"
trap 'printf "\nPUSH FAILED %s (%s).\n" "$PHASE" "$TARGET" >&2' ERR

# ------------------------------------------------------------------ the dump

if [ "$DO_DUMP" -eq 1 ]; then
    step "Taking a fresh dump"
    "$SCRIPT_DIR/db-backup.sh"
fi

# Named dumps only: db-restore.sh writes memship_pre-restore_*.sql.gz beside
# them, and a pre-restore dump is the database a restore was replacing.
DUMP=""
for f in "$DATA_ROOT"/backups/memship_[0-9]*.sql.gz; do
    [ -f "$f" ] && DUMP="$f"
done
[ -n "$DUMP" ] || die "no dump in $DATA_ROOT/backups to push. Run without --no-dump to take one."
info "dump: $(basename "$DUMP")"

# old_snapshots — read snapshot names on stdin, print those past the cutoff. The
# cutoff is at least a day old, so the snapshot this run wrote is never among
# them.
old_snapshots() {
    local name
    while IFS= read -r name; do
        name="${name%/}"
        [[ "$name" =~ $SNAP_NAME ]] || continue
        [[ "${BASH_REMATCH[1]}" < "$CUTOFF" ]] && printf '%s\n' "$name"
    done
    return 0
}

# ------------------------------------------------------------------ ssh://

push_ssh() {
    local ssh_opts=(-o BatchMode=yes) key ssh_cmd link_dest=() old
    [ -z "$RPORT" ] || ssh_opts+=(-p "$RPORT")
    key="$(setting BACKUP_SSH_KEY)"
    [ -z "$key" ] || ssh_opts+=(-i "$key")
    ssh_cmd="ssh ${ssh_opts[*]}"
    command -v rsync >/dev/null 2>&1 || die "rsync is required on this host."

    remote() { ssh "${ssh_opts[@]}" "$RHOST" "$1"; }

    step "Pushing $SNAP to $RHOST:$RPATH"
    PHASE="while pushing: no snapshot was completed and nothing older was removed"
    remote "mkdir -p '$RPATH/$SNAP.partial'"

    # Unchanged uploads are hard-linked against the previous snapshot rather
    # than sent and stored again, so a month of snapshots costs one copy of
    # storage/ plus what changed.
    if remote "test -d '$RPATH/latest/storage'"; then
        link_dest=(--link-dest="$RPATH/latest/storage")
    fi

    rsync -a --chmod=F600 -e "$ssh_cmd" "$DUMP" "$RHOST:$RPATH/$SNAP.partial/db.sql.gz"
    rsync -a --chmod=F600 -e "$ssh_cmd" "$ENV_FILE" "$RHOST:$RPATH/$SNAP.partial/env"
    rsync -a "${link_dest[@]}" -e "$ssh_cmd" "$DATA_ROOT/storage/" "$RHOST:$RPATH/$SNAP.partial/storage/"

    remote "mv '$RPATH/$SNAP.partial' '$RPATH/$SNAP' && ln -sfn '$SNAP' '$RPATH/latest'"
    info "complete: $RPATH/$SNAP"

    step "Removing snapshots older than $RETENTION_DAYS days"
    PHASE="while pruning old snapshots: $SNAP itself is complete"
    old="$(remote "ls -1 '$RPATH'" | old_snapshots)"
    if [ -n "$old" ]; then
        remote "cd '$RPATH' && rm -rf -- $(printf "'%s' " $old)"
        info "removed: $(printf '%s ' $old)"
    else
        info "nothing to remove"
    fi
}

# ------------------------------------------------------------------ s3://

push_s3() {
    local image endpoint old name
    image="$(setting BACKUP_AWS_CLI_IMAGE)"
    image="${image:-$DEFAULT_AWS_CLI_IMAGE}"
    endpoint="$(setting BACKUP_S3_ENDPOINT)"

    # Exported and passed to the container by name only, so the secret never
    # appears in the docker command line, `ps` or a log of either.
    AWS_ACCESS_KEY_ID="$(setting BACKUP_S3_ACCESS_KEY_ID)"
    AWS_SECRET_ACCESS_KEY="$(setting BACKUP_S3_SECRET_ACCESS_KEY)"
    AWS_DEFAULT_REGION="$(setting BACKUP_S3_REGION)"
    AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
    [ -n "$AWS_ACCESS_KEY_ID" ] && [ -n "$AWS_SECRET_ACCESS_KEY" ] \
        || die "BACKUP_S3_ACCESS_KEY_ID and BACKUP_S3_SECRET_ACCESS_KEY must both be set for an s3:// target."
    export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_DEFAULT_REGION

    aws() {
        docker run --rm -i \
            -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION \
            -v "$DATA_ROOT/backups:/backup/dumps:ro" \
            -v "$DATA_ROOT/storage:/backup/storage:ro" \
            -v "$ENV_FILE:/backup/env:ro" \
            "$image" ${endpoint:+--endpoint-url "$endpoint"} "$@"
    }

    step "Pushing $SNAP to $S3_BASE"
    PHASE="while pushing: no snapshot was completed and nothing older was removed"
    aws s3 cp --only-show-errors "/backup/dumps/$(basename "$DUMP")" "$S3_BASE/$SNAP/db.sql.gz"
    aws s3 cp --only-show-errors /backup/env "$S3_BASE/$SNAP/env"
    aws s3 cp --only-show-errors --recursive /backup/storage "$S3_BASE/$SNAP/storage/"
    printf '%s\n' "$STAMP" | aws s3 cp --only-show-errors - "$S3_BASE/$SNAP/COMPLETE"
    info "complete: $S3_BASE/$SNAP"

    step "Removing snapshots older than $RETENTION_DAYS days"
    PHASE="while pruning old snapshots: $SNAP itself is complete"
    old="$(aws s3 ls "$S3_BASE/" | awk '$1 == "PRE" { print $2 }' | old_snapshots)"
    if [ -n "$old" ]; then
        for name in $old; do
            aws s3 rm --only-show-errors --recursive "$S3_BASE/$name/"
        done
        info "removed: $(printf '%s ' $old)"
    else
        info "nothing to remove"
    fi
}

case "$KIND" in
    ssh) push_ssh ;;
    s3) push_s3 ;;
esac

trap - ERR
printf '\nPushed %s to %s\n' "$SNAP" "$TARGET"
