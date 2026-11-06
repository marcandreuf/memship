#!/usr/bin/env bash
#
# scripts/push-backup.sh — what it refuses, what a pushed snapshot holds, and
# what a failure leaves behind.
#
# The promise worth testing is the one an operator relies on without looking:
# a snapshot that exists at the destination is whole, and a run that did not
# produce one says so with a non-zero exit. So the failure cases assert on what
# was NOT done (no completed snapshot, nothing pruned) as much as on the exit.
#
# The ssh:// target is exercised end to end: the ssh and rsync stubs run against
# a directory in the sandbox, so the "backup host" can be read back as files.
# The s3:// target is asserted on through the call log, since the far side is
# the aws-cli image.

# shellcheck source=tests/shell/lib.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

case_defaults() {
    export STUB_DB_RUNNING=1
}
case_defaults

# instance <name> [extra .env lines…] — a running instance with one upload, and
# a directory standing in for the backup host at $REMOTE.
instance() {
    local name="$1"; shift
    new_sandbox "$name"
    write_env 2.20.0 "$@"
    printf 'logo\n' >"$STUB_DATA_ROOT/storage/logo.png"
    REMOTE="$SANDBOX_ROOT/$name-remote"
    mkdir -p "$REMOTE"
}

# snapshots — the complete snapshot directories on the backup host.
snapshots() {
    find "$REMOTE" -maxdepth 1 -type d -name 'memship-*' ! -name '*.partial' -printf '%f\n' | sort
}


# ------------------------------------------------------------ settings

it "refuses without a BACKUP_TARGET, before taking a dump"
instance push-notarget
run_script scripts/push-backup.sh
assert_status 2
assert_says "BACKUP_TARGET is not set"
assert_not_called "compose .*exec"
done_case

it "refuses a target that is neither ssh:// nor s3://"
instance push-scheme "BACKUP_TARGET=ftp://backup.example.org/memship"
run_script scripts/push-backup.sh
assert_status 2
assert_says "must start with ssh:// or s3://"
done_case

it "refuses an ssh path the far side's shell could read as a command"
instance push-unsafe "BACKUP_TARGET=ssh://backup@backup.example.org/srv/x;reboot"
run_script scripts/push-backup.sh
assert_status 2
assert_says "must be absolute"
assert_not_called "^ssh "
done_case

it "refuses a retention that is not a positive number of days"
instance push-retention "BACKUP_TARGET=ssh://backup@backup.example.org/srv/b" "BACKUP_RETENTION_DAYS=0"
run_script scripts/push-backup.sh
assert_status 2
assert_says "BACKUP_RETENTION_DAYS must be a whole number"
done_case


# ------------------------------------------------------------ ssh://

it "pushes a complete snapshot over ssh: dump, .env and uploads"
instance push-ssh-ok
write_env 2.20.0 "BACKUP_TARGET=ssh://backup@backup.example.org:2222$REMOTE"
run_script scripts/push-backup.sh
assert_status 0
assert_order "compose .*exec" "^rsync "
assert_called "^ssh .*-p 2222 backup@backup.example.org"
snap="$(snapshots)"
[ -n "$snap" ] || fail "no complete snapshot on the backup host"
[ -s "$REMOTE/$snap/db.sql.gz" ] || fail "the snapshot has no dump"
cmp -s "$SANDBOX/.env" "$REMOTE/$snap/env" || fail "the snapshot's env is not this .env"
[ -f "$REMOTE/$snap/storage/logo.png" ] || fail "the snapshot has no uploads"
[ "$(readlink "$REMOTE/latest")" = "$snap" ] || fail "latest does not point at the new snapshot"
[ -z "$(find "$REMOTE" -maxdepth 1 -name '*.partial')" ] || fail "a .partial directory was left behind"
done_case

it "leaves no complete snapshot and prunes nothing when a transfer fails"
instance push-ssh-fail
write_env 2.20.0 "BACKUP_TARGET=ssh://backup@backup.example.org$REMOTE"
mkdir -p "$REMOTE/memship-20200101T000000Z"
STUB_RSYNC_FAIL=1 STUB_RSYNC_FAIL_ON=storage run_script scripts/push-backup.sh
assert_status 23
assert_says "PUSH FAILED while pushing"
[ "$(snapshots)" = "memship-20200101T000000Z" ] || fail "a failed push produced a complete snapshot, or pruned one: $(snapshots)"
[ ! -e "$REMOTE/latest" ] || fail "latest was moved by a failed push"
assert_not_called "^ssh .*rm -rf"
done_case

it "fails loudly when the backup host cannot be reached"
instance push-ssh-down
write_env 2.20.0 "BACKUP_TARGET=ssh://backup@backup.example.org$REMOTE"
STUB_SSH_FAIL=1 run_script scripts/push-backup.sh
[ "$STATUS" -ne 0 ] || fail "an unreachable host exited 0"
assert_says "PUSH FAILED"
assert_not_called "^rsync "
done_case

it "prunes snapshots past retention, complete or partial, and keeps the rest"
instance push-ssh-prune
write_env 2.20.0 "BACKUP_TARGET=ssh://backup@backup.example.org$REMOTE" "BACKUP_RETENTION_DAYS=30"
recent="memship-$(date -u -d '-2 days' +%Y%m%dT%H%M%SZ)"
mkdir -p "$REMOTE/memship-20200101T000000Z" "$REMOTE/memship-20200102T000000Z.partial" \
    "$REMOTE/$recent" "$REMOTE/unrelated"
