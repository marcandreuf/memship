#!/usr/bin/env bash
#
# memship — confirm a deployment came back on the version you asked for.
#
#   ./scripts/verify-deployment.sh 2.7.0
#
# Run this after an install or upgrade. `docker compose up -d` returning says
# only that the containers were created; the API applies database migrations
# before it starts serving, so a failed migration looks like an API that never
# answers rather than a container that failed to start. The only way to know a
# deployment landed is to ask it.
#
# Checks, in order:
#   1. the API answers /api/v1/health
#   2. it reports the version that was deployed, not the one it was running
#   3. the Celery worker answers a ping — it is the half that fails quietly,
#      and without it no mail and no scheduled billing job runs
#
# When a check fails it prints the service's container state and log tail, so
# the reason is in this output. A migration guard that aborts an upgrade writes
# its report there, naming the rows a person has to resolve.

set -euo pipefail

EXPECTED="${1:?usage: verify-deployment.sh <version>, e.g. 2.7.0}"
EXPECTED="${EXPECTED#v}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

TIMEOUT="${VERIFY_TIMEOUT:-300}"
INTERVAL=5
FAILURE_LOG_LINES="${VERIFY_LOG_LINES:-40}"

# The API is published on the loopback interface only, which is where we probe
# it: going in through the public hostname would test DNS and the certificate
# too, and those fail for reasons that have nothing to do with the deployment.
# The backend image carries no curl, so this cannot be an `exec` into the
# container — read the published port and probe from the host.
env_value() {
    [ -f .env ] || return 0
    grep -E "^$1=" .env | tail -1 | cut -d= -f2- || true
}

# What a service is doing and what it last said, printed here rather than left
# one command away.
#
# The API applies migrations before it serves, and a migration is allowed to
# refuse: a guard that finds data it will not rewrite aborts the upgrade on
# purpose. That leaves the container restarting under its `unless-stopped`
# policy, which from outside is indistinguishable from any other boot failure
# — both are an API that never answers. The container state separates the two
# (`restarting` with a climbing restart count is a loop, not a slow start), and
# the log tail carries the report the guard wrote, which names the rows to fix.
# A deliberate abort makes no writes, so the database is as it was.
report_service_failure() {
    local service="$1" cid
    cid="$(docker compose ps -q "$service" 2>/dev/null | head -1 || true)"
    if [ -n "$cid" ]; then
        printf -- '--- %s container ---\n' "$service" >&2
        # `>&2` before `2>/dev/null`: redirections apply left to right, so the
        # other order points stdout at the just-silenced stderr and the line
        # disappears.
        docker inspect "$cid" \
            --format '  state={{.State.Status}} exit={{.State.ExitCode}} restarts={{.RestartCount}}' \
            >&2 2>/dev/null || true
        printf '\n' >&2
    fi
    printf -- '--- last %s lines of `docker compose logs %s` ---\n' \
        "$FAILURE_LOG_LINES" "$service" >&2
    docker compose logs "$service" --tail "$FAILURE_LOG_LINES" --no-log-prefix 2>&1 \
        | sed 's/^/  /' >&2 || true
    printf -- '---\n' >&2
}

API_PORT="$(env_value API_PORT)"
API_PORT="${API_PORT:-8003}"
HEALTH_URL="http://127.0.0.1:${API_PORT}/api/v1/health"

printf '==> Waiting for the API on %s\n' "$HEALTH_URL"

deadline=$((SECONDS + TIMEOUT))
body=""
while [ "$SECONDS" -lt "$deadline" ]; do
    if body="$(curl -fsS --max-time 5 "$HEALTH_URL" 2>/dev/null)"; then
        break
    fi
    body=""
    printf '.'
    sleep "$INTERVAL"
done

if [ -z "$body" ]; then
    printf '\n'
    printf 'ERROR: the API did not answer within %ss.\n' "$TIMEOUT" >&2
    printf 'A migration that refused to run is the usual cause, and it says why below.\n' >&2
    report_service_failure api
    exit 1
fi

printf '\n  %s\n' "$body"

reported="$(printf '%s' "$body" | sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
if [ "$reported" != "$EXPECTED" ]; then
    printf 'ERROR: deployed %s but the API reports %s.\n' "$EXPECTED" "${reported:-<none>}" >&2
    printf 'IMAGE_TAG in .env and the running containers disagree — the upgrade did not take.\n' >&2
    exit 1
fi
printf '  version %s — as deployed\n' "$reported"

printf '==> Pinging the Celery worker\n'
# Call celery directly. `uv run` needs write access to /app/.venv and fails as
# the non-root runtime user the containers run as.
if ! docker compose exec -T celery-worker \
        celery -A app.core.celery_app inspect ping -t 10 </dev/null >/dev/null 2>&1; then
    printf 'ERROR: the API is up but the Celery worker did not answer.\n' >&2
    printf 'Mail and the scheduled billing jobs will not run.\n' >&2
    report_service_failure celery-worker
    exit 1
fi
printf '  worker responding\n'

printf '\nDeployment verified: %s\n' "$EXPECTED"
