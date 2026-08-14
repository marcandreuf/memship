# Email delivery

Memship sends transactional email for welcome messages, password resets, activity
confirmations, waitlist promotions, payment receipts, and overdue reminders. **Email is
disabled until you configure a transport.**

There are two ways to configure one, and **they are not equivalent** — the settings screen
wins over `.env`. Read [Which one is in effect](#which-one-is-in-effect) before editing
anything, especially on an installation that is already running.

| Where | Providers | Best for |
|-------|-----------|----------|
| **Settings → Integrations → Mailing** | Resend, Gmail | Almost everyone. Takes effect on the next request, no restart. |
| **`.env`** | Resend, any SMTP server | Preseeding credentials at deploy time, and installations older than the settings screen. The only way to use an SMTP server that is not Gmail. |

## Option A — the settings screen

Sign in as superadmin and go to **Settings → Integrations → Mailing**.

The full walkthrough — obtaining the credentials, the DNS records Resend needs, the Gmail app
password, the **Send test** button, and a troubleshooting table — is in the
[Integrations setup guide, section 4](../admin-guide/integrations.md#4-mailing). Two points
from it are worth repeating here because they are the ones that silently bite:

- **Saving credentials does not activate them.** The card badge goes to *Ready*, not *Active*.
  You must then set the **Active provider** selector and save again. Configure → test →
  activate, in that order.
- **With no active provider, mail is silently skipped** — logged, not queued, no error. Nothing
  in the interface reports a send that never happened.

## Option B — `.env`

Set the variables and recreate the backend so it picks them up:

```bash
docker compose up -d --force-recreate api
```

**Resend:**

```bash
RESEND_API_KEY=re_your_key_here
RESEND_FROM_EMAIL=noreply@yourdomain.org
```

**SMTP** (any server — this is the only path for an SMTP host other than Gmail):

```bash
SMTP_HOST=smtp.yourprovider.com
SMTP_PORT=587
SMTP_USER=your-username
SMTP_PASSWORD=your-password
SMTP_FROM=noreply@yourdomain.org
SMTP_TLS=true
```

The full screen-field → environment-variable mapping is in
[Integrations setup guide, section 6](../admin-guide/integrations.md#6-configuration-file-fallback-env).

## Which one is in effect

Three cases, and the difference matters:

| Situation | What sends |
|-----------|------------|
| **The Mailing screen has never been saved** | The `.env` values, exactly as described above: Resend if `RESEND_API_KEY` is set, otherwise SMTP if `SMTP_HOST` is set, otherwise nothing. |
| **The screen has been saved and an active provider chosen** | That provider. Per field, a value saved in the screen wins; a field left empty there falls back to the matching environment variable. |
| **The screen has been saved but no active provider chosen** | **Nothing.** Mail is silently skipped, whatever `.env` says. |

The consequence to watch for: once anyone has saved the Mailing screen, **editing `.env` may
have no visible effect** — the saved value wins and no error is raised. If you configured Resend
in the screen and later change `RESEND_API_KEY` in `.env`, the old key keeps sending. Clear the
field in the screen to fall back to the environment value.

The screen marks fields it is reading from the environment with a **"from environment"** badge,
which is the quickest way to see which source is live.

## Verify

Trigger a real send to confirm delivery — for example, request a **password reset** from the
login page, or create a member and check the welcome email arrives. Emails are localized
(ES/CA/EN) based on the recipient's language.

If you configured through the settings screen, prefer its **Send test** button: it sends through
one specific provider even when that provider is not the active one, so you can verify
credentials before switching real traffic to them.

Use a member or club admin account for the reset test. Super admins are excluded from that
flow by design — their password is reset from the host with `python -m app.cli.seed`, see
[Recovering the super admin password](../getting-started/first-setup.md#recovering-the-super-admin-password)
— so testing with one looks like mail that never arrives.

## Troubleshooting

- **No email at all** — check in this order: (1) **Settings → Integrations → Mailing**, is
  *Active provider* set to something other than *None*? A saved-but-not-activated provider sends
  nothing. (2) If the screen has never been used, confirm `RESEND_API_KEY` or `SMTP_HOST` is set
  in `.env`; if neither is, email is intentionally disabled.
- **Changing `.env` did nothing** — the Mailing screen has a saved value for that field, and it
  wins. See [Which one is in effect](#which-one-is-in-effect).
- **Resend rejects the send (403, "domain is not verified")** — the From address is not on a
  domain verified in Resend, or its DNS records have not propagated. Resend refuses any From
  address outside a verified domain. The one exception is `onboarding@resend.dev`, which needs
  no domain but delivers **only to the address that owns the Resend account** — usable for a
  test, not for real traffic.
- **Emails delayed** — sending is asynchronous via Celery. Check the worker logs:
  `docker compose logs -f worker`.
- **Links point to the wrong host** — set `FRONTEND_URL` to your public site URL (see the
  [Configuration reference](configuration.md)).
