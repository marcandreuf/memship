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

- [Configuration reference](self-hosting/configuration.md) — every environment variable _(EN)_
- [Email delivery](self-hosting/email.md) — SMTP or Resend _(EN)_
- [Backups & restore](self-hosting/backups-and-restore.md) _(EN)_
- [Upgrading](self-hosting/upgrading.md) — image tags and migrations _(EN)_
- [Troubleshooting](self-hosting/troubleshooting.md) — when something will not start _(EN)_
- Reverse proxy & TLS — the stack ships a Caddy that obtains and renews certificates on its own.
  Set up in [Installation](getting-started/installation.md), tuned via `SITE_ADDRESS` in the
  [Configuration reference](self-hosting/configuration.md)
- Payment providers (Stripe, Redsys/Bizum) — _planned_

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

---

## Contributing to the docs

- **Docs live with the code.** When a feature PR changes behaviour, update its page in the
  same PR. Each admin/member guide page maps 1:1 to a feature module in the app.
- **Keep heading anchors stable.** In-app help links point at specific headings
  (e.g. `admin-guide/activities#lista-de-espera`). Renaming a heading breaks those links, so
  change anchors deliberately.
- **Plain Markdown, tool-agnostic.** These files render on GitHub today and can be published
  by a docs-site generator later without rework. Avoid tool-specific syntax.
