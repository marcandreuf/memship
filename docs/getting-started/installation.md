# Installation (Docker)

This guide covers a **production** self-hosted install. For a quick local evaluation, use the
[Quick start](quickstart.md) instead.

## Prerequisites

- A server with Docker and Docker Compose
- Git (to clone the repository)
- A domain name and the ability to point DNS at your server (recommended, for TLS)

## Option A — Pre-built images (recommended)

Uses published images from the GitHub Container Registry.

```bash
git clone https://github.com/marcandreuf/memship.git
cd memship

# Configure
cp .env.example .env
```

Edit `.env` — at minimum:

- **`SECRET_KEY`** — set a random 64-character string (never keep the default).
- **`DB_PASSWORD`** — set a strong database password.
- **`IMAGE_TAG`** — pin a released version, e.g. `IMAGE_TAG=1.2.0`. See [Upgrading](../self-hosting/upgrading.md).

See the [Configuration reference](../self-hosting/configuration.md) for every available setting.

```bash
# Pull and start all services (Caddy + API + Frontend + PostgreSQL)
docker compose pull
docker compose up -d

# Run initial setup (creates admin accounts) — see First-time setup
docker compose exec -it api uv run python -m app.cli.seed
```

Open **http://localhost** (or your domain).

## Option B — Build from source

Builds the Docker images locally from the repository source.

```bash
git clone https://github.com/marcandreuf/memship.git
cd memship
cp .env.example .env      # edit SECRET_KEY and DB_PASSWORD at minimum
docker compose up -d --build
docker compose exec -it api uv run python -m app.cli.seed
```

## Services

The default Compose stack runs behind a Caddy reverse proxy:

| Service   | URL                              | Description               |
|-----------|----------------------------------|---------------------------|
| Frontend  | `http://localhost`               | Member portal (via Caddy) |
| API       | `http://localhost/api/v1/health` | Backend API (via Caddy)   |
| API Direct| `http://localhost:8003`          | Backend API (direct)      |

## Next steps

1. [First-time setup](first-setup.md) — create your organization and admin.
2. [Configuration reference](../self-hosting/configuration.md) — review production settings.
3. [Email delivery](../self-hosting/email.md) — required for welcome emails, password resets,
   and payment notifications.
4. [Backups & restore](../self-hosting/backups-and-restore.md) — set up before going live.
