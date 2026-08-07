#!/usr/bin/env bash
#
# memship — install or update a self-hosted instance on a single host.
#
# Run as the ordinary user that will own the deployment, NOT as root. That user
# needs to be in the `docker` group (scripts/vps-bootstrap.sh arranges this on a
# fresh server; on an existing box, `sudo usermod -aG docker $USER` then log out
# and back in).
#
#   ./scripts/install.sh                                  # into ./data, plain HTTP
#   ./scripts/install.sh --domain memship.example.com     # with automatic HTTPS
#   ./scripts/install.sh --data-root /srv/openmemship --domain memship.example.com
#
# Safe to re-run: it never overwrites an existing .env, and re-running is how you
# pick up a new IMAGE_TAG. Everything it creates lives under one data root, so
# backing up memship means backing up that one directory.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_ROOT=""
DOMAIN=""
IMAGE_TAG=""
SKIP_DNS_CHECK=0

die() { printf '\nError: %s\n' "$*" >&2; exit 1; }
info() { printf '  %s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }
warn() { printf '\n!!  %s\n' "$*" >&2; }

usage() {
    sed -n '2,18p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 0
}

while [ $# -gt 0 ]; do
    case "$1" in
        --data-root) DATA_ROOT="${2:-}"; shift 2 ;;
        --domain)    DOMAIN="${2:-}"; shift 2 ;;
        --tag)       IMAGE_TAG="${2:-}"; shift 2 ;;
        --skip-dns-check) SKIP_DNS_CHECK=1; shift ;;
        -h|--help)   usage ;;
        *) die "unknown option: $1 (try --help)" ;;
    esac
done

# ---------------------------------------------------------------- preflight

step "Checking prerequisites"

[ "$(id -u)" -ne 0 ] || die "do not run this as root. Run it as the user that will own the deployment — see the header."

command -v docker >/dev/null 2>&1 || die "docker is not installed. See scripts/vps-bootstrap.sh, or https://docs.docker.com/engine/install/"
docker compose version >/dev/null 2>&1 || die "the Docker Compose plugin is missing. Install docker-compose-plugin from Docker's apt repository."
docker info >/dev/null 2>&1 || die "cannot talk to the Docker daemon. Is '$USER' in the 'docker' group? You must log out and back in after being added."

info "docker $(docker version --format '{{.Server.Version}}' 2>/dev/null || echo '?'), compose plugin present"

# ---------------------------------------------------------------- data root

# Resolve the data root: --data-root wins, then an existing .env, then ./data.
ENV_FILE="$REPO_ROOT/.env"
if [ -z "$DATA_ROOT" ] && [ -f "$ENV_FILE" ]; then
    DATA_ROOT="$(grep -E '^MEMSHIP_DATA_ROOT=' "$ENV_FILE" | tail -1 | cut -d= -f2- || true)"
