<!-- source: es/admin-guide/overview.md -->
<!-- source-hash: 5086916e23fd -->

# Introducció a la guia de l'administrador

Aquesta guia s'adreça al **personal que gestiona l'organització** des del tauler
d'administració de Memship: altes de socis, activitats, cobraments, comunicacions i
configuració.

> **En castellà:** [Introducción a la guía del administrador](../../es/admin-guide/overview.md).

> **Idioma.** Les guies de l'administrador i del soci s'escriuen primer en castellà
> (`docs/es/`), perquè qui gestiona un club i els seus socis és majoritàriament
> castellanoparlant. Totes tenen versió en anglès (`docs/en/`); la traducció al català
> (`docs/ca/`) està en curs, i fins que existeixi se serveix la pàgina en castellà.

## Rols

Memship porta tres rols del sistema:

| Rol                    | Què pot fer                                                                  |
|------------------------|------------------------------------------------------------------------------|
| **Superadministrador** | Administració a nivell de plataforma, inclosa la configuració de les passarel·les de pagament. |
| **Administrador de l'organització** | Gestió diària: socis, activitats, facturació i comunicacions. |
| **Soci**               | Ús del portal del soci: perfil, activitats, pagaments, carnet i reserves.    |

La major part d'aquesta guia es refereix a l'**administrador de l'organització**. El
superadministrador també pot crear **rols personalitzats** amb els permisos que triï; vegeu
[Rols i permisos](../reference/roles-and-permissions.md).

## Iniciar sessió

L'accés es fa amb **correu electrònic i contrasenya**. Si has oblidat la contrasenya, fes servir
l'enllaç de recuperació de la pantalla d'inici de sessió (requereix que
l'[enviament de correu](../self-hosting/email.md) estigui configurat).

## Àrees del tauler

El tauler d'administració s'organitza al voltant d'aquestes àrees:

- **Tauler (Dashboard)**, resum amb gràfics d'estat de socis i de rebuts, i imports pendents,
  pagats i vençuts.
- **[Socis](members.md)**, cicle de vida complet (alta, canvis d'estat, baixa), tipus de quota,
  grups i suport per a menors amb tutor.
- **[Entitats](entities.md)**, empreses, fundacions i organismes amb què tracta el club, amb
  rebuts al seu nom (donacions) sense necessitat de fer-los socis.
- **[Activitats](activities.md)**, creació i publicació, inscripcions amb control
  d'elegibilitat, llista d'espera, codis de descompte, consentiments i adjunts.
- **[Pagaments](payments.md)**, rebuts, generació de quotes, IVA, facturació, generació de PDF i
  cobrament en línia (Stripe, Redsys/Bizum).
- **[Donacions](donations.md)**: els tres camins per rebre una donació, i quin registre deixa
  cadascun.
- **[SEPA](sepa.md)**, mandats de domiciliació, remeses (XML pain.008) i importació de
  devolucions.
- **[Comunicacions](communications.md)**, anuncis a tots els socis, a un grup o a un tipus de
  quota.
- **[Carnet digital](member-cards.md)**, carnet en PDF amb número de soci i check-in per QR.
- **[Camps personalitzats](custom-fields.md)**, camps de perfil configurables per
  l'organització.
- **[Informes](reports.md)**, exportacions CSV, tauler financer i resum anual.
- **[Configuració](settings.md)**, marca (nom, color, logotip), adreça, dades bancàries,
  facturació i automatitzacions.

> La reserva d'espais (**Simple Bookings**) encara no forma part d'una versió publicada i es
> documentarà quan s'alliberi.

## Configuració inicial

Abans de donar d'alta socis reals, completa la
[configuració inicial](../getting-started/first-setup.md): dades de l'organització, marca, dades
bancàries i facturació, i verifica l'enviament de correu.

## Pàgines de la guia

Cada àrea (Socis, Activitats, Pagaments, etc.) té la seva pròpia pàgina.
L'[índex de la documentació](../README.md) les enumera totes.
