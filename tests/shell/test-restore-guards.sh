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

it "lets COMPOSE_FILE in .env decide the stack, rather than pinning docker-compose.yml"
# Behind an external proxy, .env layers the overlay over docker-compose.yml.
# A restore that pins -f docker-compose.yml recreates the stack without it, and
# its closing `up -d` starts the bundled Caddy on 80/443 next to that proxy.
# The dump it takes first goes through db-backup.sh's rules too.
instance restore-compose-file
restore
assert_status 0
assert_not_called "compose -f"
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

it "stops the worker and the beat as well as the API"
# Only the API was stopped, so the worker kept one session open and DROP
# DATABASE was refused with "database is being accessed by other users". That
# aborted every restore on a default stack (#567).
instance restore-stops-db-clients
restore
assert_status 0
assert_called "compose stop api celery-worker celery-beat"
assert_order "compose stop .*celery-worker" "DROP DATABASE"
done_case

it "clears a session that is still attached before it drops"
# The guard that does not depend on the stop list being complete: a container
# that reconnects between the stop and the drop, or a service added later and
# missed, would each refuse the drop on its own.
instance restore-terminates
restore
assert_status 0
assert_called "pg_terminate_backend"
assert_order "pg_terminate_backend" "DROP DATABASE"
done_case

it "stops a stack that has no celery services without failing"
# A `docker compose stop` naming a service the file does not define is an
# error, so the list is intersected with what compose reports. STUB_NO_CELERY
# is the shape of a cut-down stack.
instance restore-no-celery
STUB_NO_CELERY=1 restore
assert_status 0
assert_called "compose stop api"
assert_not_called "compose stop api celery"
done_case

it "says what is holding the database when the drop is refused, and changes nothing"
instance restore-drop-refused
STUB_PSQL_FAIL_ON="DROP DATABASE" restore
assert_status 1
assert_says "RESTORE FAILED"
assert_says "Your data is untouched."
assert_says "pg_stat_activity"
assert_not_called "ALTER ROLE"
assert_not_called "compose .*up -d"
assert_silent_about "Restore complete"
done_case

it "stops every service that docker-compose.yml connects to the database"
# The invariant, not an example. The bug arrived because services that talk to
# the database were added and the stop list was never widened, so what the
# suite pins is the relationship rather than today's three names.
#
# DATABASE_URL is declared once, in the x-backend-env anchor, and each backend
# service merges it. That anchor exists for the same reason this case does: its
# own comment says it is kept in one place "so a new setting cannot be added to
# the API and silently forgotten on the worker". A stub cannot hold a real
# connection, so this reads the two files instead.
OUT=""
db_anchor="$(awk '
    /^x-[a-z-]*:[[:space:]]*&/ { anchor = $2; sub(/^&/, "", anchor) }
    /^[^[:space:]]/ && !/^x-/ { anchor = "" }
    anchor != "" && /DATABASE_URL/ { print anchor; exit }
' "$REPO_ROOT/docker-compose.yml")"
compose_db_clients="$(awk -v a="$db_anchor" '
    /^services:/ { in_services = 1; next }
    in_services && /^  [a-z][a-z0-9_-]*:/ { svc = $1; sub(/:$/, "", svc) }
    in_services && $0 ~ ("<<:[[:space:]]*\\*" a "$") { print svc }
' "$REPO_ROOT/docker-compose.yml" | sort -u)"
stop_list="$(grep -E 'DB_CLIENTS\+=' "$REPO_ROOT/scripts/db-restore.sh" |
    head -1 | sed 's/).*//' | tr -d '[:space:]')"
[ -n "$db_anchor" ] || fail "no anchor declares DATABASE_URL — this case stopped matching"
[ -n "$compose_db_clients" ] || fail "no service merges *$db_anchor — this case stopped matching"
[ -n "$stop_list" ] || fail "could not read the stop list out of db-restore.sh"
for svc in $compose_db_clients; do
    case "|$stop_list|" in
        *"|$svc|"*) ;;
        *) fail "$svc reaches the database but db-restore.sh does not stop it" ;;
    esac
done
done_case

summary
