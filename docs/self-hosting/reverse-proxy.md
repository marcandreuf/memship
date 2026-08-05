# Reverse proxy

Memship ships with a reverse proxy already configured. Something has to terminate
HTTPS and route requests to two different containers, so the stack includes
**Caddy** and it works without configuration beyond your hostname.

If you already run a proxy on the same server, you can use that instead and turn
the bundled one off. Both are supported.

## Which one you want

**Use the bundled Caddy** if memship is the only thing on the server, or the main
thing. This is the default and the recommended path. You get automatic HTTPS with
no certificate files to manage and no account to create anywhere.

**Use an external proxy** if the server already terminates TLS for other sites, if
you are deploying to Docker Swarm, or if your organisation has a proxy it wants
everything to sit behind.

Whichever you pick, **the application containers are identical.** Only what sits
in front of them changes.

## The default: bundled Caddy

Set your hostname in `Caddyfile`, replacing `:80`:

```
memship.yourclub.org {
    handle /api/v1/* {
        reverse_proxy api:8000
    }
    handle /uploads/* {
        reverse_proxy api:8000
    }
    handle {
        reverse_proxy frontend:3000
    }
}
```

Then:

```bash
docker compose up -d
```

Caddy requests a certificate from Let's Encrypt on first start and renews it
automatically. For that to work:

- the hostname must already resolve to this server's public IP, and
- ports **80 and 443** must be reachable from the internet. Port 80 is used for
  the certificate challenge, so do not close it even though the site itself is
  HTTPS.

Certificates are kept in the `caddy_data` volume. Leave that volume alone —
deleting it means requesting new certificates, and Let's Encrypt applies rate
limits.

Keep the three route blocks in that order and do not drop `/uploads/*`: uploaded
files — your organisation's logo, member photos, activity images — are served by
the API, not the frontend. Without that block they will not load.

## The alternative: an external proxy

```bash
docker compose -f docker-compose.yml -f docker-compose.external-proxy.yml up -d
```

This override does three things: it removes the bundled Caddy (via a Compose
profile that is never activated), it stops publishing the API and PostgreSQL
ports on the host, and it attaches the API and frontend to an external Docker
network with routing labels for [Traefik](https://traefik.io).

Set these in `.env` first:

```bash
MEMSHIP_HOST=memship.yourclub.org
TRAEFIK_NETWORK=traefik_proxy       # the network your Traefik watches
TRAEFIK_CERTRESOLVER=cloudflare     # a resolver defined in your traefik.yml
```

The network must already exist and your Traefik must be attached to it:

```bash
docker network create traefik_proxy
```

Three routers are published, and the priorities matter:

| Router | Matches | Priority |
|---|---|---|
| `memship-webhooks` | `/api/v1/webhooks/*` | 30 |
| `memship-api` | `/api/v1/*` and `/uploads/*` | 20 |
| `memship-frontend` | everything else | 10 |

**If you add an authentication middleware** — to keep a test or demo site
private — apply it to `memship-api` and `memship-frontend` only. Payment
providers POST to the webhook endpoints from their own servers and cannot present
credentials, so an auth middleware covering them silently breaks payment
confirmation. That is why webhooks are a separate router with no middlewares
attached. Those endpoints verify a provider signature on every request, which is
their real protection.

### Using another proxy

Nginx, HAProxy, Apache or anything else works too — the override's Traefik labels
are simply ignored by a proxy that does not read them. Route to the containers on
the shared network with the same three rules:

- `/api/v1/*` → `api:8000`
- `/uploads/*` → `api:8000`
- everything else → `frontend:3000`

Set `MEMSHIP_HOST` and `TRAEFIK_NETWORK` anyway, since the override requires them;
`TRAEFIK_CERTRESOLVER` can be any value, as nothing will read it.

## After changing the proxy

Whichever proxy terminates TLS, these must match your real public URL or logins
and single sign-on will fail:

```bash
FRONTEND_URL=https://memship.yourclub.org
CORS_ORIGINS=https://memship.yourclub.org
BACKEND_PUBLIC_URL=https://memship.yourclub.org
```

`BACKEND_PUBLIC_URL` is what the SSO callback URL is built from, so it has to
match the redirect URI registered with Google or Apple exactly, including
`https://`.

## A note on published ports

The default `docker-compose.yml` publishes the API on `8003` and PostgreSQL on
`5433` so you can reach them while setting things up. **On a public server, close
them.** A host firewall is not enough on its own: Docker inserts its own iptables
rules, and a published port can stay reachable from the internet even when `ufw`
is configured to deny it. Either set `API_PORT` and `DB_PORT` to bind to
`127.0.0.1`, or use the external-proxy override, which stops publishing them
altogether.