run_script scripts/push-backup.sh
assert_status 0
[ ! -e "$REMOTE/memship-20200101T000000Z" ] || fail "an expired snapshot was kept"
[ ! -e "$REMOTE/memship-20200102T000000Z.partial" ] || fail "an expired partial snapshot was kept"
[ -d "$REMOTE/$recent" ] || fail "a snapshot inside retention was removed"
[ -d "$REMOTE/unrelated" ] || fail "something that is not a snapshot was removed"
[ "$(snapshots | wc -l)" -eq 2 ] || fail "expected the recent and the new snapshot: $(snapshots)"
done_case

it "hard-links uploads against the previous snapshot rather than resending them"
instance push-ssh-link
write_env 2.20.0 "BACKUP_TARGET=ssh://backup@backup.example.org$REMOTE"
mkdir -p "$REMOTE/memship-20261101T000000Z/storage"
ln -s memship-20261101T000000Z "$REMOTE/latest"
run_script scripts/push-backup.sh
assert_status 0
assert_called "^rsync .*--link-dest=$REMOTE/latest/storage"
done_case


# ------------------------------------------------------------ the dump

it "stops before pushing when the dump cannot be taken"
instance push-nodb
write_env 2.20.0 "BACKUP_TARGET=ssh://backup@backup.example.org$REMOTE"
STUB_DB_RUNNING=0 run_script scripts/push-backup.sh
[ "$STATUS" -ne 0 ] || fail "a missing dump exited 0"
assert_says "PUSH FAILED before anything was pushed"
assert_not_called "^ssh "
done_case

it "--no-dump pushes the newest dump, never a pre-restore one"
instance push-nodump
write_env 2.20.0 "BACKUP_TARGET=ssh://backup@backup.example.org$REMOTE"
printf 'old\n' | gzip >"$STUB_BACKUP_DIR/memship_20261101_033000.sql.gz"
printf 'new\n' | gzip >"$STUB_BACKUP_DIR/memship_20261105_033000.sql.gz"
printf 'pre\n' | gzip >"$STUB_BACKUP_DIR/memship_pre-restore_20261106_120000.sql.gz"
run_script scripts/push-backup.sh --no-dump
assert_status 0
assert_not_called "compose .*exec"
assert_called "^rsync .*memship_20261105_033000.sql.gz"
assert_not_called "^rsync .*pre-restore"
done_case

it "--no-dump refuses when only a pre-restore dump exists"
instance push-onlypre
write_env 2.20.0 "BACKUP_TARGET=ssh://backup@backup.example.org$REMOTE"
printf 'pre\n' | gzip >"$STUB_BACKUP_DIR/memship_pre-restore_20261106_120000.sql.gz"
run_script scripts/push-backup.sh --no-dump
assert_status 1
assert_says "no dump in"
done_case


# ------------------------------------------------------------ s3://

S3_ENV=("BACKUP_TARGET=s3://club-backups/memship"
        "BACKUP_S3_ACCESS_KEY_ID=AKIAEXAMPLE"
        "BACKUP_S3_SECRET_ACCESS_KEY=s3cr3t-never-in-argv")

it "pushes to s3 and writes the COMPLETE marker last"
instance push-s3-ok "${S3_ENV[@]}" "BACKUP_S3_ENDPOINT=https://s3.example.org"
run_script scripts/push-backup.sh
assert_status 0
assert_called "s3 cp .*db.sql.gz"
assert_called "s3 cp .*/backup/env s3://club-backups/memship/memship-"
assert_called "s3 cp .*--recursive /backup/storage"
assert_called "--endpoint-url https://s3.example.org"
assert_order "s3 cp .*--recursive /backup/storage" "/COMPLETE"
grep -q 's3cr3t-never-in-argv' "$STUB_LOG" && fail "the S3 secret appeared on a command line"
done_case

it "writes no COMPLETE marker and prunes nothing when an s3 upload fails"
instance push-s3-fail "${S3_ENV[@]}"
STUB_S3_FAIL_ON="/backup/storage s3://" STUB_S3_LISTING='PRE memship-20200101T000000Z/\n' \
    run_script scripts/push-backup.sh
[ "$STATUS" -ne 0 ] || fail "a failed upload exited 0"
assert_says "PUSH FAILED while pushing"
assert_called "s3 cp .*db.sql.gz"
assert_not_called "/COMPLETE"
assert_not_called "s3 rm"
done_case

it "refuses an s3 target without credentials"
instance push-s3-nocreds "BACKUP_TARGET=s3://club-backups/memship"
run_script scripts/push-backup.sh
assert_status 1
assert_says "BACKUP_S3_SECRET_ACCESS_KEY must both be set"
assert_not_called "s3 cp"
done_case

it "prunes expired s3 snapshots and keeps recent ones"
instance push-s3-prune "${S3_ENV[@]}"
recent="memship-$(date -u -d '-2 days' +%Y%m%dT%H%M%SZ)"
STUB_S3_LISTING="                           PRE memship-20200101T000000Z/\n                           PRE $recent/\n" \
    run_script scripts/push-backup.sh
assert_status 0
assert_called "s3 rm .*--recursive s3://club-backups/memship/memship-20200101T000000Z/"
assert_not_called "s3 rm .*$recent"
done_case

summary
