#!/usr/bin/env bash
#
# Runs ON the staging VPS. Piped in over SSH by .github/workflows/deploy-staging.yml:
#
#   ssh user@host "API_IMAGE=... FRONTEND_IMAGE=... IMAGE_TAG=... bash -s" < scripts/staging-deploy.sh
#
# Can also be run by hand on the box to redeploy or roll back:
#
#   API_IMAGE=ghcr.io/marcandreuf/memship-backend:sha-a04e2846f66d \
#   FRONTEND_IMAGE=ghcr.io/marcandreuf/memship-frontend:sha-a04e2846f66d \
#   IMAGE_TAG=sha-a04e2846f66d bash scripts/staging-deploy.sh
#
set -euo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/memship}"
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.staging.yml)

: "${API_IMAGE:?API_IMAGE is required}"
: "${FRONTEND_IMAGE:?FRONTEND_IMAGE is required}"
: "${IMAGE_TAG:?IMAGE_TAG is required}"

cd "$DEPLOY_DIR"

# Pin the exact images being validated. Rewritten each deploy rather than
# appended, so .env cannot accumulate stale pins that shadow the new ones.
touch .env
sed -i -E '/^(API_IMAGE|FRONTEND_IMAGE|IMAGE_TAG)=/d' .env
{
    echo "API_IMAGE=${API_IMAGE}"
    echo "FRONTEND_IMAGE=${FRONTEND_IMAGE}"
    echo "IMAGE_TAG=${IMAGE_TAG}"
} >> .env

echo "Deploying:"
echo "  api      ${API_IMAGE}"
echo "  frontend ${FRONTEND_IMAGE}"

"${COMPOSE[@]}" pull
"${COMPOSE[@]}" up -d --remove-orphans

# The api entrypoint applies migrations before serving, so a failed migration
# shows up as an api that never answers. Wait for it rather than declaring
# success the moment the container is created.
echo -n "Waiting for the API"
for _ in $(seq 1 60); do
    if "${COMPOSE[@]}" exec -T api curl -fsS http://localhost:8000/api/v1/health >/dev/null 2>&1; then
        echo " — healthy"
        # Confirm the worker came back too: it is the part that fails quietly.
        if ! "${COMPOSE[@]}" exec -T celery-worker \
            uv run celery -A app.core.celery_app inspect ping -t 10 >/dev/null 2>&1; then
            echo "ERROR: the API is up but the Celery worker did not answer a ping." >&2
            echo "Emails and the scheduled billing jobs will not run. Check:" >&2
            echo "  ${COMPOSE[*]} logs celery-worker" >&2
            exit 1
        fi
        echo "Celery worker responding."
        docker image prune -f --filter "until=168h" >/dev/null 2>&1 || true
        exit 0
    fi
    echo -n "."
    sleep 5
done

echo >&2
echo "ERROR: the API did not become healthy within 5 minutes." >&2
echo "Most likely a failed migration. Check:  ${COMPOSE[*]} logs api" >&2
exit 1
