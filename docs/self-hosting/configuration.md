# Configuration reference

Memship is configured through environment variables, typically set in a `.env` file next to
`docker-compose.yml`. Copy `.env.example` to `.env` and adjust. This page documents every
setting the backend reads.

> **Minimum for production:** change `SECRET_KEY` and `DB_PASSWORD`, set `IMAGE_TAG` to a
> released version, and configure [email](email.md).

## Deployment layout

| Variable            | Default  | Description                                                        |
|---------------------|----------|--------------------------------------------------------------------|
| `MEMSHIP_DATA_ROOT` | `./data` | Absolute path holding every persistent path — database, uploads, scheduler state, TLS certificates, backups. Back this up. See [Installation](../getting-started/installation.md#the-data-root). |
| `SITE_ADDRESS`      | _(empty)_ | The address Caddy serves. A bare hostname (`memship.example.com`) makes Caddy provision a Let's Encrypt certificate automatically; empty serves plain HTTP on port 80. |
| `HOST_UID`          | `1001`   | Uid the backend containers run as. Set to your `id -u` so bind-mounted uploads belong to you and are readable without `sudo`. |
| `HOST_GID`          | `1001`   | Gid, likewise — your `id -g`.                                      |

`scripts/install.sh` sets all four for you.

## Security

| Variable      | Default                 | Description                                                                 |
|---------------|-------------------------|-----------------------------------------------------------------------------|
| `SECRET_KEY`  | _(generated into `storage/session.key`)_ | Signs session cookies and member-card QR codes, and derives the key encrypting stored payment-provider credentials. Leave blank and a per-install key is generated on first boot; **set it explicitly** if you want it to survive a lost data root. Generate with `openssl rand -hex 32`. The placeholder values shipped in the example files are recognised and ignored — anything signed with a published key is forgeable. |
| `SESSION_KEY_FILE` | `<STORAGE_LOCAL_PATH>/session.key` | Where the auto-generated signing key is persisted when `SECRET_KEY` is blank. Must sit on persistent storage, or every restart logs all users out and stored payment credentials stop decrypting. |
| `COOKIE_SECURE` | _(derived from `FRONTEND_URL`)_ | Forces the `Secure` attribute on the session cookie on/off. The default reads the `FRONTEND_URL` scheme, which is correct unless TLS is terminated by an upstream proxy that talks plain HTTP to Caddy — set `true` there. |
| `MEMSHIP_SECRET_KEY` | _(generated into `storage/secret.key`)_ | Encrypts SSO and payment-provider credentials stored in the database. **Set it explicitly** — an auto-generated key lives only in the data root, so a rebuilt host cannot decrypt a restored backup without it. Rotating it makes existing stored credentials unreadable. |
| `SECRETS_KEY_FILE` | `<STORAGE_LOCAL_PATH>/secret.key` | Where the auto-generated key is persisted when `MEMSHIP_SECRET_KEY` is unset. Must sit on persistent storage, or stored credentials become unreadable after a restart. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30`      | Access token lifetime in minutes.                                          |

## Database

| Variable        | Default                                                    | Description                                             |
|-----------------|------------------------------------------------------------|---------------------------------------------------------|
| `DB_PASSWORD`   | `memship`                                                  | **Change this.** PostgreSQL password used by Compose.   |
| `DATABASE_URL`  | `postgresql://memship:memship@localhost:5433/memship_db`   | Full connection string. In Compose it points at the `db` service. |

## Application

| Variable         | Default                 | Description                                                        |
|------------------|-------------------------|-------------------------------------------------------------------|
| `APP_ENV`        | `development`            | Set to `production` for deployments. Affects debug behaviour and API docs exposure. |
| `APP_VERSION`    | _(from image / git tag)_ | Baked into the image at build time; leave unset when running published images. |
| `DEFAULT_LOCALE` | `es`                     | Default interface language: `es`, `ca`, or `en`.                  |
| `CORS_ORIGINS`   | `http://localhost:3000`  | Comma-separated list of allowed browser origins. Set to your site URL(s). |
| `FRONTEND_URL`   | `http://localhost:3000`  | Public URL of the frontend; used in email links.                  |
| `BACKEND_PUBLIC_URL` | `http://localhost:8003` | Publicly reachable backend URL for payment-provider callbacks (e.g. Redsys `Ds_Merchant_MerchantURL`). In production this **must** be the external hostname the gateway can POST to. |

## Ports

Set in `.env` for the Compose stack (defaults shown in `.env.example`):

| Variable     | Default | Description                    |
|--------------|---------|--------------------------------|
| `HTTP_PORT`  | `80`    | Caddy HTTP port.               |
| `HTTPS_PORT` | `443`   | Caddy HTTPS port.              |
| `API_PORT`   | `8003`  | Direct backend API port.       |
| `DB_PORT`    | `5433`  | PostgreSQL host port.          |

## Email

Email is **disabled** unless either a Resend API key or an SMTP host is set. See
[Email delivery](email.md) for a full walkthrough.

**Resend (preferred, managed delivery):**

| Variable            | Default | Description                     |
|---------------------|---------|---------------------------------|
| `RESEND_API_KEY`    | _(empty)_ | Enables Resend delivery.       |
| `RESEND_FROM_EMAIL` | _(empty)_ | Verified sender address.       |

**SMTP (self-hosted alternative):**

| Variable        | Default                 | Description                          |
|-----------------|-------------------------|--------------------------------------|
| `SMTP_HOST`     | _(empty)_               | Enables SMTP delivery when set.      |
| `SMTP_PORT`     | `587`                   | SMTP port.                           |
| `SMTP_USER`     | _(empty)_               | SMTP username.                       |
| `SMTP_PASSWORD` | _(empty)_               | SMTP password.                       |
| `SMTP_FROM`     | `noreply@memship.local` | From address.                        |
| `SMTP_TLS`      | `true`                  | Use STARTTLS.                        |

If both are configured, Resend takes precedence.

## Background jobs (Celery / Redis)

| Variable            | Default                    | Description                                                |
|---------------------|----------------------------|------------------------------------------------------------|
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Redis broker for async email, recurring billing, reminders. Redis is included in the Compose stack. |

The worker and scheduler (Celery beat) run as part of the stack and power async emails,
scheduled fee generation, and payment reminders.

## File storage

| Variable             | Default   | Description                                              |
|----------------------|-----------|----------------------------------------------------------|
| `STORAGE_LOCAL_PATH` | `storage` | In-container path for uploads (logos, activity images, PDFs). Bind-mounted from `$MEMSHIP_DATA_ROOT/storage`, which also holds `secret.key` — include it in [backups](backups-and-restore.md). |
| `MAX_UPLOAD_SIZE_MB` | `10`      | Maximum upload size in megabytes.                        |

## Server

| Variable | Default   | Description                  |
|----------|-----------|------------------------------|
| `HOST`   | `0.0.0.0` | Bind address of the backend. |
| `PORT`   | `8000`    | In-container backend port.   |

## Migrations

| Variable         | Default | Description                                                             |
|------------------|---------|-------------------------------------------------------------------------|
| `RUN_MIGRATIONS` | _(set to `1` in Compose)_ | When `1`, the backend runs database migrations on startup. See [Upgrading](upgrading.md). |
