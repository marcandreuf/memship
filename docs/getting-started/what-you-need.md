# What you need to run Memship

This page is for deciding **whether** to run Memship. It states what the stack needs, what that
costs, and what it does not need. Whoever goes ahead afterwards reads
[Installation](installation.md), which is written for the person at the terminal.

> **En español:** [Qué necesitas para ejecutar Memship](es/what-you-need.md).

Everything below was measured on release 2.19.0 rather than estimated. Where a number is a
judgement rather than a measurement, it says so.

## The short answer

| | |
|---|---|
| **A server** | 2 vCPU, 4 GB RAM, 40 GB SSD. Linux with Docker. One Memship per host |
| **A domain name** | With an A record pointing at the server. HTTPS is then automatic |
| **A way to send email** | Resend, Gmail, or any SMTP server. This cannot be skipped |
| **What it costs** | **8–12 € a month**, VAT included, for everything above |
| **Who installs it** | You, any sysadmin you already use, or the maintainer as a paid engagement |

No Kubernetes, no managed database, no object storage, no per-member licence.

## The server

Memship runs seven containers: a Caddy reverse proxy, the API, a Celery worker, a Celery beat
scheduler, the Next.js frontend, Redis and PostgreSQL.

**Measured memory.** Release 2.19.0, after seeding a club of 60 members, 28 activities, 190
registrations, 80 receipts and 25 SEPA mandates, then browsing the member, activity, receipt,
remittance and mandate screens and the annual summary:

| Container | Resident memory |
|---|---|
| Frontend (Next.js) | 236 MiB |
| Celery worker | 149 MiB |
| API (FastAPI) | 131 MiB |
| Celery beat | 107 MiB |
| PostgreSQL | 42 MiB |
| Caddy | 12 MiB |
| Redis | 5 MiB |
| **Total** | **682 MiB** |

So the whole stack works in about **0.7 GB**. The worker figure is the one a 2 vCPU host produces:
Celery sizes its process pool to the number of CPUs, so it starts two worker processes there. On
a larger machine it starts more and uses roughly 50 MiB per additional CPU — worth knowing if you
put Memship on a box you already own.

**2 GB of RAM is enough to run it; 4 GB is the recommendation.** The gap is not the application. It
is PostgreSQL having spare memory to cache with, and an upgrade briefly holding the new images
alongside the running ones. 4 GB is also what the entry plan at every provider below includes, so
asking for less saves nothing.

**Measured disk.** The five images occupy **1.06 GB** on disk and are a **358 MB** download — five
rather than seven, because the API, the worker and the beat scheduler all run the same image. A
database holding the club described above was 12 MB, inside a 50 MB PostgreSQL data directory.

Call the baseline **1.5 GB**, plus the operating system. Growth comes only from files people
upload:

- One photo per member and one cover image per activity, each replaced rather than accumulated
- Attachments on activity registrations, which do accumulate
- Generated SEPA remittance files

Each upload is capped at 10 MB (`MAX_UPLOAD_SIZE_MB`). **Receipt and mandate PDFs are generated on
demand and never written to disk**, so they are not a growth factor. A club of 500 members with a
photo each is under a gigabyte. The 40 GB that comes with the entry plans is not a constraint you
need to shop around for; leave room on top if you keep database backups on the same machine.

**Operating system:** any Linux with Docker Engine and the Compose plugin.
`scripts/vps-bootstrap.sh` prepares a bare **Debian 12** or **Ubuntu 24.04** server, which is what
that script expects.

**One Memship per host.** The containers are named explicitly (`memship-db`, `memship-api`, …), and
Docker names are global to the daemon, so a second instance on the same host fails part-way. Use a
second server, or a VM.

## What it costs

Entry plans at two European providers, both 2 vCPU / 4 GB / 40 GB NVMe, checked on 2026-10-20:

| Provider | Plan | Without VAT | With 21 % IVA |
|---|---|---|---|
| [Hetzner](https://www.hetzner.com/cloud/) | CX23 | 5.49 €/month | ≈ 6.64 €/month |
| [OVHcloud](https://www.ovhcloud.com/es-es/vps/) | VPS-1 | 3.81 €/month | 4.61 €/month |

The OVHcloud figure is its twelve-month-upfront rate; paying monthly costs more. Hetzner raised its
cloud prices on 15 June 2026, so the figure above is the current one and older comparisons
understate it.

On top of the server:

- **A domain**, usually 10–15 € a year, so about 1 € a month.
- **Email**, free for a small association. Resend's free tier covers 3,000 messages a month, and
  Gmail works with an ordinary account. See the limits below before assuming free is enough.

Adding up: the Hetzner plan at 6.64 € including IVA, plus about 1 € a month for the domain, plus
nothing for email on a free tier, is **under 8 € a month**. Budget **8–12 € a month including VAT**
and that covers a larger server or a paid email tier as the association grows. There is no charge
per member, per admin or per receipt.

## A domain name

One hostname, with a DNS **A record** pointing at the server's IP address. Once that resolves,
the bundled Caddy obtains and renews a Let's Encrypt certificate on its own — there is no
certificate to buy, install or remember to renew.

If the domain belongs to an association rather than to the person installing — so the hostname, the
DNS zone and the mail domain are three different people's business — read
[Your organisation's domain](../self-hosting/domain-and-dns.md) before starting.

## A way to send email

Memship needs to send transactional email, and this is **not optional**: password resets, email
verification and payment reminders all go through it, and a member cannot sign in for the first
time until it works.

Three options. Resend and Gmail can be configured from the Settings screen or from `.env`; any
other SMTP server is set in `.env` only, as the Settings screen has no field for a server address:

- **Resend** — an email API. Free tier: 3,000 messages a month, 3 domains, but **100 a day**. That
  daily cap is the one that bites: sending reminders to more than 100 members in a single run
  exceeds it. The paid tier is 20 USD a month.
- **Gmail** — an ordinary Google account with an app password. Google applies its own daily sending
  limits.
- **Any SMTP server** — including the one that comes with the association's existing mail hosting.

[Email delivery](../self-hosting/email.md) covers all three, including the DNS records Resend needs.

## How long it takes

Once the images are on the server, the stack starts and answers as healthy in **16 seconds**.

The end-to-end time for a first install on a bare server — `scripts/vps-bootstrap.sh`, then
`scripts/install.sh`, then creating the first admin — has not been measured, and this page will not
guess at it. The parts that dominate it are the image download (358 MB) and the DNS record you
create for the domain propagating.

## What it does not need

- **No Kubernetes**, and no orchestration beyond Docker Compose.
- **No managed database.** PostgreSQL runs as one of the seven containers.
- **No object storage.** Uploads go to a directory on the server's disk.
- **No separate job queue service.** Redis and Celery are in the stack.
- **No licence fee, and no per-member cost.** Memship is source-available under the
  [Elastic License 2.0](https://github.com/marcandreuf/memship/blob/main/LICENSE). You are free to use, modify and self-host it; the licence
  restricts offering it as a managed service to third parties, which is not what an association
  running it for its own members is doing.

## Who installs it

- **Yourself**, or anyone comfortable with a Linux server and a DNS panel.
- **A sysadmin the association already uses**, who needs nothing from this project beyond
  [Installation](installation.md).
- **The maintainer, as a paid engagement**, if nobody in the association wants to own a server.

## Next

- Deciding is done, installing is next: [Installation](installation.md).
- Want to click around first, with no server at all: [Quick start](quickstart.md) runs the whole
  stack on your own machine with one command. It is for evaluation only.
