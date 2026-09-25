🌐 **English** | [Español](README.es.md) | [Català](README.ca.md)

# Memship

> **This project is under active development and open to any feedback via gihub [issues or feature requests](https://github.com/marcandreuf/memship/issues).**

**Membership management for everyone.**

Memship is a self-hosted, open-source membership management system designed for professional associations, sports clubs, cultural organizations, and any member-based entity. Deploy it on your own infrastructure, own your data, and manage your community with modern tooling.

---

## What we're building

Most membership tools are either expensive SaaS platforms or outdated legacy software. Memship aims to change that — a modern, full-featured solution that you control. No vendor lock-in, no per-member pricing, no data leaving your servers.

- **Self-hosted** — runs on any server with Docker
- **Single-tenant** — one database per organization, complete data isolation
- **Multi-language** — Spanish, Catalan, and English from day one. Extensible to any language via community contributions
- **GDPR-ready** — built-in legal terms templates and consent management

## Quick Start (Docker)

> **For trying memship out, not for running it.** This is the fastest path to a
> working instance on your own machine: published images, throwaway volumes, and
> a fixed database password. To run memship for a real organization, follow
> [Installation](docs/getting-started/installation.md) instead — same product,
> set up so it can be backed up, upgraded and kept.

Try memship with a single command — no cloning required:

```bash
mkdir -p "$HOME/memship-quickstart" && cd "$HOME/memship-quickstart"
curl -fsSL https://raw.githubusercontent.com/marcandreuf/memship/main/docker-compose.quickstart.yml -o docker-compose.yml
docker compose pull        # fetch the latest published images
PORT=8081 docker compose up -d
```

Then run the setup, which walks you through three questions:

```bash
docker compose exec -it demo-memship-api python -m app.cli.seed
```

1. **Super admin** — you choose the address and password. Nothing is preset.
2. **Club data** — offered only if there is any, so it is a no-op on a fresh install.
3. **Club setup** — enter your organization's real details, or generate a demo club.

Choose the demo club to look around: it creates a full year of realistic sample
data — ~60 members across all statuses, activities, receipts in every state
spread across the months, SEPA mandates and dashboard reminders. It also
generates logins for a club admin and two members and **prints those passwords
once**, so keep the output. Safe to re-run (idempotent).

Open http://localhost:8081 and log in as your super admin. Change `PORT=8081` to
any port you prefer (default is 80).

Once you are done evaluating, re-run the same command and answer *yes* to the
club-data question: it clears the demo club while keeping your super admin and
any payment providers you configured. See
[First-time setup](docs/getting-started/first-setup.md).

## Releases

Memship follows [semantic versioning](https://semver.org/), and **version numbers are assigned at release time — never reserved in advance.** One line per version below; the full notes for each are on the [releases page](https://github.com/marcandreuf/memship/releases). What is coming next is under [Roadmap](#roadmap), and [Choosing a version](CONTRIBUTING.md#choosing-a-version) covers how a number is picked.

| Version | Milestone | Status |
|---------|-----------|--------|
| v0.1.0 | Member Management MVP — auth, RBAC, member CRUD, membership types, i18n, Docker, CI | Done |
| v0.1.1 | Email sending (SMTP) — welcome emails, password reset emails | Done |
| v0.1.2 | Groups, guardian/minor support, restricted role (schema) | Done |
| v0.1.3 | Caddy reverse proxy, backup/restore scripts, self-hosted polish | Done |
| v0.1.4 | Organization settings management (API + frontend) | Done |
| v0.1.5 | Activity CRUD — models, modalities, pricing, admin frontend | Done |
| v0.1.6 | Strong entity pattern — unified list/detail/tabs across all entities | Done |
| v0.2.0 | Activity Management — registration, eligibility, waitlist, discounts, consents, attachments | Done |
| v0.2.1 | UX refactor — Shadcn sidebar, dark mode, brand colors, compact tables, quick start | Done |
| v0.2.2 | E2E test foundation (Cypress) — auth, members, activities, registrations | Done |
| v0.2.3 | Error handling & validation hardening — toast notifications, global error handler, backend schema validation, StrEnum, 76 validation tests, 16 E2E tests | Done |
| v0.2.4 | Bug fixes — dark mode sidebar, form error display, route guards, member list cancelled visibility, member delete removed | Done |
| v0.2.5 | Activity UX — member activity card redesign, cover image upload, registration status badges, activity list thumbnails, My Activities grid, Docker storage volume | Done |
| v0.2.6 | Bug fixes & testing — Shadcn confirm dialogs (replaced 13 browser alerts), seed discount code fix, self-cancellation deadline check, re-registration after cancel, 21 new API tests, 9 new E2E eligibility tests | Done |
| v0.2.7 | Activity polish — loading skeletons, nuqs URL state | Done |
| v0.2.9 | Payment prerequisites — org address & banking, logo upload, contact info tab, member IBAN, Celery/Redis, email notifications (Jinja2 + SMTP/Resend) | Done |
| v0.3.0 | Basic Payments & Invoicing — receipts, PDF generation, VAT, fee generation, member payment history | Done |
| v0.3.1 | Bug fixes — failing tests and translated readme files | Done |
| v0.3.2 | Bug fixes — frontend build pipeline fix | Done |
| v0.3.3 | CI improvements — faster test execution | Done |
| v0.3.4 | Bug fixes — warning cleanup and integration test optimizations | Done |
| v0.3.5 | Bug fixes — failing integration tests | Done |
| v0.3.6 | CI optimization — setup-uv v7, cached password hashing, pytest-xdist parallel workers, automated version hooks | Done |
| v0.4.0 | SEPA Direct Debit — mandate management, remittance batches, pain.008 XML, member payment method | Done |
| v0.4.1 | Payment provider settings — super admin configurable payment gateway management | Done |
| v0.4.2 | Webhook infrastructure + Stripe Checkout — provider webhooks, real-time payment status, member "Pay Now" flow | Done |
| v0.4.3 | Redsys integration — Spanish bank gateway with 3D Secure + Bizum | Done |
| v0.4.4 | Recurring billing — scheduled fee generation | Done |
| v0.4.5 | Payment reminders — overdue email notifications | Done |
| v0.5.0 | Simple Communications — admin announcements to all/group/membership type | Done |
| v0.5.1 | Communications sent view — recipient tracking + in-app "Seen" | Done |
| v0.7.0 | Digital Member Card + QR Check-in — PDF card, auto member numbers | Done |
| v0.7.1 | Member card polish — admin card view on member page, member profile photo upload, profile page redesign | Done |
| v1.0.0 | Stabilization & Release — CSV exports, finance dashboard, notes & reminders, annual summary, demo seed, docs polish | Done |
| v1.0.1 | Patch — fix Celery scheduled billing/reminder task registration; CI guard against image tag overwrite | Done |
| v1.1.0 | Custom profile fields — org-configurable member data (text, number, date, select, …) with per-field validation and per-field visibility/editability | Done |
| v1.1.1 | Patch — settings navigation reorganised: payment and member settings grouped under Payments and Members tabs | Done |
| v1.2.2 | SSO and mailing configuration — public registration with email verification and an admin approval flow, Google / Apple sign-in, and Resend / Google SMTP setup from an Integrations tab | Done |
| v1.3.0 | Simple Bookings — member reservations of shared spaces on a week calendar, with per-slot capacity and a FIFO waitlist | Done |
| v1.4.0 | Flexible roles & permissions — multi-role assignment and granular per-permission checks in place of the four fixed roles. Also repairs deployment stacks that ran no Celery worker and mounted no volume on the API service | Done |
| v2.0.0 | Self-hosting overhaul — host-visible bind mounts under one `MEMSHIP_DATA_ROOT`, backend containers running as the operator's uid, and a one-command `install.sh`. **Security:** PostgreSQL and the API are no longer published to the internet. **Breaking:** `uv run` no longer works in the containers, and existing installs need a one-off `chown` | Done |
| v2.1.0 | Setup without published credentials — the same interactive setup on every environment, with no accounts whose passwords ship in this repository, plus unattended flags for scripted installs | Done |
| v2.2.0 | Super admin recovery from the host — a super admin's password is reset with `python -m app.cli.seed` on the server rather than by email. **Security:** mailbox access was equivalent to owning the instance | Done |
| v2.3.0 | Uploaded files behind authentication, and sign-in that cannot be guessed at forever — **Security:** the storage directory was served by a static-file mount, reset tokens came back in API responses, and the published placeholder signing key was the Compose default. **Breaking:** installs on that placeholder key get a fresh one, signing everyone out | Done |
| v2.3.1 | Money paths that were wrong quietly — a SEPA file no longer drops receipts whose mandate was cancelled, a payment webhook no longer records a mismatched amount as paid in full, and an activity can no longer be over-booked by two people registering at once. **Behaviour:** a remittance whose mandate vanished now fails with an error instead of producing a short file, and a payment for the wrong amount leaves the receipt unpaid for review | Done |
| v2.4.0 | Sign-in requires a confirmed email address, and invoice numbers are sequential and unbroken. **Breaking:** an account that never confirmed its address can no longer sign in — `python -m app.cli.verify_email` confirms one from the host when the confirmation email is what is broken. **Migration:** receipt numbering moves to a counter per year, seeded from the numbers already issued | Done |
| v2.5.0 | Every outbound email in one branded layout — the organisation's name, logo and colour come from the settings row, every message now carries a plain-text alternative alongside the HTML, and receipt delivery and the recurring-billing summary are templates rather than inline markup. Also: a registration whose receipt fails to generate is no longer rolled back with it, and `SEED_EMAIL_DOMAIN` lets an install that deliberately sends real mail seed a demo club at a domain that can receive it | Done |
| v2.6.0 | A super admin chooses which emails the system sends — a Settings screen with a switch per template, and all 17 senders routed through one gate instead of mailing unconditionally. The announcements feature flag now closes its endpoints rather than only hiding the navigation, and an unreadable template policy fails closed, because it is not consent. **Breaking:** optional email now defaults to off, so an existing installation goes quiet on upgrade until a super admin enables the templates it wants — only address verification and password reset keep sending | Done |
| v2.7.0 | Sessions that slide rather than expiring mid-task — an active session renews itself halfway through its window, and when it does run out it says so and returns you to sign-in instead of failing a request silently. Spaces and the billing lists move onto the same list and detail chrome the rest of the app already uses, and the last English-only screens are translated. **Self-hosting:** a release deploys to a VPS that holds no git and no source checkout; the install and upgrade guides fetch a release tarball instead of cloning; and a first install now names the file holding the keys a lost host would take with it, with `scripts/pull-backup.sh` to copy them off | Done |
| v2.7.1 | A first install now leaves a `POST-INSTALL.md` on the server listing what the installer cannot do for you — copy `.env` off the host, create the organization and super admin, schedule backups and get them off the machine, configure email before mail is dropped silently — with every path filled in. A first deploy repeats the first of those at the top of the run page. The v2.7.0 warning was correct and unread: it landed at line 248 of an 1,150-line log, inside a collapsed step. **Also:** `pull-backup.sh`'s usage examples no longer carry a real host alias and SSH port | Done |
| v2.8.0 | Membership a member buys, and can lose — a plan is bought from the member's own portal at a prorated, tax-inclusive price, granted when the money arrives by any route (card, cash an admin records, or a SEPA remittance reconciled days later), and given up 21 days after an unpaid fee falls due, with the tier that was lost recorded so paying restores it. Spaces gain a price and a list of the membership types allowed to book them, and every confirmation path — a direct booking and a waitlist promotion — raises a receipt. **Billing:** an issued receipt is rectified by a credit note instead of being cancelled and reissued, so the number series Spanish invoicing treats as legally significant stays unbroken and a paid receipt can be corrected at all; and closing a SEPA remittance now settles the receipts the bank never reported as failed, which had been sitting emitted forever. **Fix:** self-registration assigned the oldest membership type rather than a free one, silently starting a recurring fee nobody agreed to — `is_default` marks the tier sign-ups land on, enforced by the database, and a Paid tier check report lists the members the bug left on a paid plan. **Behaviour:** a membership fee gets its own seven-day window under `membership_fee_due_days` in place of `recurring_billing_due_days`, and tier reversion stays off until a club switches it on | Done |
| v2.9.0 | The screen a member buys their plan on — v2.8.0 could take the money but left no way to ask for it. The portal now has a **My plan** page listing the plan held and the plans available, and showing the prorated first charge before anything is confirmed: net, VAT and total to pay today, with a line saying which months it covers and what the full fee will be next period. Buying raises a receipt and nothing more — the plan activates when that receipt is paid, an unpaid one voids itself at its due date and charges nothing, and where card payment is switched on it can be paid on the spot. A member reverted to the free tier for non-payment is told which plan paying restores. **Fix:** `seed --test` numbered its receipts from a private counter without advancing the year's invoice sequence, so the next receipt created afterwards collided on a duplicate number and failed — the seeder now carries the counter past the numbers it issued. Test data only; a real installation seeds no receipts and was never affected | Done |
| v2.9.1 | A first install that can follow its own instructions — every fix here was found running the guide end to end on a fresh server. `vps-bootstrap.sh` aborted part-way whenever Ubuntu's own boot-time apt run held the dpkg lock, leaving a host with Docker and a privileged deploy account but **no firewall and no fail2ban**, after output that read like success; it copied only the *first* key out of the `authorized_keys` file the guide tells you to point it at, so the deploy user was unreachable with any of the others; and it closed by printing steps that cannot be run — telling an account deliberately created with no password to use `sudo`, and creating one of the two directories the install needs, so `install.sh` stopped at `cannot create /srv/openmemship/data`. It also added a second copy of Docker's apt repository on any host where Docker was already installed. **Quick start:** now says where to put itself — the Compose project, and so the data, is named after whatever directory you happen to run the first command in — and how to stop it, pause it, and remove it completely | Done |
| v2.10.0 | Thirteen fixes to the paths that handle money, personal data and load — no new screens. **Security:** password-reset and email-verification tokens are stored as SHA-256 digests and compared in constant time, so the `users` table, a backup or a log no longer holds anything that can be presented; `GET /members/me/payment-method` stops returning the full IBAN beside its masked form, and the member's form treats the account number as write-only; and the admin CSV exports prefix any cell opening with `=`, `+`, `-`, `@`, a tab or a carriage return, so a member's own name can no longer arrive as a live formula in the spreadsheet of the person with the most access. **Money:** a discount code's usage cap is decided under a row lock and given back when the registration is cancelled, so two redemptions arriving together can no longer both pass it; remittance numbers come from a locked per-year counter instead of a count of the rows, as receipt numbers already did; and receipt totals are derived from what the admin entered — base gross, discount as a percentage or a fixed sum — so editing the discount on a receipt changes the total instead of being silently dropped. **Correctness:** registration, cancellation and waitlist-promotion emails wait for the transaction to commit rather than racing it, so nobody is told about a registration that was rolled back; an admin correcting a member's address now moves the login with it, refusing an address another account signs in with; narrowing a space's opening hours checks the bookings already taken outside the new window and refuses with the counts unless forced; and a discount code matches whatever case it was typed in. **Performance:** list endpoints skip the `COUNT(*)` when the page already tells the total — the usual case for a club — and a week of booking availability loads in two queries rather than two per slot. **Behaviour:** the admin's "send reminder" button hands the mail to the worker instead of holding the request open on SMTP. **Breaking:** outstanding password-reset and email-verification links stop working on upgrade; a member holding an unused verification link asks for a new one. **Migration:** existing discount codes are upper-cased, leaving any that would collide on the same activity for a person to resolve; discounted receipts move to the new base-and-discount shape with their VAT and totals unchanged; and each year's remittance counter is backfilled from the highest number already issued | Done |
| v2.11.0 | Staff are not members of the club — a super admin or club admin now administers the instance without belonging to it. `member` used to be pinned to every account by `assign_roles`, and re-added by `replace_user_roles` whatever an admin had selected, so an operator carried a member number, a membership type and a place in every member count, export, annual summary and billing run — and the role could not be taken off through the UI or the API either. It is granted where it is meant now: self-registration, SSO sign-up, and the seed paths that create members. A fresh install opens its register with the club's first actual member on **M-0001** rather than the operator. What separates staff from members is the **member record**, not a permission: every staff account holds all twelve `self.*` keys and always will, because those are the floor on the endpoints staff and members share — `/members/{id}` and the receipt PDFs widen from them rather than branch on them, so taking them away would lock an admin out of the member register. The portal's personal navigation, the profile page and the member pages therefore hang off the member record, and an operator gets the staff nav and nothing else. `treasurer` deliberately stays a member: a club officer who is also a member, whose `billing.*` role grants nothing of its own. **Behaviour:** five routes that resolved the caller's own member row disagreed about the answer when there wasn't one — registrations said 400, membership purchase and `/members/me/receipts` said 404, the card and booking routes said 403. All five now answer `403` with `{"code": "not_a_member"}`; the request is well formed and the caller is known, what is missing is a membership. **Fix:** the profile page waited on a member that never arrived and rendered its skeleton forever for an operator — on a page the user dropdown links to; and the activities list and an activity's detail page asked for the caller's own registrations and eligibility on every visit, three guaranteed refusals on pages an admin opens constantly. **Migration:** an existing install's staff accounts lose their member record and their `member` role. A member row is **left alone** when a receipt or a SEPA mandate points at it — an account with billing history behind it is one a person should look at, not one a migration should quietly rewrite. **This is not reversible:** the rows and the member numbers they held do not come back, the member count drops by the number of operator accounts the install had, and `downgrade()` restores only the role assignment | Done |
| v2.12.0 | Sign-in, mail, payments and the upgrade itself — the paths a club trips over in its first weeks on a fresh install. **Sign-in:** email addresses are stored stripped and lower-cased and compared that way everywhere, so a member who registered as `Marc@example.com` can sign in and reset a password as `marc@example.com` — including the super admin `install.sh` creates, which no spelling could sign in as; and the public signup form answers a taken address exactly as a free one, same status, same body, same time, instead of confirming who is a member. **Mail:** a member who self-registered before a mail provider was configured could never confirm their address, showed as active, and nothing in the product could unstick them — `/auth/register` and `/auth/resend-verification` now refuse with `503` until a transport exists, the member detail page shows an unconfirmed address with a **Confirm address** button, and the audit row says an admin did it; a member's email opt-out is honoured on every mail rather than announcements alone; announcements report how many emails went out rather than how many could have; a switched-off reminder template is no longer logged as a failed delivery; the waitlist email that crashed on an extra argument now sends and tells the member their position in the queue; and the never-sent welcome mail is removed rather than left outside the opt-in gate. **Payments:** a provider whose credentials are still empty can no longer be switched on — `create`, `update` and `toggle` run the same validation `/test` does and answer `provider_not_ready` naming the fields, as codes the UI translates rather than English sentences; and the registration page quotes members the tax-inclusive price they will be invoiced, as the membership purchase flow already did. **Activities:** the creation form gained the `tax_rate` field it was missing, so a new activity no longer defaults to 0% and misprices its receipts; and the membership-type restriction the backend already enforced can now be set from both activity forms. **Correctness:** `members.user_id` is unique, and the caller's own member row resolves to the live, most recent one rather than whichever came first; and the `member` role can be granted and revoked from the Accounts editor like any other. **Operations:** `upgrade.sh` pulls every image of the target release and asks the new API about the data *before* replacing the stack, so a migration that refuses leaves the old version running instead of a crash loop; and `TRUSTED_PROXY_HOPS` (default `1`, the bundled Caddy) states how many proxies sit in front of the API, so the login throttle no longer collapses every caller into one bucket behind a second proxy. **Migration:** existing addresses are lower-cased — the migration refuses when two accounts hold one address in different cases, which is a decision between two people's logins, and the upgrade preflight reports it before anything is replaced; a login holding several member rows keeps the active, most recent one and the rest are detached from it, their numbers and history untouched; and announcements gain a real sent count | Done |
| v2.13.0 | The audit release — seventeen defects found by reading the code against its own documentation, none of them a feature. **Sessions:** resetting a password now ends every session that password opened; a JWT used to stay valid until it expired and `/auth/refresh` let an active one slide indefinitely, so whoever had the old password kept the access the reset was meant to end. A locked account is refused by the uploads router the way it is refused everywhere else. **Throttles:** the Next.js proxy forwards the caller's address to the API, so the login, signup and reset throttles key on the caller — twenty-one bad passwords from anywhere no longer lock every member out for fifteen minutes — and forwards `Retry-After` back, so a throttled caller is told how long to wait. The proxy is not a hop: `TRUSTED_PROXY_HOPS=1` stays right whether a request came through it or straight to `/api/v1`. **Addresses:** email addresses are ASCII-only, so the application and the unique index fold case the same way — `İ` folded to two different strings and let one typed address be stored twice under an index meant to forbid that — and a migration trims tabs and line breaks that the first normalisation left behind; SSO refuses a non-ASCII provider address with its own message. **Words, not codes:** booking errors reach the UI as codes the three languages translate, with the dates a series failed on, instead of the raise site's English; a permission refusal or any other bare code toasts a sentence rather than `forbidden` or "Validation error". **Dates:** billing stamps emission, payment and return dates in the club's timezone rather than the UTC container's, so a credit note issued at 00:30 on 1 January no longer takes the old year's number. **Files:** replacing a photo, logo or cover commits the row before touching the old file, and deleting one commits before unlinking, so a failed commit leaves a working image rather than a broken one; a failed attachment insert removes the file it wrote. **Small:** three lists honour `per_page` instead of silently serving the default; `apiClient` keeps `Content-Type` when a caller passes headers; the payment return pages keep the member's language. **Development:** the API container reloads on a change under `app/` as the docs promised, and `dev.sh test` starts every run on a fresh database so a new column is never invisible to the suite | Done |
| v2.14.0 | The bug-bash release — sixteen reported defects and a build that could ship an image unable to start, no new features. **Build:** the backend image never used `uv.lock` — it was not even in the build context — so every build re-resolved dependencies from PyPI; SQLAlchemy 2.1.0 turned that into an image whose `alembic upgrade head` died on a missing `psycopg`. Builds now install the lockfile with `--locked`, and every RC image is booted — backend against a throwaway Postgres through its migrations, frontend serving a page — before it is pushed. **Money:** the activity detail returned prices with VAT zeroed, so the sign-up page showed a 55 € + 10 % price as "0,00 €"; deleting a slot or space now voids its unpaid booking receipts instead of leaving members owing for a seat that no longer exists. **Visibility:** a member got 404 on an unpublished activity but could still read its prices, consents and modalities; every member-readable sub-resource now applies the same rule. **Rules that were stored but not applied:** age limits now bind — a member with no birth date no longer passes every age gate, plans refuse a buyer outside their range, and admins can set the limits at all; booking window and cancellation deadline are range-checked on save and a bad stored value falls back to the default instead of a 500; gender is validated against the organization's options; every feature-gated page redirects when its flag is off. **Forms:** an emptied field is cleared on save rather than silently kept behind a success toast, and whitespace is refused wherever a value is required. **Lists:** search matches a full name as the table shows it, word by word and — on groups and spaces — ignoring accents; lists sharing a `created_at` break ties on `id`, so pages no longer repeat or skip rows and the waitlist promotes deterministically; the member dashboard lists upcoming activities soonest first; Mis reservas says a booking is past its cancellation deadline instead of offering a button that can only fail. **Words:** about fifty Spanish and Catalan strings regain their accents, eligibility reasons are translated, the settings tabs are no longer duplicated, and the BIC hint stops claiming it is derived from the IBAN | Done |

## Roadmap

Priority-ordered, not yet versioned. Each becomes a versioned release when it ships, and the release claims the next semver number in order. Each item has an issue carrying its summary and current thinking — see the [`roadmap` issues](https://github.com/marcandreuf/memship/labels/roadmap).

- **User invitations** — invite a new super admin, club admin or member by email address and role; they set their own name and password. Sent by email where email is configured, and as a copyable link where it is not, so a freshly installed instance can add a second administrator without shell access
- **Data backups** — download a full backup from the admin area, covering the database and the uploaded files, with a documented and tested restore
- **Convocations** — formal General Assembly calls with token-based member RSVP
- **Document library** — statutes, minutes, forms with per-group visibility
- **Events calendar + RSVP** — calendar view and participation tracking
- **Integrations** — connect memship to the tools a club already runs on, instead of asking it to move. Instant messaging first (WhatsApp, Telegram, Signal, Instagram), since that is where most clubs actually communicate; then calendar subscriptions, accounting and e-invoicing exports, sports-federation licence submissions, and outbound webhooks as the generic escape hatch. Each connector has its own cost and constraints and ships on its own

Complex variations are built on demand, when a real deployment needs them: GoCardless e-mandates, PayPal, Stripe Invoice flow, bulk receipt actions, custom report builder, surveys, family group billing, paid & recurring bookings, equipment rental, convocation voting & document attachments, and similar deeper cuts of the features above.

**Deferred — extensions as a modules/plugins system.** Optional add-ons such as photo albums, a forum, a guestbook, a weblinks directory, inventory/lending and portal widgets need a module system designed into the architecture rather than added on top of it. This waits for a future revision of that architecture instead of shipping as a feature.

---

## Features

**Member Management** (available now)
- Full member lifecycle: registration, onboarding, status changes, cancellation
- Membership types with groups, pricing, and age restrictions
- Guardian/minor support
- Role-based access: super admin, org admin, member
- Organization settings with branding (color, logo upload), address, banking (IBAN/BIC), invoice series
- Member contact info management (phone, email, with contact types)
- Member bank details (IBAN/BIC) for SEPA direct debit
- Multi-language interface (ES, CA, EN) with locale selector in profile
- Admin dashboard with status charts (recharts)
- Unified entity pattern: list → detail → tabs for all entities
- Email notifications (registration confirmation, cancellation, waitlist promotion) via Celery/Redis
- Dual email transport: SMTP (self-hosted) or Resend API (managed)
- Jinja2 email templates with locale support (ES/CA/EN)

**Activities & Events** (available now)
- Activity creation with lifecycle management (draft → published → archived)
- Cover image upload per activity (admin upload, member-visible thumbnails)
- Modalities (variants with independent capacity, pricing, and deadlines)
- Pricing tiers with time-based validity (early bird pricing)
- Online registration with eligibility checks (membership type, age, status)
- Capacity management with automatic waiting list and promotion
- Self-cancellation with configurable deadlines
- Discount codes (percentage/fixed, max uses, validity dates)
- Per-activity legal consents (mandatory/optional)
- Per-activity required attachments with file upload
- Member portal: activity browsing with thumbnails, registration status badges, "My Activities" grid
- Admin portal: registration management with status changes

**Payments & Invoicing** (available now)
- Receipt management with 7-status lifecycle (new → emitted → paid / returned / cancelled / overdue)
- PDF receipt generation (WeasyPrint) with org header, member details, VAT breakdown — 3 locales (ES/CA/EN)
- Bulk membership fee generation from membership types
- Auto-receipt on activity registration (emitted on confirmation, cancelled on cancellation)
- Manual receipt creation from member detail page
- VAT/IVA calculation with configurable default rate per organization
- Invoice numbering with configurable prefix and optional annual reset (e.g., FAC-2026-0001)
- European currency formatting (1.234,56 €) based on org locale
- Member self-service: "My Receipts" page with PDF download
- Admin dashboard: receipt status chart + pending/paid/overdue amount cards
- Receipt email notification with PDF attachment (via Celery + Resend or SMTP)
- Settings → Payments tab for invoicing and banking configuration

**SEPA Direct Debit** (available — v0.4.0)
- SEPA mandate management (create, PDF, upload signed, cancel)
- Remittance batch processing with SEPA XML (pain.008.001.02)
- Bank return file import and receipt status tracking
- Member self-service payment method page

**Payment Providers** (in progress — v0.4.x)
- Configurable payment gateway management (super admin settings)
- Stripe Checkout — member self-service "Pay Now" for pending receipts
- Redsys SIS (TPV Virtual) — Spanish bank gateway with hosted 3D Secure V2 and Bizum (v0.4.3)
- Webhook infrastructure for real-time payment status updates (POST /webhooks/{provider})
- Extensible adapter pattern for regional providers (GoCardless, MercadoPago, Razorpay, etc.)

**Bookings & Spaces** (available now)
- Bookable spaces with daily opening hours and admin-defined dated slots
- Repeat rules that materialize a dated series (selected weekdays, every N weeks), plus whole-day slots
- Per-slot capacity with a FIFO waitlist and automatic promotion on cancellation
- Member week calendar with live occupancy, self-cancellation up to a configurable deadline
- Confirmation, waitlist, promotion and admin-cancellation emails

**Communications** (planned)
- Email campaigns with templates and audience targeting
- Direct messaging between admins and members
- Multi-language email templates

**Reports & Dashboards** (planned)
- Membership statistics and trends
- Financial summaries
- Data exports (CSV, PDF)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12+ / FastAPI / SQLAlchemy / Alembic |
| Frontend | Next.js / React / Tailwind CSS / Shadcn/ui |
| Database | PostgreSQL 15 |
| Containers | Docker + Docker Compose |
| CI | GitHub Actions |
| Registry | GitHub Container Registry (ghcr.io) |

## Development

Backend in Docker, frontend locally with pnpm hot reload — driven by `scripts/dev.sh`:

```bash
./scripts/dev.sh start all      # backend (Docker) + frontend (local)
./scripts/dev.sh status
./scripts/dev.sh test           # backend suite
```

Full setup, every command, service URLs, seeding and the test suites are in
**[Local development environment](docs/development/local-environment.md)**.

See [CONTRIBUTING](CONTRIBUTING.md) for branching, versioning and how a release is cut.

## Installation (Docker)

Production self-hosting lives in the docs, so there is one copy of it to keep correct:

- **[Installation](docs/getting-started/installation.md)** — `vps-bootstrap.sh` on a bare server,
  then `install.sh`, which generates real secrets, pins a version and puts your data under one
  backed-up directory
- **[First-time setup](docs/getting-started/first-setup.md)** — create the super admin and the
  organization
- **[Configuration reference](docs/self-hosting/configuration.md)** — every environment variable
- **[Backups & restore](docs/self-hosting/backups-and-restore.md)** — set this up before going live
- **[Upgrading](docs/self-hosting/upgrading.md)** — moving to a new release
- **[Troubleshooting](docs/self-hosting/troubleshooting.md)** — when something will not start

The [Quick Start](#quick-start-docker) above is for evaluation only: it ships a signing key that is
published in this repository and keeps data in throwaway volumes.


## Contributing

Memship is in its early stages. Code contributions will be welcome once the project foundation is in place — stay tuned.

In the meantime, feel free to [open an issue](https://github.com/marcandreuf/memship/issues) to share ideas, suggest features, or ask questions. All feedback is welcome.

## License

Memship is licensed under the [Elastic License 2.0 (ELv2)](LICENSE). You are free to use, modify, and self-host Memship. The license restricts offering it as a managed service to third parties.