fi
DATA_ROOT="${DATA_ROOT:-$REPO_ROOT/data}"
case "$DATA_ROOT" in
    /*) ;;
    *) DATA_ROOT="$REPO_ROOT/${DATA_ROOT#./}" ;;
esac

step "Preparing $DATA_ROOT"

# The parent must be traversable by the container users (postgres runs as uid 70),
# or Postgres cannot reach its data directory and refuses to start. A 0700 home
# directory is the usual cause — which is why /srv is a better home for this than
# a user's home directory on a hardened box.
PARENT="$(dirname "$DATA_ROOT")"
if [ ! -d "$DATA_ROOT" ]; then
    mkdir -p "$DATA_ROOT" 2>/dev/null || die "cannot create $DATA_ROOT. Create it and chown it to '$USER' first:
    sudo mkdir -p $DATA_ROOT && sudo chown $USER:$USER $DATA_ROOT"
fi
[ -w "$DATA_ROOT" ] || die "$DATA_ROOT is not writable by '$USER'. Fix with: sudo chown -R $USER:$USER $DATA_ROOT"

if [ "$(stat -c '%a' "$PARENT" 2>/dev/null || echo 755)" = "700" ]; then
    warn "$PARENT is mode 0700. Containers running as other users (Postgres uses uid 70)
    cannot traverse into it, and Postgres will fail to start. Either:
      sudo chmod 0711 $PARENT
    or put the data root somewhere else, e.g. --data-root /srv/openmemship"
fi

# Redis is only the Celery broker and has no volume — losing queued tasks on a
# restart is acceptable and there is no appendonly file to keep.
for d in postgres storage celerybeat caddy/data caddy/config backups; do
    mkdir -p "$DATA_ROOT/$d"
    info "$DATA_ROOT/$d"
done

# storage/ holds uploads AND the auto-generated encryption key (secret.key). The
# backend image currently runs as root, so its files land root-owned on the host;
# 0770 at least keeps the directory itself yours. See docs/self-hosting/.
chmod 0770 "$DATA_ROOT/storage"
chmod 0700 "$DATA_ROOT/backups"

# ---------------------------------------------------------------- .env

step "Configuring"

gen_secret() { openssl rand -hex 32; }
# Fernet needs urlsafe base64 of exactly 32 bytes — see backend/app/core/config.py.
gen_fernet() { openssl rand -base64 32 | tr '+/' '-_'; }

if [ -f "$ENV_FILE" ]; then
    info ".env exists — leaving it alone (edit it by hand to change settings)"
else
    command -v openssl >/dev/null 2>&1 || die "openssl is required to generate secrets. Install it and re-run."

    SITE="${DOMAIN}"
    if [ -n "$DOMAIN" ]; then
        PUBLIC_URL="https://$DOMAIN"
    else
        PUBLIC_URL="http://localhost"
    fi

    umask 077
    cat > "$ENV_FILE" <<EOF
# Written by scripts/install.sh. Secrets below are randomly generated —
# losing them means losing access to encrypted data. Back this file up.

MEMSHIP_DATA_ROOT=$DATA_ROOT
SITE_ADDRESS=$SITE
IMAGE_TAG=$IMAGE_TAG

# The backend containers run as this uid/gid, so uploads written to
# \$MEMSHIP_DATA_ROOT/storage belong to you and need no sudo to read.
HOST_UID=$(id -u)
HOST_GID=$(id -g)

DB_PASSWORD=$(gen_secret)
SECRET_KEY=$(gen_secret)

# Encrypts SSO and payment-provider secrets stored in the database. Set
# explicitly so a rebuilt host can still decrypt a restored backup.
MEMSHIP_SECRET_KEY=$(gen_fernet)

APP_ENV=production
DEFAULT_LOCALE=es
FRONTEND_URL=$PUBLIC_URL
CORS_ORIGINS=$PUBLIC_URL
BACKEND_PUBLIC_URL=$PUBLIC_URL

# Email is disabled until one of these is filled in. Without it, registration,
# receipt and announcement emails are dropped silently.
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=noreply@${DOMAIN:-memship.local}
SMTP_TLS=true
EOF
    umask 022
    chmod 600 "$ENV_FILE"
    info "wrote .env with generated secrets (mode 600)"
fi

# Applying --domain or --tag to an existing .env, in place.
if [ -n "$DOMAIN" ]; then
    sed -i "s|^SITE_ADDRESS=.*|SITE_ADDRESS=$DOMAIN|" "$ENV_FILE"
    info "SITE_ADDRESS=$DOMAIN"
fi
if [ -n "$IMAGE_TAG" ]; then
    sed -i "s|^IMAGE_TAG=.*|IMAGE_TAG=$IMAGE_TAG|" "$ENV_FILE"
    info "IMAGE_TAG=$IMAGE_TAG"
fi
grep -qE '^MEMSHIP_DATA_ROOT=' "$ENV_FILE" || printf 'MEMSHIP_DATA_ROOT=%s\n' "$DATA_ROOT" >> "$ENV_FILE"

# Upgrades from a pre-bind-mount install have no HOST_UID. Add it, and take
# ownership of storage/ so the now-non-root backend can still write there.
if ! grep -qE '^HOST_UID=' "$ENV_FILE"; then
    printf 'HOST_UID=%s\nHOST_GID=%s\n' "$(id -u)" "$(id -g)" >> "$ENV_FILE"
    info "added HOST_UID/HOST_GID for the non-root backend"
fi
if [ -n "$(find "$DATA_ROOT/storage" ! -user "$(id -u)" -print -quit 2>/dev/null)" ]; then
    warn "$DATA_ROOT/storage contains files owned by another user — left from when the
    backend ran as root. The container cannot write them now. Fix with:
      sudo chown -R $(id -u):$(id -g) $DATA_ROOT/storage"
fi

# ---------------------------------------------------------------- DNS check

SITE_NOW="$(grep -E '^SITE_ADDRESS=' "$ENV_FILE" | tail -1 | cut -d= -f2- || true)"

if [ -n "$SITE_NOW" ] && [ "$SKIP_DNS_CHECK" -eq 0 ]; then
    step "Checking DNS for $SITE_NOW"

    # Caddy validates over HTTP-01 before issuing. If the record does not resolve
    # here yet, every attempt fails and Let's Encrypt rate-limits failed
    # validations (5 per hostname per hour) — so check rather than discover.
    RESOLVED="$(getent ahostsv4 "$SITE_NOW" 2>/dev/null | awk '{print $1; exit}' || true)"
    PUBLIC_IP="$(curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null || true)"

    if [ -z "$RESOLVED" ]; then
        warn "$SITE_NOW does not resolve yet.
    Create a DNS A record pointing it at this host, wait for it to propagate,
    then re-run. Starting now would burn Let's Encrypt validation attempts.
    Override with --skip-dns-check if you know what you are doing."
        die "aborting before certificate issuance would fail"
    elif [ -n "$PUBLIC_IP" ] && [ "$RESOLVED" != "$PUBLIC_IP" ]; then
        warn "$SITE_NOW resolves to $RESOLVED but this host's public IP is $PUBLIC_IP.
    If your DNS provider proxies traffic (Cloudflare's orange cloud), turn it off
    for this record — HTTP-01 validation needs to reach this box directly."
    else
        info "$SITE_NOW -> $RESOLVED (matches this host)"
    fi
else
    info "SITE_ADDRESS is empty — serving plain HTTP on :80"
fi

# ---------------------------------------------------------------- bring it up

step "Pulling images"
cd "$REPO_ROOT"
docker compose pull

step "Starting"
docker compose up -d

step "Done"
cat <<EOF

  Data root:  $DATA_ROOT
  Config:     $ENV_FILE  (contains your secrets — back it up)
  Address:    ${SITE_NOW:-http://localhost}

  Create the first admin account:

    docker compose exec api uv run python -m app.cli.seed

  Then:  docker compose ps       # check everything is up
         docker compose logs -f  # watch it start

  Upgrading later: set IMAGE_TAG in .env and re-run this script.
  Backups: docs/self-hosting/backups-and-restore.md

EOF
