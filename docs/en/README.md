# Memship Documentation (English)

Documentation for **self-hosting operators**, **organization admins** and **members**.
This is the English tree; the Spanish one is at [`../es/README.md`](../es/README.md).

## Which version these docs describe

These pages describe the current release, plus anything merged since it was tagged. They are
published from the main branch, so a change lands here when it is merged rather than when the
next version ships. The exact version is stated in
[the documentation index](../README.md#which-version-these-docs-describe).

**To check what your own instance runs**, ask it:

```bash
curl -s http://localhost/api/v1/health   # {"status":"healthy","version":"2.19.0",...}
```

`version` is the image tag the instance was deployed with. If it reads `latest` you are on an
unpinned install and cannot tell from here — see [Upgrading](self-hosting/upgrading.md).

**If your instance is older**, read the docs as they stood for your release rather than these.
Every tag carries its own copy, so swap the version into the path:

```
https://github.com/marcandreuf/memship/blob/v2.18.0/docs/README.md
```

What changed between your version and this one is on the
[releases page](https://github.com/marcandreuf/memship/releases), where each release's notes carry
the behaviour changes and migrations an upgrader must not miss.

## Getting started

New to Memship? Start here.

- [What you need to run Memship](getting-started/what-you-need.md) — the server, the domain,
  the email and what they cost, measured rather than estimated. For deciding, before installing
- [Quick start](getting-started/quickstart.md) — try Memship with a single command
- [Installation](getting-started/installation.md) — production Docker install
- [First-time setup](getting-started/first-setup.md) — create your admin and organization

## Self-hosting (operators)

Running Memship on your own server.

- [Your organisation's domain](self-hosting/domain-and-dns.md) — choosing a hostname and the DNS
  records behind it, when the domain belongs to a club rather than to you
- [Configuration reference](self-hosting/configuration.md) — every environment variable
- [Feature flags](self-hosting/feature-flags.md) — the twenty-one module switches, what a fresh install starts with
- [Email delivery](self-hosting/email.md) — Resend, Gmail or any SMTP server
- [Backups & restore](self-hosting/backups-and-restore.md)
- [Upgrading](self-hosting/upgrading.md) — image tags and migrations
- [Troubleshooting](self-hosting/troubleshooting.md) — when something will not start
- Reverse proxy & TLS — the stack ships a Caddy that obtains and renews certificates on its own.
  Set up in [Installation](getting-started/installation.md), tuned via `SITE_ADDRESS` in the
  [Configuration reference](self-hosting/configuration.md); the DNS side is
  [Your organisation's domain](self-hosting/domain-and-dns.md)
- [Payment providers](admin-guide/payment-providers.md) — connecting Stripe, Redsys and Bizum:
  which credential to get from where, the Stripe webhook, and why Redsys needs none

## Administration

- [Integrations](admin-guide/integrations.md) — SSO (Google, Apple) and email, step by step
- [Payment providers](admin-guide/payment-providers.md) — connecting Stripe, Redsys and Bizum

The rest of the administrator guide exists in Spanish only for now, and is listed in
[the Spanish index](../es/README.md#guía-del-administrador-admin-guide). Coverage is tracked in
[#423](https://github.com/marcandreuf/memship/issues/423).

## Development (contributors)

Working on Memship itself.

- [Local development environment](development/local-environment.md) — the dev stack, commands,
  seeding and the test suites
- [Contributing](https://github.com/marcandreuf/memship/blob/main/CONTRIBUTING.md) — branching, versioning and how a release is cut

## Member guide

The member-facing guide exists in Spanish only for now:
[Guía del socio](../es/README.md#guía-del-socio-member-guide).

## Reference

- [Roles y permisos](../es/reference/roles-and-permissions.md) — Spanish only for now
- FAQ — _planned_
- Glossary — _planned_

> **Simple Bookings** (space reservations) ships in the released images — `/api/v1/bookings` is
> in the API and the setup command seeds spaces, slots and a waitlist — but it has **no admin or
> member guide page yet**. That is a documentation gap, not a missing feature.
