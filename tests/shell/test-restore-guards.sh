#!/usr/bin/env bash
#
# scripts/db-restore.sh — what has to be true before it says "Restore complete".
#
# A dump that loads is not yet an instance that works. On a new server the
# database role still has the password install.sh generated, while the restored
# .env carries the old one, so the API cannot log in and crash-loops — and the
# restore, which talks to postgres over the trusted local socket, never noticed
# (#552). So the cases here assert that the password is set from .env, without
# the value reaching a command line, and that "complete" waits for the API.

# shellcheck source=tests/shell/lib.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

case_defaults() {
    export STUB_DB_RUNNING=1 STUB_HEALTH_VERSION=3.1.0
}
case_defaults

DUMP=memship_20261101_033000.sql.gz

# instance <name> — a running instance whose .env carries a recognisable
# DB_PASSWORD, with one dump to restore.
instance() {
    new_sandbox "$1"
    write_env 3.1.0 "DB_PASSWORD=pw-never-in-argv"
    printf -- '-- PostgreSQL database dump\n' | gzip >"$STUB_BACKUP_DIR/$DUMP"
}

restore() {
    run_script scripts/db-restore.sh --confirm --yes "$DUMP"
}


it "sets the database password from .env before starting the stack"
instance restore-ok
restore
assert_status 0
assert_says "Restore complete"
assert_order "-d memship_db --quiet" "ALTER ROLE memship PASSWORD"
assert_order "ALTER ROLE memship PASSWORD" "compose .*up -d"
assert_called "exec -T -e MEMSHIP_RESTORE_DB_PASSWORD db"
grep -q 'pw-never-in-argv' "$STUB_LOG" && fail "DB_PASSWORD appeared on a command line"
assert_order "compose .*up -d" "^curl .*api/v1/health"
done_case

it "does not say complete while the API is not answering"
instance restore-api-down
STUB_HEALTH_VERSION="" restore
assert_status 1
assert_says "the API is not answering"
assert_silent_about "Restore complete"
done_case

it "leaves the stack stopped when the password cannot be set"
instance restore-alter-fails
STUB_PSQL_FAIL_ON="ALTER ROLE" restore
assert_status 1
assert_says "could not be set to DB_PASSWORD"
assert_not_called "compose .*up -d"
assert_silent_about "Restore complete"
done_case

it "touches neither the password nor the stack when the dump does not load"
instance restore-load-fails
STUB_PSQL_FAIL_ON="-d memship_db --quiet" restore
assert_status 1
assert_says "RESTORE FAILED"
assert_not_called "ALTER ROLE"
assert_not_called "compose .*up -d"
done_case

summary
