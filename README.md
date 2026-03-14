# Memship

> **This project is under active development, not yet ready for production, and open to [feature requests](https://github.com/marcandreuf/memship/issues).**

**Membership management for everyone.**

Memship is a self-hosted, open-source membership management system designed for professional associations, sports clubs, cultural organizations, and any member-based entity. Deploy it on your own infrastructure, own your data, and manage your community with modern tooling.

---

## What we're building

Most membership tools are either expensive SaaS platforms or outdated legacy software. Memship aims to change that — a modern, full-featured solution that you control. No vendor lock-in, no per-member pricing, no data leaving your servers.

- **Self-hosted** — runs on any server with Docker
- **Single-tenant** — one database per organization, complete data isolation
- **Multi-language** — Spanish, Catalan, and English from day one
- **GDPR-ready** — built-in legal terms templates and consent management

## Planned Features

**Member Management**
- Full member lifecycle: registration, onboarding, status changes, cancellation
- Membership types, groups, and custom fields
- Guardian/minor support
- Member cards with QR codes

**Activities & Events**
- Activity creation with modalities, pricing, and capacity control
- Online registration with eligibility filters and waitlists
- Attendance tracking with QR check-in

**Payments & Invoicing**
- Membership fee generation and invoicing
- SEPA direct debit batch processing
- Stripe online payments
- Payment tracking and reminders

**Communications**
- Email campaigns with templates and audience targeting
- Direct messaging between admins and members
- Multi-language email templates

**Bookings & Spaces**
- Space and resource reservation system
- Calendar views with availability
- Booking rules and conflict prevention

**Reports & Dashboards**
- Membership statistics and trends
- Financial summaries
- Data exports (CSV, PDF)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12+ / FastAPI / SQLAlchemy / Celery |
| Frontend | Next.js / React / Tailwind CSS / Shadcn/ui |
| Database | PostgreSQL 15 |
| Cache | Redis 7 |
| Proxy | Caddy 2 (auto-SSL) |
| Containers | Docker + Docker Compose |

## Roadmap

| Phase | Milestone | Version | Status |
|-------|-----------|---------|--------|
| Phase 0 | Infrastructure setup | v0.0.x | Not started |
| Phase 1 | Member Management MVP | v0.1.0 | Not started |
| Phase 2 | Activity Management | v0.2.0 | — |
| Phase 3 | Basic Payments | v0.3.0 | — |
| Phase 4 | Payment Processing (SEPA + Stripe) | v0.4.0 | — |
| Phase 5 | Communication System | v0.5.0 | — |
| Phase 6 | Bookings & Documents | v0.6.0 | — |
| Phase 7 | Reports & Analytics | v0.7.0 | — |
| Phase 8 | Stabilization & Release | v1.0.0 | — |

## Contributing

Memship is in its early stages. Code contributions will be welcome once the project foundation is in place — stay tuned.

In the meantime, feel free to [open an issue](https://github.com/marcandreuf/memship/issues) to share ideas, suggest features, or ask questions. All feedback is welcome.

## License

Memship is licensed under the [Elastic License 2.0 (ELv2)](LICENSE). You are free to use, modify, and self-host Memship. The license restricts offering it as a managed service to third parties.
