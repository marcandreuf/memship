# Behind your own reverse proxy

Memship ships with Caddy in front of it: it terminates HTTPS, gets the certificate, sets the
security headers and routes each request to the right container. **Use it unless you have a
reason not to.** Installation sets it up, and nothing on this page is needed for it.

> **En español:** [Detrás de tu propio proxy inverso](../../es/self-hosting/reverse-proxy.md).
> **En català:** [Darrere del teu propi proxy invers](../../ca/self-hosting/reverse-proxy.md).

This page is for the other case: a server that already runs a reverse proxy for other sites, or an
organisation whose traffic must all pass through its own proxy. Memship then runs without its
Caddy, and your proxy takes its place. The application containers are the same either way; only
what sits in front of them changes. The supported proxy is **Traefik** (v2 or v3), through
Docker labels.

## What your proxy has to do

These are the bundled Caddy's rules, and an external proxy has to keep all of them:

| Request | Goes to |
|---|---|
| `/api/v1/*` | the API, `api:8000` |
| everything else | the frontend, `frontend:3000` |

**There is no `/uploads` route, on purpose.** Uploaded files reach the browser through the
frontend's `/api/uploads` path, which passes the member's session on to the API's authenticated
uploads router. A rule that sends `/uploads` straight to the API skips that check. When that
router was a static file mount, such a rule handed out the encryption key and the SEPA files. If
your proxy has a habit of adding an `/uploads` route for apps like this one, do not add it here.

Every response also needs these headers, the same ones the bundled Caddy sets:

| Header | Value |
|---|---|
| `X-Content-Type-Options` | `nosniff` |
| `Content-Security-Policy` | `frame-ancestors 'none'` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Strict-Transport-Security` | `max-age=31536000` |
| `Server` | removed |

Do not judge them from a browser tab: the frontend sets four of them itself, so a page can look
complete while every `/api/v1/*` response lacks them. Check with
`curl -s -D - -o /dev/null https://<your-host>/api/v1/health`.

## Setting it up with Traefik

`docker-compose.external-proxy.yml`, next to `docker-compose.yml`, does all of the above with
Traefik labels:

- it switches the bundled Caddy off
- it joins the API and the frontend to your proxy's Docker network
- it routes `/api/v1/*` to the API and everything else to the frontend, with no `/uploads` route
- it adds the six headers as one middleware, attached to both containers
- it gives payment-provider callbacks (`/api/v1/webhooks/*`) a router of their own

**1. Your Traefik.** It must already run with the Docker provider, an HTTPS entrypoint and a
certificate resolver, and be attached to a Docker network the Memship containers can join. Note
the network's name, the entrypoint's name and the resolver's name.

**2. Install as usual,** following the [Installation](../getting-started/installation.md), with
`--domain` set to the hostname your proxy will serve. That writes `FRONTEND_URL`, `CORS_ORIGINS`
and `BACKEND_PUBLIC_URL` as `https://<your-host>`, which email links, sign-in and payment
callbacks depend on. `install.sh` checks that the name resolves to this server, as it does for the
bundled Caddy.

**3. Turn the overlay on in `.env`:**

```bash
COMPOSE_FILE=docker-compose.yml:docker-compose.external-proxy.yml
MEMSHIP_HOST=memship.example.org
TRAEFIK_NETWORK=traefik
TRAEFIK_ENTRYPOINT=websecure
TRAEFIK_CERTRESOLVER=letsencrypt
```

`MEMSHIP_HOST` is the hostname without `https://`. The other three take the names from step 1;
the values shown are the defaults. `COMPOSE_FILE` is what makes every `docker compose` command
read both files, the scripts' included: there is no separate command to remember.

**4. Apply it.** `install.sh` started the bundled Caddy, and switching it off in the overlay does
not stop a container that is already running, so remove it first, then recreate the rest:

```bash
docker compose stop caddy
docker compose rm -f caddy
docker compose up -d
```

Until Caddy is gone it holds ports 80 and 443, and your proxy cannot take them if it runs on the
same server.

**5. Check it**, from any machine:

```bash
curl -s -D - -o /dev/null https://memship.example.org/api/v1/health
```

It should answer `200` with the five headers in the table above and no `Server` line.

## Payment callbacks and access control

If you put the site behind your proxy's basic auth or single sign-on, for a demo or a staging
copy, add that middleware to the `memship-api` and `memship-frontend` routers only, **never** to
`memship-webhooks`. Stripe and Redsys call that path from their own servers and prove themselves
by a signature, not a password: a login in front of it refuses every payment confirmation, and
paid receipts stay unpaid.

## Upgrades, backups and restores

Nothing changes. `upgrade.sh`, `db-backup.sh` and `db-restore.sh` run `docker compose` from the
install directory, so they read `COMPOSE_FILE` and keep the overlay; `push-backup.sh` takes its
dump through `db-backup.sh`.
`install.sh` reloads the bundled Caddy after an upgrade only when Caddy is part of the stack, so
an upgrade never starts it next to your proxy.

The API stays published on `127.0.0.1:8003`, loopback only, as in the default setup.
`verify-deployment.sh` checks the API's health there after an upgrade; nothing outside the server
can reach it.

## Going back to the bundled Caddy

Remove the `COMPOSE_FILE` line from `.env` (the other four can stay, they are then unused), point
the domain's DNS at the server if your proxy lived elsewhere, free ports 80 and 443 if your
proxy runs on the same server, and run `docker compose up -d`. Caddy starts and requests its
certificate.
