# First-time setup

After [installing](installation.md) Memship and starting the services, run the setup command to
create your account and configure your organization. It is the same command on every
environment, and it is interactive:

```bash
docker compose exec -it api python -m app.cli.seed
```

Note the `-it`: the command prompts, so it needs a terminal attached.

## The three questions

The setup asks three independent questions, so one command covers every situation.

### 1. Super admin

The account that owns the instance. You choose the address and the password — nothing is
preset, and no credentials for it exist anywhere in this repository.

If a super admin already exists, the setup offers to reset its password instead. That is the
supported recovery path today; see
[issue #40](https://github.com/marcandreuf/memship/issues/40) for the standalone command that
will replace it.

### 2. Club data

Offered only when the instance already holds club data, which on a fresh install it does not.
Answering *yes* deletes every member, activity, receipt, mandate and the organization itself,
after showing you the row counts and asking you to type the organization name to confirm.

It **keeps** the super admin accounts, the system roles, and any payment providers you have
configured. That last one is the reason to use this rather than deleting the database volume:
provider credentials live in the database, encrypted, not in `.env`, so a volume wipe means
re-entering every secret.

This is how you turn an instance you evaluated with demo data into the real thing.

### 3. Club setup

Either enter your organization's real details, or generate a demo club.

For a real deployment, choose **1) real details**. Only the name is required; anything you
leave blank stays blank and can be filled in from **Settings** later. Nothing is invented —
an instance set up this way starts with no tax ID and no IBAN, rather than plausible-looking
placeholders you would have to notice and correct.

Choose **2) demo club** only for evaluation or for a demo you are preparing. It generates a
year of sample data, plus logins for a club admin and two members whose generated passwords
are printed once at the end of the run.

## The three roles

| Role            | What it can do                                                            |
|-----------------|---------------------------------------------------------------------------|
| **Super admin** | Owns the instance: roles, credentials, custom fields, payment providers.   |
| **Club admin**  | Runs the organization day-to-day: members, activities, billing, comms.     |
| **Member**      | Uses the member portal: profile, activities, payments, card, bookings.     |

Narrower roles — a treasurer who only sees billing, for example — are created by the super
admin from **Settings → Roles**. See
[Roles y permisos](../reference/roles-and-permissions.es.md).

## Unattended setup

For automated deployments, the same three steps take flags instead of prompts. The password is
read from the environment, never from the command line, where it would land in the shell
history and in `ps`:

```bash
MEMSHIP_ADMIN_PASSWORD='...' docker compose exec -T api \
  python -m app.cli.seed --admin-email you@example.org --club-name "Your Club"
```

| Flag | Effect |
|------|--------|
| `--admin-email EMAIL` | Create the super admin, or reset its password if it exists. Requires `MEMSHIP_ADMIN_PASSWORD`. |
| `--reset-club-data` | Delete all club data. No confirmation prompt — it is the explicit request. |
| `--club-name NAME` | Create the organization with this name. |
| `--demo` | Generate the demo club and its sample data instead. |

## Log in

Open your Memship URL and sign in as the super admin you just created. Authentication is
**email + password**.

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
