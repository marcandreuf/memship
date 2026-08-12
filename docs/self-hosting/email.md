# Email delivery

Memship sends transactional email for welcome messages, password resets, activity
confirmations, waitlist promotions, payment receipts, and overdue reminders. **Email is
disabled until you configure a transport.** Two options are supported.

## Which transport?

| Transport  | Best for                                  | Notes                                              |
|------------|-------------------------------------------|----------------------------------------------------|
| **Resend** | Most self-hosters who want reliable delivery | Managed API, good deliverability, minimal setup. |
| **SMTP**   | Fully self-hosted mail, or an existing mail relay | Works with any SMTP server.                 |

If both are configured, **Resend takes precedence.**

## Option A — Resend

1. Create a Resend account and verify your sending domain.
2. Create an API key.
3. Set in `.env`:

   ```bash
   RESEND_API_KEY=re_your_key_here
   RESEND_FROM_EMAIL=noreply@yourdomain.org
   ```

4. Recreate the backend so it picks up the change:

   ```bash
   docker compose up -d --force-recreate api
   ```

## Option B — SMTP

Set in `.env`:

```bash
SMTP_HOST=smtp.yourprovider.com
SMTP_PORT=587
SMTP_USER=your-username
SMTP_PASSWORD=your-password
SMTP_FROM=noreply@yourdomain.org
SMTP_TLS=true
```

Then recreate the backend:

```bash
docker compose up -d --force-recreate api
```

## Verify

Trigger a real send to confirm delivery — for example, request a **password reset** from the
login page, or create a member and check the welcome email arrives. Emails are localized
(ES/CA/EN) based on the recipient's language.

Use a member or club admin account for the reset test. Super admins are excluded from that
flow by design — their password is reset from the host with `python -m app.cli.seed`, see
[Recovering the super admin password](../getting-started/first-setup.md#recovering-the-super-admin-password)
— so testing with one looks like mail that never arrives.

## Troubleshooting

- **No email at all** — confirm `RESEND_API_KEY` or `SMTP_HOST` is set; if neither is set,
  email is intentionally disabled.
- **Emails delayed** — sending is asynchronous via Celery. Check the worker logs:
  `docker compose logs -f worker`.
- **Links point to the wrong host** — set `FRONTEND_URL` to your public site URL (see the
  [Configuration reference](configuration.md)).
