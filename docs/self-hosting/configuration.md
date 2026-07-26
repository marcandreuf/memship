# Configuration reference

Memship is configured through environment variables, typically set in a `.env` file next to
`docker-compose.yml`. Copy `.env.example` to `.env` and adjust. This page documents every
setting the backend reads.

> **Minimum for production:** change `SECRET_KEY` and `DB_PASSWORD`, set `IMAGE_TAG` to a
> released version, and configure [email](email.md).

## Security

| Variable      | Default                 | Description                                                                 |
|---------------|-------------------------|-----------------------------------------------------------------------------|
| `SECRET_KEY`  | `change-me-in-production` | **Change this.** Signing key for auth tokens. Use a random 64-char string. |
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
| `STORAGE_LOCAL_PATH` | `storage` | Local path for uploads (logos, activity images, PDFs). Mounted as a Docker volume — include it in [backups](backups-and-restore.md). |
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
