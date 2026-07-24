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
- Reverse proxy & TLS — _planned_
- Payment providers (Stripe, Redsys/Bizum) — _planned_
- Troubleshooting — _planned_

## Guía del administrador (admin guide)

Para el personal que gestiona la organización desde el panel de administración.

- [Introducción](admin-guide/overview.es.md) — roles, navegación y panel _(ES)_
- Socios · Actividades · Pagos · SEPA · Comunicaciones · Carné digital ·
  Campos personalizados · Reservas · Informes · Configuración — _planificado_

## Guía del socio (member guide)

Para las personas socias que usan el portal.

- Cuenta y perfil · Actividades · Pagos · Carné digital · Reservas — _planificado_

## Reference

- Roles & permissions — _planned_
- FAQ — _planned_
- Glossary — _planned_

---

## Contributing to the docs

- **Docs live with the code.** When a feature PR changes behaviour, update its page in the
  same PR. Each admin/member guide page maps 1:1 to a feature module in the app.
- **Keep heading anchors stable.** In-app help links point at specific headings
  (e.g. `admin-guide/activities#lista-de-espera`). Renaming a heading breaks those links, so
  change anchors deliberately.
- **Plain Markdown, tool-agnostic.** These files render on GitHub today and can be published
  by a docs-site generator later without rework. Avoid tool-specific syntax.
