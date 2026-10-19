# Your organisation's domain

[Installation](../getting-started/installation.md) assumes a hostname that already resolves to
your server. This page is about getting to that point when the domain belongs to an organisation
rather than to you: which name to choose, which records to create, and the two or three ways it
goes wrong that cost you an hour each.

Nothing here is specific to memship's internals. If your DNS is already set up and you only want
to install, go straight to [Installation](../getting-started/installation.md).

## Who has to do what

An association's domain is usually not held by the person doing the install. Find out who holds
these before you book an evening for it — waiting on a registrar login is the most common reason
a go-live slips.

| What | Who typically holds it | Needed for |
|---|---|---|
| The registrar account (where the domain was bought) | a board member, or the person who set up the website | nothing, usually — unless DNS is also served there |
| The DNS zone (where records are edited) | whoever runs the organisation's website | the `A` record for memship |
| The organisation's email | sometimes a different provider again | the sending domain, later |
| The server | you | everything else |

The registrar and the DNS provider are often, but not always, the same company. What you need is
whoever can add a record to the zone.

## Choose the hostname

**Use a subdomain, not the apex.** `socios.myclub.org`, `members.myclub.org`, `app.myclub.org` —
whatever the organisation will recognise. The apex (`myclub.org` with no prefix) almost always
already points at the organisation's website, and pointing it at memship takes that website down.

A subdomain also means you never touch an existing record: you add one, and the website keeps
working throughout. If it goes wrong, deleting the record you added puts everything back.

> **memship answers on exactly one hostname.** The `Caddyfile` serves a single site, the one named
> in `SITE_ADDRESS`. There is no `www` alias and no second name: `www.socios.myclub.org` will not
> resolve, and if you did put memship on the apex, `www.myclub.org` would not reach it either.
> Choose the name people will be given, and use that one everywhere.

