<!-- source: es/admin-guide/payments.md -->
<!-- source-hash: a7d0f48a5ea4 -->

# Pagaments i rebuts

Gestió de rebuts, generació de quotes, IVA i cobraments (inclòs el pagament en línia).

> **En castellà:** [Pagos y recibos](../../es/admin-guide/payments.md).

## El rebut i el seu cicle de vida

Cada rebut té un **número**, un **soci**, una **descripció**, imports (**base**, **IVA**,
**descompte**, **total**) i un **estat**. El cicle de vida és:

**Nou** o **Pendent** → **Emès** → **Cobrat**, i, segons el cas, **Retornat**, **Anul·lat** o
**Vençut**. Un rebut retornat que es reemet torna a **Pendent**.

Accions disponibles segons l'estat: **Emetre**, **Cobrar**, **Retornar**, **Anul·lar** i
**Reemetre** (per a un rebut retornat). Des del rebut també pots **Descarregar PDF**.

Un rebut inclòs en una remesa ja **Enviada** o **Processada** no es pot **Cobrar** ni **Anul·lar**
a mà: el cobrament està en curs al banc. Importa la devolució o tanca la remesa, mira
[Domiciliació SEPA](sepa.md#remeses).

## Corregir un rebut emès

Un rebut emès no s'edita: es corregeix emetent una **factura rectificativa** des del mateix rebut
(**Emetre rectificativa**). El rebut original conserva el seu número, els seus imports i el seu
estat; la rectificativa és un document nou, amb import negatiu, que pren el número següent de la
mateixa sèrie i enllaça amb el document que rectifica. Tots dos junts sumen el que el soci deu
realment.

Pots rectificar un rebut **emès, vençut, retornat o ja cobrat**, inclosa, per tant, una quantitat
cobrada de més. Indiques el **motiu** i, si no vols rectificar el total, l'**import**; es poden
emetre diverses rectificatives parcials fins a cobrir l'import del rebut. Una rectificativa no es
cobra per remesa ni es pot anul·lar: la devolució dels diners es fa pel banc.

Anul·lar continua estant disponible per a un rebut que no s'hauria d'haver emès mai, però un rebut
ja cobrat només es corregeix amb una rectificativa.

## Origen dels rebuts

Un rebut pot tenir com a origen:

- **Quota**, quota de soci (mira *Generar quotes* i la
  [facturació recurrent](settings.md#facturació-recurrent)).
- **Activitat**, generat automàticament en confirmar una [inscripció](activities.md); s'anul·la
  si la inscripció es cancel·la.
- **Manual**, creat a mà des de la fitxa del soci.
- **Donació**: creat a mà, amb IVA 0 per defecte. No entra en els avisos d'impagament ni en
  l'import pendent del tauler: una donació sense completar no és un deute. Mira
  [Donacions](donations.md).

## Generar quotes

L'acció **Generar quotes** crea rebuts per a tots els socis actius segons el seu **tipus de
quota**. És la manera d'emetre la quota periòdica de forma massiva sense crear-los un per un.

## IVA i facturació

- El **tipus d'IVA** es calcula sobre la base; el tipus per defecte es configura a
  [Configuració → Pagaments → General](settings.md#banca-i-facturació).
- La **numeració** fa servir un prefix configurable i, opcionalment, es reinicia cada any
  (p. ex. `FAC-2026-0001`).
- El **PDF** del rebut inclou la capçalera de l'organització, les dades del soci i el desglossament
  de l'IVA, en l'idioma corresponent (ES/CA/EN).

## Mètodes de pagament i cobrament en línia

Un rebut es pot cobrar en **efectiu**, per **transferència**, amb **targeta**, per
**domiciliació** (mira [SEPA](sepa.md)) o mitjançant una **passarel·la de pagament en línia**.

Quan hi ha un proveïdor configurat, el soci veu el botó **Pagar ara** als seus rebuts pendents i
pot pagar amb:

- **Stripe**, pagament amb targeta.
- **Redsys**, passarel·la bancària espanyola amb 3D Secure.
- **Bizum**, a través de Redsys, i només si **Oferir Bizum** està activat en aquell proveïdor. El
  teu banc l'ha d'haver habilitat abans al terminal.

> La confirmació definitiva dels pagaments amb passarel·la arriba per la **notificació
> asíncrona** del proveïdor, no pel retorn del navegador. La configuració dels proveïdors es fa a
> [Configuració → Pagaments → Proveïdors de pagament](settings.md#proveïdors-de-pagament).

### Quan una notificació de pagament falla

A **Configuració → Pagaments → Proveïdors de pagament**, sota els proveïdors, **Notificacions de
pagament** llista el que les passarel·les han enviat i memship no ha aplicat:

- **Fallida**, no s'ha pogut aplicar. La passarel·la reintenta; si continua fallant, cal
  revisar-la.
- **Ignorada**, s'ha rebut i a propòsit no s'ha fet res: un tipus d'avís que no es tracta, un
  import diferent o un pagament d'un rebut **ja pagat**. Aquest últim cas és un doble cobrament:
  cal retornar el segon pagament des de la passarel·la.
- **Rebutjades per la signatura**, un recompte per proveïdor a sobre de la llista. Si no para de
  créixer, la clau configurada no és la correcta i no s'està confirmant cap pagament.

Per rebre un avís, indica l'adreça de notificacions de facturació: arriba un correu al dia, només
si en les últimes 24 hores hi ha hagut alguna cosa. És **Incidències en notificacions de
pagament** a Configuració → Socis → Comunicacions: activat per defecte en una instal·lació nova, i
es pot desactivar allà. Una instal·lació anterior comença amb ell desactivat; activa'l allà.

Si la passarel·la ha cobrat i el rebut continua pendent, marca'l com a pagat triant Redsys, Bizum o
Stripe: memship demana la **referència de la passarel·la** (el codi d'autorització o
l'identificador del pagament) per poder-ho quadrar amb el banc.

> **Per donar-los d'alta pas a pas**, quina credencial demanar a Stripe o al banc, com crear el
> webhook de Stripe i per què Redsys no el necessita, consulta la
> [guia de proveïdors de pagament](payment-providers.md).

## Tauler financer

El [tauler](reports.md) mostra l'estat dels rebuts i els imports **pendent**, **cobrat aquest
mes** i **vençut**.
