# Feature flags

Memship ships every module in one image. Which of them an organization actually
uses is decided by **twenty-one keys** in a single JSONB column,
`organization_settings.features`, on the one row the database allows
(`CHECK (id = 1)`). They are edited from **Settings** in the admin portal — not
from `.env`, and not from a file on the server. Nothing here needs a restart.

This page exists because "the flag is absent" and "the flag is off" are the same
thing to the application but not to a person reading a screen, and until it was
written down there was no way to tell a module nobody had switched on from a
module that was broken.

## What a fresh install starts with

**Two of the twenty-one.** Everything else is absent.

| Set | Why |
|---|---|
| `custom_roles` | The permission layer is always active; hiding the only screen that can retune it helps nobody. |
| `gender_options` | Five seeded options, so the member form has something to offer on day one. |

That is deliberate, not an oversight. A club opts into each module when it is
ready for it, and `install.sh` produces exactly this state. It does mean a first
boot looks sparse: **seven routes redirect to the dashboard** until their module
is switched on.

| Route | Needs |
|---|---|
| `/communications`, `/announcements` | `communications` |
| `/spaces`, `/book`, `/my-bookings` | `bookings` |
| `/scan`, `/my-card` | `member_card` |

A module that is off also **404s its own endpoints**, which is why the frontend
redirects rather than rendering a shell over a dead API.

**Absent does not always mean off.** Two keys default to *enabled* when missing —
`public_registration` and `registration_requires_approval`, both read as
`features.get(key, True)` in `domains/auth/service.py`. So sign-up is open *by
policy* on a fresh install, and each sign-up lands in the pending-approval queue
rather than becoming an active member. If you do not want an open sign-up form,
set `public_registration` to `false` explicitly — removing the key does the
opposite of what it looks like.

Open by policy is not the same as working. `POST /auth/register` refuses with
**503 — "the club has not finished setting up email"** until a mail transport is
configured, because confirming an address needs a link and the link needs a
transport. That is deliberate: it is better than minting an account nobody can
ever sign in to. On a fresh self-hosted install it is the answer every visitor
gets, so the sign-up form is open in Settings and closed in practice until you
configure Resend or SMTP. Verified on a clean install, not inferred.

## Want a configured instance instead?

```bash
python -m app.cli.seed --demo     # or: ./scripts/dev.sh seed demo
```

The demo path switches on **all twenty-one** and fills a club's worth of data
behind them. It is for evaluation and review — never for a real organization,
because it also creates demo members and receipts.

> **It arms the scheduled jobs too.** `recurring_billing_enabled`,
> `payment_reminders_enabled` and `membership_lapse_enabled` are switches that a
> Celery beat task reads at 02:00, 03:00 and 04:00 UTC. While they are on, a
> running instance generates receipts, marks unpaid ones overdue, and moves
> members whose fees lapsed onto the free tier. It is behaving correctly, but
> its data will not be exactly as you left it.
>
> **Lapsing does not suspend anyone.** A lapsed member is a full member on the
> free tier — `Member.status` is deliberately untouched, and the previous tier
> is parked on `Member.membership_reverted_from_id` so that paying the fee
> restores it (see `lapse_service.py` and memship#145). Member status counts on
> the dashboard therefore do not move when a lapse run does.
>
> **Those are UTC hours, and UTC is not your working day.** At UTC+9 they fire
> at 11:00, 12:00 and 13:00 — the middle of a working morning, not overnight. If
> you are reviewing or demoing an instance and want its data to hold still,
> switch these three off for the duration. They gate scheduled work and have no
> screen of their own, so nothing you can look at is lost by doing so.

## The twenty-one

Three different kinds of thing live in this column, and they do not behave alike.

- **Gates** — off means a request is refused. These are the ones that redirect.
- **Values** — they parameterise behaviour rather than gate it. An absent one
  falls back to a default written in code, so the instance is *already running
  on that number* whether or not the key exists.
- **Data** — a list, validated per entry on the way in.

| Key | Kind | Absent means | Gates |
|---|---|---|---|
| `custom_roles` | gate | off | the Accounts/Roles settings tab |
| `communications` | gate | off | `/communications`, `/announcements` |
| `member_card` | gate | off | `/scan`, `/my-card` |
| `bookings` | gate | off | `/spaces`, `/book`, `/my-bookings` |
| `custom_profile_fields` | gate | off | custom member fields |
| `public_registration` | gate | **on** | self sign-up — but 503s until email is configured |
| `registration_requires_approval` | gate | **on** | the pending-approval queue |
| `payment_reminders_enabled` | gate | off | the dunning run and manual reminders |
| `recurring_billing_enabled` | gate | off | the scheduled membership-fee run |
| `membership_lapse_enabled` | gate | off | the scheduled run that reverts lapsed members to the free tier |
| `reminder_days_after_due` | value | **3** | days after due before the first reminder |
| `reminder_repeat_days` | value | **7** | days between repeats |
| `reminder_max_count` | value | **3** | reminders per receipt |
| `recurring_billing_day` | value | **1** | day of month the billing run emits on |
| `membership_fee_due_days` | value | **7** | days from emission to due date |
| `membership_lapse_grace_days` | value | **21** | days past due before a member lapses |
| `booking_window_days` | value | **14** | how far ahead a member may book (1–365) |
| `booking_cancellation_deadline_hours` | value | **24** | cancellation cut-off (0–8760) |
| `booking_waitlist_enabled` | value | off | whether a full slot offers a waitlist |
| `billing_notification_email` | value | *unset* | where billing-run summaries go; no-op when unset |
| `gender_options` | data | no options offered | the member form's gender field |

The defaults above are not documentation-only — they are the literal fallbacks in
`reminder_service.py`, `recurring_billing_service.py`, `lapse_service.py` and
`bookings/rules.py`, and `backend/tests/integration/test_demo_data.py` fails if
the seeded values and the code defaults ever drift apart.

## Switching one off is not the same as never switching it on

A **value** has no off state and no redirect. Setting `reminder_max_count` to
something out of range is a different situation from leaving it absent: the
booking rules range-check on save and fall back to the default rather than
raising, but not every value does. If you are reviewing this area, a value needs
to be looked at for *what the screen does with a nonsensical number*, which is
not a gesture the gates need at all.

## One name collision worth knowing

`activities.features` is a **different column** on a different table, and it
holds a `waiting_list` key. A grep for `features` finds both. Nothing in
`organization_settings.features` is named `waiting_list`, and the activity-level
key has nothing to do with `booking_waitlist_enabled`.

## Related

- [Configuration reference](configuration.md) — environment variables, which are
  a separate mechanism entirely
- [First-time setup](../getting-started/first-setup.md)