Pick the name before you install rather than after. It is written into four settings — Caddy's site
address plus the three public URLs that build email links, the CORS origin and the payment-provider
callback — and it is registered by hand in a few other places afterwards; see
[Changing it later](#changing-it-later) for what that costs.

## The records to create

One record. At your DNS provider, in the zone for `myclub.org`:

| Field | Value |
|---|---|
| Type | `A` |
| Name / Host | `socios` (just the label — most providers append the domain for you) |
| Value | your server's **public IPv4 address** |
| TTL | 300 seconds while you are setting up |

A short TTL costs nothing and means a mistake is correctable in five minutes rather than a day.
Raise it afterwards if you like.

### If the server has IPv6

Either add an `AAAA` record with the server's IPv6 address, or make sure the name has **no** `AAAA`
record at all. Both are fine. What is not fine is an `AAAA` record pointing somewhere else — and
on an organisation's domain that is a real possibility, because a wildcard or an inherited record
from the website's host can supply one you never created.

> **This is the trap worth knowing about.** `install.sh` checks the `A` record only, so it reports
> success. Let's Encrypt, validating the certificate, connects over IPv6 when an `AAAA` record
> exists — and it falls back to IPv4 only when the connection *fails*, not when it succeeds and
> returns the wrong thing. A stale `AAAA` pointing at a live web host answers, serves a 404, and
> validation fails. You then have five failed attempts per hour before Let's Encrypt makes you
> wait.
>
> Check for one explicitly: `dig +short AAAA socios.myclub.org` should print your server's address
> or nothing at all.

### What not to do

- **Do not enable your DNS provider's proxy** — Cloudflare's orange cloud, or any "CDN"/"web
  proxy" toggle on the record. Certificate validation has to reach your box directly, and the
  proxy would terminate TLS itself. `install.sh` warns when it detects this, naming it.
- **A `CNAME` works only if it ultimately resolves to this server.** An `A` record is simpler and
  one fewer thing to reason about. Many providers also refuse a `CNAME` at the apex.
- **Do not use the server's hostname from your provider's panel** (`vps-12345.example-host.net`).
  It resolves, so it installs, but it is theirs: it can change, and members will have it in their
  browsers and in every email link.

## Check it, then install

From the server:

```bash
dig +short A    socios.myclub.org    # your server's IPv4
dig +short AAAA socios.myclub.org    # your server's IPv6, or nothing
curl -fsS https://api.ipify.org      # what this host's public IPv4 actually is
```

The first and the third must match. Propagation is usually minutes; a name that resolved to
something else before can take as long as its old TTL.

Then install with the name, following [Installation](../getting-started/installation.md):

```bash
./scripts/install.sh --data-root /srv/openmemship/data \
                     --domain socios.myclub.org --tag 2.19.0
```

> **Leave port 80 open afterwards.** Certificates renew through the same HTTP validation that
> issued them, roughly every 60 days, and a firewall tightened later to "443 only" breaks renewal
> silently — you find out when the certificate expires. `vps-bootstrap.sh` opens 80 and 443, and
> both should stay open.

If DNS is not ready yet and you want to get the stack running anyway, install without `--domain`
and add it on a later run. That is the documented rehearsal path, and
[Installation](../getting-started/installation.md#without-a-domain) explains why it also saves you
from spending certificates.

## Email is a separate domain decision

The address memship sends from does **not** have to be — and usually should not be — on the
subdomain you just created. Members recognise `no-reply@myclub.org`; nobody recognises
`no-reply@socios.myclub.org`.

That means a second set of DNS records, unrelated to the one above:

- The site's `A` record makes the application reachable. It does nothing for email.
- A sending domain needs the records your mail provider asks for — with Resend, a DKIM record plus
  an SPF/MX pair on a `send.` subdomain. The walkthrough is
  [Integrations → Mailing](../admin-guide/integrations.md#4-mailing), and
  [Email delivery](email.md) covers choosing between Resend and SMTP.

Two things to settle with whoever runs the organisation's email, because they are theirs and not
yours:

- **Which address memship sends from**, and that it is on a domain they can add records to.
- **Whether the domain publishes a DMARC policy.** If it does, a new sending service has to align
  with it or the organisation's own mail reputation is affected. Adding memship as a sender is a
  change to their mail setup, not only to yours.

Mail that is not working is invisible by design — [Email delivery](email.md) explains that with no
active provider, sends are skipped and logged rather than queued or reported. Send a test message
from the settings screen before you tell anybody the instance is live, and remember that members
cannot sign in until email works, because they confirm their address first.

## Changing it later

Re-running `install.sh --domain <new-name>` updates `SITE_ADDRESS` and the three public URLs
together, so nothing is left pointing at the old host. What it cannot update is everything outside
memship that was told the old name:

| Where | What breaks |
|---|---|
| Google / Apple SSO | the redirect URI is registered per-hostname and must match exactly, or sign-in fails. [Integrations → SSO](../admin-guide/integrations.md#3-single-sign-on-sso) |
| Stripe webhooks | the endpoint URL is registered in Stripe's dashboard. **Edit the existing endpoint** rather than creating one: a new destination issues a new signing secret, memship stores one, and every event would then fail verification — which looks exactly like a payment that silently never arrives |
| Emails already sent | links in them keep pointing at the old hostname for as long as it resolves |
| Members' bookmarks | the old name has to keep resolving, or be redirected, for as long as you care |

Redsys needs no change: memship sends the callback URL with each transaction rather than having it
registered.

None of that is hard, but it is why choosing the hostname once, before go-live, is worth ten
minutes of thought.

## See also

- [Installation](../getting-started/installation.md) — the install itself, and the certificate
  rate-limit warnings worth reading before your first attempt
- [First-time setup](../getting-started/first-setup.md) — what the organisation has to decide once
  the instance is up
- [Configuration reference](configuration.md) — `SITE_ADDRESS`, `FRONTEND_URL`, `CORS_ORIGINS`,
  `BACKEND_PUBLIC_URL` and the rest
- [Troubleshooting](troubleshooting.md) — when the stack is up but the site is not reachable
