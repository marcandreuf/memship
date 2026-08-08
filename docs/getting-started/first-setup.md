# First-time setup

After [installing](installation.md) Memship and starting the services, you need to create the
initial accounts and configure your organization. This is done with the **seed** command.

## 1. Create accounts

Run the interactive seed for a real deployment — it prompts you to create your own super admin
and organization admin, and generates **no** sample data:

```bash
docker compose exec -it api python -m app.cli.seed
```

> **Do not use the `--test` / `--demo` seed modes in production.** They create publicly-known
> credentials and fake data. Those modes are for evaluation only — see the
> [Quick start](quickstart.md).

### The three roles

| Role            | What it can do                                                            |
|-----------------|---------------------------------------------------------------------------|
| **Super admin** | Platform-level administration, including payment provider configuration.   |
| **Org admin**   | Runs the organization day-to-day: members, activities, billing, comms.     |
| **Member**      | Uses the member portal: profile, activities, payments, card, bookings.     |

## 2. Log in

Open your Memship URL and sign in as the organization admin you just created. Authentication
is **email + password**.

## 3. Configure your organization

From the admin panel, go to **Settings** and complete:

- **Branding** — organization name, brand colour, and logo.
- **Address** — used on receipts and legal documents.
- **Banking** — IBAN/BIC, needed for SEPA direct debit.
- **Invoicing** — invoice number prefix, VAT/IVA default rate, and optional annual reset
  (e.g. `FAC-2026-0001`).
- **Default language** — Spanish, Catalan, or English.

## 4. Verify email delivery

Welcome emails, password resets, and payment notifications all depend on email being
configured. Set up [email delivery](../self-hosting/email.md) and send a test (for example, by
triggering a password reset) before onboarding real members.

## Next steps

- [Admin guide → Introducción](../admin-guide/overview.es.md) — how the admin panel is organized.
- [Backups & restore](../self-hosting/backups-and-restore.md) — configure before going live.
