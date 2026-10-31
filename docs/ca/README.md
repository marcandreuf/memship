# Documentació de Memship (català)

Documentació per a **qui allotja Memship**, **qui administra una entitat** i **les persones
sòcies**. Aquest és l'arbre en català; el castellà és a [`../es/README.md`](../es/README.md) i
l'anglès a [`../en/README.md`](../en/README.md).

> **Aquesta pàgina és, per ara, l'única en català.** La resta encara no està traduïda, així que
> cada enllaç d'aquest índex porta a la pàgina en castellà o en anglès, i al web se serveix en
> aquell idioma amb un avís. La cobertura es segueix a
> [#423](https://github.com/marcandreuf/memship/issues/423).

## Quina versió descriu aquesta documentació

Aquestes pàgines descriuen memship 3.0.1 — la versió publicada actual — més el que s'hagi
fusionat des que es va etiquetar. Es publiquen des de la branca principal, així que un canvi
apareix aquí quan es fusiona i no quan surt la versió següent.

**Per saber quina versió executa la teva instància**, pregunta-l'hi:

```bash
curl -s http://localhost/api/v1/health   # {"status":"healthy","version":"2.19.0",...}
```

`version` és l'etiqueta d'imatge amb què es va desplegar. Si diu `latest`, la instal·lació no està
fixada a cap versió i des d'aquí no es pot saber — mira
[Upgrading](../en/self-hosting/upgrading.md).

**Si la teva instància és més antiga**, llegeix la documentació tal com era per a la teva versió i
no aquesta. Cada etiqueta porta la seva pròpia còpia, així que posa la teva versió a la ruta:

```
https://github.com/marcandreuf/memship/blob/v2.18.0/docs/README.md
```

El que ha canviat entre la teva versió i aquesta és a la
[pàgina de versions](https://github.com/marcandreuf/memship/releases), on les notes de cada una
recullen els canvis de comportament i les migracions que més val no saltar-se.

## Primers passos

- [Què necessites per executar Memship](../es/getting-started/what-you-need.md) — el servidor, el
  domini, el correu i què costen, mesurat i no estimat. Per decidir, abans d'instal·lar _(en
  castellà)_
- [Quick start](../en/getting-started/quickstart.md) — provar Memship amb una sola ordre _(en
  anglès)_
- [Installation](../en/getting-started/installation.md) — instal·lació de producció amb Docker
  _(en anglès)_
- [First-time setup](../en/getting-started/first-setup.md) — crear el super administrador i deixar
  l'entitat a punt _(en anglès)_

## Guia de l'administrador (admin guide)

Per al personal que gestiona l'entitat des del tauler d'administració. Totes aquestes pàgines
són, per ara, en castellà.

- [Introducció](../es/admin-guide/overview.md) — rols, navegació i tauler
- [Socis](../es/admin-guide/members.md) — cicle de vida, tipus de quota, grups
- [Activitats](../es/admin-guide/activities.md) — inscripcions, modalitats, descomptes
- [Pagaments i rebuts](../es/admin-guide/payments.md) — rebuts, quotes, IVA, pagament en línia
- [Domiciliació SEPA](../es/admin-guide/sepa.md) — mandats i remeses
- [Comunicacions](../es/admin-guide/communications.md) — avisos als socis
- [Carnet digital](../es/admin-guide/member-cards.md) — carnet QR i control d'accés
- [Camps de perfil](../es/admin-guide/custom-fields.md) — camps personalitzats
- [Informes i tauler](../es/admin-guide/reports.md) — tauler, resum anual, exportacions
- [Configuració](../es/admin-guide/settings.md) — entitat, facturació, automatitzacions
- [Integrations](../en/admin-guide/integrations.md) — SSO (Google, Apple) i correu, pas a pas _(en
  anglès)_
- [Payment providers](../en/admin-guide/payment-providers.md) — connectar Stripe, Redsys i Bizum
  _(en anglès)_

## Guia del soci (member guide)

Per a les persones sòcies que fan servir el portal. En castellà, per ara.

- [El teu compte i el teu perfil](../es/member-guide/account.md) — accés, perfil, idioma, foto
- [Activitats](../es/member-guide/activities.md) — inscriure's, llista d'espera
- [Pagaments i rebuts](../es/member-guide/payments.md) — els meus rebuts, pagar en línia, forma de
  pagament
- [Carnet digital](../es/member-guide/member-card.md) — carnet QR

## Allotjar Memship (operadors)

Aquestes pàgines són, per ara, només en anglès:

- [Your organisation's domain](../en/self-hosting/domain-and-dns.md) — el nom de màquina i els seus
  registres DNS, quan el domini és de l'entitat i no teu
- [Configuration reference](../en/self-hosting/configuration.md) — totes les variables d'entorn
- [Feature flags](../en/self-hosting/feature-flags.md) — els vint-i-un interruptors de mòdul
- [Email delivery](../en/self-hosting/email.md) — Resend, Gmail o qualsevol servidor SMTP
- [Backups & restore](../en/self-hosting/backups-and-restore.md) — còpies de seguretat i
  restauració
- [Upgrading](../en/self-hosting/upgrading.md) — etiquetes d'imatge i migracions
- [Troubleshooting](../en/self-hosting/troubleshooting.md) — quan alguna cosa no arrenca

## Referència

- [Rols i permisos](../es/reference/roles-and-permissions.md) _(en castellà)_
- Preguntes freqüents — _pendent_
- Glossari — _pendent_

> **Reserva d'espais** (Simple Bookings) va a les imatges publicades — `/api/v1/bookings` és a
> l'API i l'ordre de posada en marxa sembra espais, franges i llista d'espera — però **encara no
> té pàgina ni a la guia de l'administrador ni a la del soci**. És un buit de documentació, no una
> funció que falti.
