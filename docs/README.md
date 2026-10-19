# Memship Documentation

Documentation for **self-hosting operators**, **organization admins**, and **members**.

> **Languages.** Operator/self-hosting docs are written in **English** (the audience is
> developers and system administrators, often international). The admin and member guides
> are **Spanish-first** (`.es.md`), since the people running a club and its members are
> primarily Spanish-speaking; Catalan (`.ca.md`) and English (`.md`) translations are added
> on demand.

## Getting started

New to Memship? Start here.

- [Quick start](getting-started/quickstart.md) — try Memship with a single command _(EN)_
- [Installation](getting-started/installation.md) — production Docker install _(EN)_
- [First-time setup](getting-started/first-setup.md) — create your admin and organization _(EN)_

## Self-hosting (operators)

Running Memship on your own server.

- [Your organisation's domain](self-hosting/domain-and-dns.md) — choosing a hostname and the DNS
  records behind it, when the domain belongs to a club rather than to you _(EN)_
- [Configuration reference](self-hosting/configuration.md) — every environment variable _(EN)_
- [Feature flags](self-hosting/feature-flags.md) — the twenty-one module switches, what a fresh install starts with _(EN)_
- [Email delivery](self-hosting/email.md) — SMTP or Resend _(EN)_
- [Backups & restore](self-hosting/backups-and-restore.md) _(EN)_
- [Upgrading](self-hosting/upgrading.md) — image tags and migrations _(EN)_
- [Troubleshooting](self-hosting/troubleshooting.md) — when something will not start _(EN)_
- Reverse proxy & TLS — the stack ships a Caddy that obtains and renews certificates on its own.
  Set up in [Installation](getting-started/installation.md), tuned via `SITE_ADDRESS` in the
  [Configuration reference](self-hosting/configuration.md); the DNS side is
  [Your organisation's domain](self-hosting/domain-and-dns.md)
- [Payment providers](admin-guide/payment-providers.md) — connecting Stripe, Redsys and Bizum:
  which credential to get from where, the Stripe webhook, and why Redsys needs none _(EN)_

## Development (contributors)

Working on Memship itself.

- [Local development environment](development/local-environment.md) — the dev stack, commands,
  seeding and the test suites _(EN)_
- [Contributing](../CONTRIBUTING.md) — branching, versioning and how a release is cut _(EN)_

## Guía del administrador (admin guide)

Para el personal que gestiona la organización desde el panel de administración.

- [Introducción](admin-guide/overview.es.md) — roles, navegación y panel _(ES)_
- [Socios](admin-guide/members.es.md) — ciclo de vida, tipos de membresía, grupos _(ES)_
- [Actividades](admin-guide/activities.es.md) — inscripciones, modalidades, descuentos _(ES)_
- [Pagos y recibos](admin-guide/payments.es.md) — recibos, cuotas, IVA, pago en línea _(ES)_
- [Domiciliación SEPA](admin-guide/sepa.es.md) — mandatos y remesas _(ES)_
- [Comunicaciones](admin-guide/communications.es.md) — anuncios a los socios _(ES)_
- [Carné digital](admin-guide/member-cards.es.md) — carné QR y control de acceso _(ES)_
- [Campos de perfil](admin-guide/custom-fields.es.md) — campos personalizados _(ES)_
- [Informes y panel](admin-guide/reports.es.md) — panel, resumen anual, exportaciones _(ES)_
- [Configuración](admin-guide/settings.es.md) — organización, facturación, automatizaciones _(ES)_
- [Integrations](admin-guide/integrations.md) — SSO (Google, Apple) and email, step by step _(EN)_
- [Payment providers](admin-guide/payment-providers.md) — connecting Stripe, Redsys and Bizum _(EN)_

## Guía del socio (member guide)

Para las personas socias que usan el portal.

- [Tu cuenta y tu perfil](member-guide/account.es.md) — acceso, perfil, idioma, foto _(ES)_
- [Actividades](member-guide/activities.es.md) — inscribirse, lista de espera _(ES)_
- [Pagos y recibos](member-guide/payments.es.md) — mis recibos, pagar online, forma de pago _(ES)_
- [Carné digital](member-guide/member-card.es.md) — carné QR _(ES)_

## Reference

- [Roles y permisos](reference/roles-and-permissions.es.md) _(ES)_
- FAQ — _planned_
- Glossary — _planned_

> **Simple Bookings** (reserva de espacios) ships in the released images — `/api/v1/bookings` is
> in the API and the setup command seeds spaces, slots and a waitlist — but it has **no admin or
> member guide page yet**. That is a documentation gap, not a missing feature.

## Project policies

These live at the repository root rather than here, because `docs/` is product
documentation — how memship works and how to run it — and these are the project's own
rules. GitHub also surfaces them from the root on its own.

- [Contributing](../CONTRIBUTING.md) — branching, versioning and how a release is cut _(EN)_
- [Code of conduct](../CODE_OF_CONDUCT.md) — what is expected of everyone taking part _(EN)_
- [Security policy](../SECURITY.md) — reporting a vulnerability privately, and what counts as
  one rather than an ordinary bug _(EN)_
- [Accessibility](../ACCESSIBILITY.md) — what the project aims for, what has and has not been
  tested, and how to report a barrier _(EN)_

---

## Contributing to the docs

- **Docs live with the code.** When a feature PR changes behaviour, update its page in the
  same PR. Each admin/member guide page maps 1:1 to a feature module in the app.
- **Keep heading anchors stable.** Pages link into each other's headings (e.g.
  `settings.es.md#banca-y-facturación`), the READMEs and the issue templates link in from
  outside the folder, and GitHub does not redirect a renamed anchor. So rename headings
  deliberately and fix what pointed at them — nothing warns you. The app itself does not yet
  link to these pages; when it does, its links will be the ones hardest to find and fix.
- **Plain Markdown, tool-agnostic.** These files render on GitHub today and can be published
  by a docs-site generator later without rework. Avoid tool-specific syntax.
