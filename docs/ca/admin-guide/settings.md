<!-- source: es/admin-guide/settings.md -->
<!-- source-hash: d581d4591573 -->

# Configuració de l'organització

Ajustos generals, facturació, SEPA, proveïdors de pagament i automatitzacions. Requereix permisos
d'administració.

> **En castellà:** [Configuración de la organización](../../es/admin-guide/settings.md).

## Dades de l'organització

A **Configuració → Organització**.

- **Dades de l'organització**, nom, raó social, CIF/NIF, correu, telèfon i lloc web.
- **Imatge de marca**, **color de marca** i **logotip** (JPG, PNG, WebP o SVG).
- **Adreça**, que s'utilitza en rebuts i documents legals.
- **Localització**, **idioma per defecte** (s'utilitza en rebuts, correus i format de nombres),
  zona horària, moneda i format de data.

## Banca i facturació

A **Configuració → Pagaments → General**.

- **Banca**, nom del banc, **IBAN** i **BIC/SWIFT** de l'organització.
- **Facturació**, **prefix de factura**, **número següent** i **numeració anual** (reinicia la
  numeració al començament de cada any).
- **IVA per defecte**, tipus que s'aplica per defecte en calcular els rebuts.

## Domiciliació SEPA

A **Configuració → Pagaments → General**.

- **Identificador del creditor**, identificador de creditor SEPA (p. ex. `ES12000B12345678`),
  obligatori per generar remeses.
- **Format SEPA**, ISO 20022 **pain.008**, l'estàndard per als bancs de la zona SEPA.

Vegeu [Domiciliació SEPA](sepa.md) per al flux de mandats i remeses.

## Proveïdors de pagament

A **Configuració → Pagaments → Proveïdors de pagament**, configures les credencials de les
passarel·les de **pagament en línia** que veuran els socis a *Pagar ara*: **Stripe**, **Redsys**,
**Bizum** (a través de Redsys, amb el seu propi interruptor **Oferir Bizum**, desactivat per
defecte) i **domiciliació SEPA**. Cada proveïdor té un **nom visible**, un **estat** (Actiu /
Proves / Desactivat) i l'opció **Provar connexió** per validar la configuració.

> Els detalls de credencials i URL de retorn de cada proveïdor es tracten a la
> [guia de self-hosting](../self-hosting/configuration.md).

## Facturació recurrent

A **Configuració → Pagaments → Facturació recurrent**. Genera automàticament els rebuts de quota
segons un calendari:

- **Activar facturació recurrent**.
- **Dia del mes** (1–28) en què s'executa. Les quotes trimestrals i anuals només es facturen el
  primer mes del seu període.
- **Correu de notificació** opcional que rep un resum després de cada execució.

## Recordatoris de pagament

A **Configuració → Pagaments → Recordatoris de pagament**. Envia correus automàtics als socis amb
rebuts vençuts:

- **Dies després del venciment** abans del primer recordatori.
- **Repetir cada (dies)** entre recordatoris successius.
- **Recordatoris màxims** per rebut (1–10).

## Correus als membres

A **Configuració → Socis → Comunicacions**, sota l'interruptor d'anuncis, es tria **quins correus
envia el sistema**. Cada correu té el seu propi interruptor, agrupat per àrea (compte i accés,
altes, activitats, reserves, facturació, anuncis).

Tres tipus:

- **Obligatoris**, verificació de correu i restabliment de contrasenya. Apareixen bloquejats i no
  es poden desactivar: sense ells no es pot activar un compte nou ni recuperar l'accés a un
  d'existent.
- **Operatius**, el soci guanya o perd alguna cosa i no té cap altre avís (plaça alliberada,
  reserva cancel·lada pel club, enviament de rebut, recordatori de pagament). Es poden
  desactivar, però la pantalla avisa abans de què deixa de rebre el soci.
- **Opcionals**, confirmacions que el soci també veu al portal, el resum intern de facturació i
  la difusió d'anuncis.

Un correu desactivat deixa d'enviar-se en el següent intent; no cal reiniciar. Una instal·lació
que no visiti mai aquesta pantalla envia tots els correus, com fins ara.

## Altres opcions

A **Configuració → Socis**:

- **Comunicacions**, activa l'enviament d'[anuncis](communications.md).
- **Targeta de soci**, activa el [carnet digital](member-cards.md) i la seva numeració.
- **Camps de perfil**, activa els [camps personalitzats](custom-fields.md).

A **Configuració → Organització**:

- **Opcions de gènere**, configura les opcions disponibles als formularis de socis.
