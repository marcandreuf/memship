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

If a super admin already exists, the setup offers to reset its password instead. That is how a
locked-out operator gets back in — see [Recovering the super admin password](#recovering-the-super-admin-password).

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

### A second super admin

One super admin is a single point of failure: if that person leaves, the only way back in is
shell access to the server. Promote a second one early.

A super admin does it from **Settings → Users**: pick the account and tick **Super admin**.
Only a super admin sees that box enabled — for anyone else it is disabled and labelled as
super-admin-only, because an account cannot grant a role it does not hold. Memship also
refuses to remove the last super admin, so you cannot lock the instance out by demoting
yourself.

The account has to exist first. Today that means the person either signed up themselves
(when public registration is on) or was created by the setup command — there is no
admin-side "invite a user" flow yet.

## Recovering the super admin password

**Only from the host, with `python -m app.cli.seed`.** The browser's forgot-password flow
deliberately refuses super admins: that account holds the roles-and-credentials permissions,
so allowing an email inbox to reset it would make mailbox access equivalent to owning the
instance. It also would not work on most installs — a fresh one has no SMTP configured, which
is exactly when you need recovery.

The request returns the same "if the email exists…" response it gives an unknown address, so
the login page never reveals which accounts are super admins. Nothing arrives by email.

Instead, on the machine running the containers:

```bash
docker compose exec -it api python -m app.cli.seed
```

Answer **yes** to "Reset the password for one of them?", give the address, and type the new
password twice. Answer *no* to the club-data question and choose **3) Skip for now** for the
club setup — a reset changes nothing else.

Unattended, for a scripted recovery:

```bash
MEMSHIP_ADMIN_PASSWORD='...' docker compose exec -T -e MEMSHIP_ADMIN_PASSWORD api \
  python -m app.cli.seed --admin-email you@example.org
```

Every reset is written to the audit log as an update to the account, with no acting user —
whoever ran it had shell access to the host, which the log cannot name. If you find one you
did not run, treat it as you would any other unexplained root-level access.

Ordinary members and club admins are unaffected: they use the normal forgot-password flow,
which needs [email delivery](../self-hosting/email.md) working.

## Unattended setup

For automated deployments, the same three steps take flags instead of prompts. The password is
read from the environment, never from the command line, where it would land in the shell
history and in `ps`:

```bash
MEMSHIP_ADMIN_PASSWORD='...' docker compose exec -T -e MEMSHIP_ADMIN_PASSWORD api \
  python -m app.cli.seed --admin-email you@example.org --club-name "Your Club"
```

**The `-e MEMSHIP_ADMIN_PASSWORD` is not optional.** `docker compose exec` does not pass the
calling shell's environment into the container, so without it the variable is set on your host
and unset where the command runs — and setup stops with
`--admin-email needs the password in MEMSHIP_ADMIN_PASSWORD`. Naming the variable after `-e`,
with no `=value`, is what forwards it without putting the password in `ps` output.

| Flag | Effect |
|------|--------|
| `--admin-email EMAIL` | Create the super admin, or reset its password if it exists. Requires `MEMSHIP_ADMIN_PASSWORD`. Refuses an address that already belongs to an account which is *not* a super admin, rather than resetting a stranger's password. |
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
configured. Set up [email delivery](../self-hosting/email.md) and send a test before
onboarding real members — trigger a password reset from a **member or club admin** account,
since the flow refuses super admins and would look like a delivery failure.

## Next steps

- [Admin guide → Introducción](../admin-guide/overview.es.md) — how the admin panel is organized.
- [Backups & restore](../self-hosting/backups-and-restore.md) — configure before going live.
