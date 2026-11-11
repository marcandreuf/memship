# Documentació de Memship (català)

Documentació per a **qui allotja Memship**, **qui administra una entitat** i **les persones
sòcies**. Aquest és l'arbre en català; el castellà és a [`../es/README.md`](../es/README.md) i
l'anglès a [`../en/README.md`](../en/README.md).

> **Tota la documentació és en català**, igual que en castellà i en anglès. Cada pàgina enllaça
> les seves versions en els altres dos idiomes.

## Quina versió descriu aquesta documentació

Aquestes pàgines descriuen memship 3.3.0, la versió publicada actual, més el que s'hagi
fusionat des que es va etiquetar. Es publiquen des de la branca principal, així que un canvi
apareix aquí quan es fusiona i no quan surt la versió següent.

**Per saber quina versió executa la teva instància**, pregunta-l'hi:

```bash
curl -s http://localhost/api/v1/health   # {"status":"healthy","version":"2.19.0",...}
```

`version` és l'etiqueta d'imatge amb què es va desplegar. Si diu `latest`, la instal·lació no està
fixada a cap versió i des d'aquí no es pot saber, mira
[Actualitzar](self-hosting/upgrading.md).

**Si la teva instància és més antiga**, llegeix la documentació tal com era per a la teva versió i
no aquesta. Cada etiqueta porta la seva pròpia còpia, així que posa la teva versió a la ruta:

```
https://github.com/marcandreuf/memship/blob/v2.18.0/docs/README.md
```

El que ha canviat entre la teva versió i aquesta és a la
[pàgina de versions](https://github.com/marcandreuf/memship/releases), on les notes de cada una
recullen els canvis de comportament i les migracions que més val no saltar-se.

## Primers passos

- [Què necessites per executar Memship](getting-started/what-you-need.md), el servidor, el
  domini, el correu i què costen, mesurat i no estimat. Per decidir, abans d'instal·lar
- [Inici ràpid](getting-started/quickstart.md), provar Memship amb una sola ordre
- [Instal·lació (Docker)](getting-started/installation.md), instal·lació de producció amb Docker
- [Configuració inicial](getting-started/first-setup.md), crear el super administrador i deixar
  l'entitat a punt

## Guia de l'administrador (admin guide)

Per al personal que gestiona l'entitat des del tauler d'administració.

- [Introducció a la guia de l'administrador](admin-guide/overview.md), rols, navegació i tauler
- [Socis](admin-guide/members.md), cicle de vida, tipus de quota, grups
- [Entitats](admin-guide/entities.md), donants, patrocinadors i col·laboradors que no són socis
- [Activitats](admin-guide/activities.md), inscripcions, modalitats, descomptes
- [Pagaments i rebuts](admin-guide/payments.md), rebuts, quotes, IVA, pagament en línia
- [Domiciliació SEPA](admin-guide/sepa.md), mandats i remeses
- [Donacions](admin-guide/donations.md), un enllaç de donació al web de l'entitat
- [Comunicacions](admin-guide/communications.md), avisos als socis
- [Carnet digital i control d'accés](admin-guide/member-cards.md), carnet QR i control d'accés
- [Camps de perfil personalitzats](admin-guide/custom-fields.md), camps personalitzats
- [Informes i tauler](admin-guide/reports.md), tauler, resum anual, exportacions
- [Configuració de l'organització](admin-guide/settings.md), entitat, facturació, automatitzacions
- [Integracions: guia de configuració](admin-guide/integrations.md), SSO (Google, Apple) i correu, pas a pas
- [Proveïdors de pagament: guia de configuració](admin-guide/payment-providers.md), connectar Stripe, Redsys i Bizum

## Guia del soci (member guide)

Per a les persones sòcies que fan servir el portal.

- [El teu compte i el teu perfil](member-guide/account.md), accés, perfil, idioma, foto
- [Activitats](member-guide/activities.md), inscriure's, llista d'espera
- [Pagaments i rebuts](member-guide/payments.md), els meus rebuts, pagar en línia, forma de
  pagament
- [Carnet digital](member-guide/member-card.md), carnet QR

## Allotjar Memship (operadors)

- [El domini de la teva entitat](self-hosting/domain-and-dns.md), el nom de màquina i els seus
  registres DNS, quan el domini és de l'entitat i no teu
- [Referència de configuració](self-hosting/configuration.md), totes les variables d'entorn
- [Feature flags](self-hosting/feature-flags.md), els vint-i-un interruptors de mòdul
- [Enviament de correu](self-hosting/email.md), Resend, Gmail o qualsevol servidor SMTP
- [Còpies de seguretat i restauració](self-hosting/backups-and-restore.md), còpies de seguretat i
  restauració
- [Actualitzar](self-hosting/upgrading.md), etiquetes d'imatge i migracions
- [Resolució de problemes](self-hosting/troubleshooting.md), quan alguna cosa no arrenca
- [Darrere del teu propi proxy invers](self-hosting/reverse-proxy.md), Traefik en lloc del Caddy inclòs, per a un
  servidor que ja té un proxy

## Desenvolupament (contribuir)

Per treballar en Memship.

- [Entorn de desenvolupament local](development/local-environment.md), l'entorn de desenvolupament, les
  ordres, les dades de prova i les suites de tests
- [Contributing](https://github.com/marcandreuf/memship/blob/main/CONTRIBUTING.md), branques,
  versions i com es publica una versió _(en anglès)_

## Referència

- [Rols i permisos](reference/roles-and-permissions.md)
- Preguntes freqüents, _pendent_
- Glossari, _pendent_

> **Reserva d'espais** (Simple Bookings) va a les imatges publicades, `/api/v1/bookings` és a
> l'API i l'ordre de posada en marxa sembra espais, franges i llista d'espera, però **encara no
> té pàgina ni a la guia de l'administrador ni a la del soci**. És un buit de documentació, no una
> funció que falti.
