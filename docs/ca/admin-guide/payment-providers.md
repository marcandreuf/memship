<!-- source: en/admin-guide/payment-providers.md -->
<!-- source-hash: 2e0c55d58406 -->

# Proveïdors de pagament: guia de configuració

**Per a qui és:** la persona que gestiona una instal·lació de memship per al seu club o
associació (el **superadministrador**).
**Què cobreix:** tot el que hi ha a **Configuració → Pagaments → Proveïdors de pagament**:
connectar **Stripe** per als pagaments amb targeta, i **Redsys** per a la passarel·la bancària
espanyola i **Bizum**.

> **En anglès:** [Payment providers: Setup Guide](../../en/admin-guide/payment-providers.md).

No cal editar cap fitxer ni reiniciar res. Totes les credencials d'aquesta guia s'introdueixen a
la interfície web i tenen efecte a la petició següent.

---

## Índex

1. [Abans de començar](#1-abans-de-començar)
2. [Com es protegeixen els secrets](#2-com-es-protegeixen-els-secrets)
3. [Com es completa realment un pagament en línia](#3-com-es-completa-realment-un-pagament-en-línia)
4. [Stripe](#4-stripe)
   - [Què necessites](#41-què-necessites)
   - [Obtenir les claus d'API](#42-obtenir-les-claus-dapi)
   - [Crear l'endpoint del webhook](#43-crear-lendpoint-del-webhook)
   - [Omplir la pantalla](#44-omplir-la-pantalla)
   - [Proves](#45-proves)
   - [Resolució de problemes de Stripe](#46-resolució-de-problemes-de-stripe)
5. [Redsys i Bizum](#5-redsys-i-bizum)
   - [Què necessites](#51-què-necessites)
   - [Obtenir les credencials del teu banc](#52-obtenir-les-credencials-del-teu-banc)
   - [Per què no hi ha cap webhook per configurar](#53-per-què-no-hi-ha-cap-webhook-per-configurar)
   - [Omplir la pantalla](#54-omplir-la-pantalla)
   - [Proves](#55-proves)
   - [Resolució de problemes de Redsys](#56-resolució-de-problemes-de-redsys)
6. [Activació, mode de proves i què veuen els socis](#6-activació-mode-de-proves-i-què-veuen-els-socis)
   - [Quan una notificació de pagament falla](#61-quan-una-notificació-de-pagament-falla)
7. [Referència de camps](#7-referència-de-camps)

---

## 1. Abans de començar

**Accés.** Pagaments només és visible per als usuaris amb el rol de **superadministrador**. Un
administrador normal no veu la pestanya. Ves a **Configuració → Pagaments** i després a la
subpestanya **Proveïdors de pagament**.

**Una adreça pública.** Tots dos proveïdors han de poder arribar a la teva instal·lació des
d'internet per confirmar un pagament. Aquesta adreça es configura una sola vegada en instal·lar,
a `BACKEND_PUBLIC_URL` i `FRONTEND_URL`. Un proveïdor configurat en una instal·lació a la qual
internet no pot arribar cobrarà els diners i no marcarà mai el rebut com a pagat.

**La domiciliació és una altra cosa.** Si els teus socis paguen per domiciliació SEPA, res d'això
no s'aplica, mira [SEPA](sepa.md). Aquesta guia tracta només del pagament en línia amb targeta o
Bizum.

---

## 2. Com es protegeixen els secrets

El xifratge, l'emmagatzematge i la còpia de seguretat funcionen igual que a la resta de
Configuració, i es descriuen sencers a
[Integracions → Com es protegeixen els secrets](integrations.md#2-com-es-protegeixen-els-secrets). L'edició difereix en una cosa,
a l'últim punt de sota. En resum:

- Els valors secrets es **xifren abans de desar-se** a la base de dades.
- **No es tornen mai al navegador.** Un secret desat no és cap camp d'entrada: es mostra com a
  text (`••••` més els quatre últims caràcters, i la paraula *desat*) al costat d'un botó
  **Substitueix**, i el camp només apareix quan el prems. És l'esperat, no un error, i és
  deliberat: un gestor de contrasenyes no té cap camp per omplir, així que no pot sobreescriure
  en silenci una credencial que funciona la propera vegada que desis.
- **Fes còpia de seguretat del fitxer de la clau de xifratge juntament amb la base de dades.**
  Si restaures un bolcat en una màquina amb un altre fitxer de clau, els secrets desats no es
  podran desxifrar i els hauràs de tornar a introduir.
- **Un secret desat no es pot buidar.** Desar un valor en blanc a sobre es rebutja, indicant el
  camp, i el valor desat es queda com estava. Aquí no hi ha *Esborra*, a diferència de les
  pantalles d'Integracions, que en tenen perquè una integració es pot desactivar legítimament
  traient-ne la credencial. El secret d'un proveïdor de pagament només se substitueix: prem
  **Substitueix** i enganxa el valor nou. Si el proveïdor es retira, elimina la fila del
  proveïdor, cosa que la pantalla rebutja mentre hi hagi rebuts vinculats.

> **Per què rebutjar el valor en blanc en lloc d'acceptar-lo?** El valor desat està xifrat i és
> l'única còpia, res no el pot recuperar un cop sobreescrit. Un camp en blanc gairebé sempre és
> un enganxament que ha anat malament i no una instrucció, i abans de la v2.19.0 s'acceptava: el
> secret se substituïa per res, i en un proveïdor encara *desactivat* el desament informava d'èxit.

Quins camps es tracten com a secrets depèn del proveïdor, i no és arbitrari, una clau publicable
està pensada per ser pública, així que es desa en clar i es mostra sencera.

| Proveïdor | Xifrat | Desat en clar |
|---|---|---|
| Stripe | `secret_key`, `webhook_secret` | `publishable_key` |
| Redsys | `secret_key` | `merchant_code`, `terminal_id`, `environment`, `currency_code` |

---

## 3. Com es completa realment un pagament en línia

Val la pena entendre-ho abans de configurar res, perquè explica *per a què* serveixen les
credencials i per què una configuració errònia passa desapercebuda en lloc de fer soroll.

Quan un soci paga passen tres coses, i només una és determinant:

1. **memship envia el soci al proveïdor.** Per a Stripe és una redirecció a una sessió de
   Checkout; per a Redsys és un formulari signat que s'envia automàticament a la pàgina del TPV
   del banc.
2. **El soci paga i el seu navegador torna** a una pàgina de memship. **Aquest retorn no és la
   confirmació.** El soci pot tancar la pestanya, perdre la cobertura o tirar enrere, i el
   navegador no és una part de qui memship es pugui fiar per saber si s'han mogut diners.
3. **El proveïdor fa una crida de servidor a servidor a memship** confirmant el resultat.
   **Aquesta és la font de veritat**, i és l'única cosa que marca un rebut com a pagat.

Tot el que diu aquesta guia sobre webhooks, URL de notificació i claus de signatura existeix per
fer que el pas 3 funcioni i per demostrar que la crida ve realment del proveïdor.

**Per això també una configuració trencada passa desapercebuda.** L'endpoint que rep les crides
no té autenticació per disseny, la seguretat ve de verificar la signatura del proveïdor, no d'un
inici de sessió. Si el secret de signatura és incorrecte, totes les confirmacions fallen la
verificació i es descarten. Per al soci el pagament ha anat bé; a memship el rebut simplement es
queda sense pagar, i cap pantalla no informa de cap error. **Completa sempre un pagament de prova
real de cap a cap abans d'anunciar un mètode de pagament als socis.**

---

## 4. Stripe

Stripe gestiona els pagaments amb targeta mitjançant Stripe Checkout, una pàgina de pagament
allotjada per Stripe. Les dades de la targeta no arriben mai al teu servidor.

### 4.1 Què necessites

Un compte de Stripe i, d'aquest compte, tres valors: una **clau secreta**, una **clau
publicable** i un **secret de signatura del webhook**. Els dos primers surten de la pàgina de
claus d'API. El tercer encara no existeix, el crees al pas 4.3.

### 4.2 Obtenir les claus d'API

1. Inicia sessió a [dashboard.stripe.com](https://dashboard.stripe.com).
2. Ves a **Developers → API keys** ([documentació](https://docs.stripe.com/keys)).
3. Copia la **Publishable key**, comença per `pk_`.
4. Mostra i copia la **Secret key**, comença per `sk_`.

Stripe té claus separades per al mode de proves i el mode real, que se seleccionen amb
l'interruptor del tauler. Les claus de proves són `pk_test_` / `sk_test_`, les reals `pk_live_` /
`sk_live_`. Fes servir les claus de proves fins que hagis completat un pagament de prova de cap a
cap.

> memship comprova que la clau secreta comenci per `sk_` i la publicable per `pk_`, i es nega a
> desar un valor al camp equivocat. **No** comprova a quin mode pertany una clau, combinar una
> clau secreta real amb una clau publicable de proves s'accepta i fallarà en el moment del
> pagament.

### 4.3 Crear l'endpoint del webhook

**Aquest és el pas on la gent s'encalla, així que llegeix amb atenció la frase següent.** El
webhook és una cosa que crees *tu* a Stripe, apuntant a memship. memship no crea res al teu
compte de Stripe. El secret que acabaràs enganxant a memship l'emet Stripe *després* que
l'endpoint existeixi.

**La URL que necessites és:**

```
https://<your-memship-address>/api/v1/webhooks/stripe
```

No l'has de construir a mà: el formulari del proveïdor Stripe a **Configuració → Pagaments → Proveïdors de
pagament** la mostra, construïda a partir de `BACKEND_PUBLIC_URL`, amb un botó per copiar-la. El
prefix `/api/v1/` és important: la configuració del proxy invers inclosa només encamina
`/api/v1/*` a l'API i envia tota la resta a la interfície web, així que una URL sense el prefix
arriba al servei equivocat i Stripe informarà d'errors.

Després, al tauler de Stripe ([documentació dels webhooks](https://docs.stripe.com/webhooks)):

1. Ves a **Developers → Webhooks → Add endpoint**.
2. **Endpoint URL**, la URL de dalt.
3. **Events from**, *Your account*.
4. **Payload style**, **Snapshot**. Això és important: memship llegeix l'objecte de
   l'esdeveniment complet, i un payload *Thin* només porta identificadors, així que les
   confirmacions arribarien sense res amb què actuar.
5. **API version**, el valor per defecte ja va bé. memship no fixa cap versió i només llegeix
   camps de la Checkout Session estables des de fa temps.
6. **Select events**, tria exactament aquests dos:
   - `checkout.session.completed`
   - `checkout.session.expired`
7. Crea l'endpoint i després **mostra el Signing secret**. Comença per `whsec_`. Aquest és el
   valor que memship anomena **Secret del webhook**.

> **Subscriu-te només a aquests dos esdeveniments.** memship ignora qualsevol altre tipus
> d'esdeveniment, així que subscriure-te'n a més no fa cap mal més enllà de generar trànsit i
> soroll als registres de Stripe, però un tauler ple d'enviaments que memship descarta
> deliberadament fa més difícil detectar un problema real.

### 4.4 Omplir la pantalla

A **Configuració → Pagaments → Proveïdors de pagament**, afegeix un proveïdor Stripe i introdueix:

| Camp | Valor |
|---|---|
| Clau secreta | la clau `sk_…` del 4.2 |
| Clau publicable | la clau `pk_…` del 4.2 |
| Secret del webhook | el secret `whsec_…` del 4.3 |

Un proveïdor acabat de crear comença **desactivat**. Primer configura'l, prova'l i després
activa'l.

> **El Secret del webhook es comprova, però només la seva forma.** memship es nega a desar un
> valor que no comenci per `whsec_`, així que l'error d'enganxament habitual, una clau secreta,
> una clau publicable, alguna cosa de la casella equivocada, es detecta en el moment de desar-lo
> i no en activar. El que cap comprovació local no pot detectar és un secret *amb la forma
> correcta* d'un altre endpoint: un d'antic, o un d'un endpoint que has eliminat. Té exactament
> el mateix aspecte, es desa sense problemes i després falla la verificació en cada
> esdeveniment, el soci veu que ha anat bé i el rebut es queda sense pagar. memship rebutja
> cadascuna d'aquestes notificacions i les compta, així que **Notificacions de pagament** (mira
> [6.1](#61-quan-una-notificació-de-pagament-falla)) mostra els rebuigs i el motiu, però només
> un cop s'ha intentat un pagament real. La prova de cap a cap del 4.5 és el que et diu que el
> valor és el correcte.

### 4.5 Proves

**El botó Provar connexió fa una crida real a Stripe.** Recupera el teu compte i, si va bé,
mostra el nom visible o l'identificador del compte i el seu país. Això demostra que la clau
secreta funciona. **No** prova el secret del webhook, que no es pot verificar sense un
esdeveniment real.

Per provar el webhook, porta un rebut fins a un pagament real amb Stripe en mode de proves i
[una targeta de proves](https://docs.stripe.com/testing). Després confirma dues coses:

- el rebut a memship ha passat a **cobrat**
- l'enviament a **Stripe → Developers → Webhooks** mostra una resposta `2xx`

Un enviament que mostra `400` amb un error de signatura vol dir que el Secret del webhook és
incorrecte; memship també el compta a **Notificacions de pagament**.

### 4.6 Resolució de problemes de Stripe

| Símptoma | Causa |
|---|---|
| El botó de prova informa d'un error d'autenticació | La clau secreta és incorrecta, s'ha revocat o pertany a l'altre mode |
| El pagament es completa a Stripe, el rebut es queda sense pagar, Stripe mostra `400` | El Secret del webhook és incorrecte |
| El pagament es completa, el rebut es queda sense pagar, Stripe no mostra cap enviament | La URL de l'endpoint és incorrecta o no és accessible des d'internet |
| Stripe mostra `404` | A la URL li falta el prefix `/api/v1/`, així que ha arribat a la interfície web en lloc de l'API |
| El rebut es queda sense pagar, tota la resta sembla correcte | Mira la nota sobre la discrepància d'import de sota |

> **Un pagament per un import equivocat es rebutja a propòsit.** memship compara l'import que
> informa Stripe amb el total del rebut i, si no coincideixen, **deixa el rebut sense pagar** i
> registra la notificació com a **ignorada** amb tots dos imports, a **Notificacions de
> pagament**, perquè una persona la revisi. Una signatura vàlida demostra que el missatge l'ha
> enviat Stripe, no que la suma sigui la que vas demanar. Això té exactament el mateix aspecte
> que un webhook trencat, així que revisa Notificacions de pagament abans de concloure que la
> configuració és incorrecta.

---

## 5. Redsys i Bizum

Redsys és la passarel·la que fan servir la majoria de bancs espanyols, i opera el *TPV Virtual*.
La mateixa entrada de proveïdor serveix també per a **Bizum**, que és un mètode de pagament dins
de Redsys, no una connexió separada per configurar. No hi ha unes segones credencials per a
Bizum; hi ha un interruptor, **Oferir Bizum**, i està desactivat fins que l'actives.

### 5.1 Què necessites

El teu banc t'ha d'haver emès un TPV Virtual. Del contracte o del portal del banc necessites
quatre valors: el **codi de comerç (FUC)**, un **número de terminal**, una **clau de signatura**,
i saber si treballes contra l'entorn de proves o el de producció.

**Si vols Bizum, demana al teu banc que l'activi en aquell terminal.** Bizum l'activa el banc per
comerç i terminal, no res que introdueixis aquí, i les mateixes credencials serveixen per a
targeta i per a Bizum un cop activat. Val la pena demanar-ho al mateix temps que el TPV, perquè
un terminal sense Bizum rebutja els pagaments amb Bizum a la passarel·la. Demana també les
credencials de **proves**: són les que fas servir mentre el camp Entorn digui `test`.

Quan el banc t'ho confirmi, activa **Oferir Bizum** a l'entrada de Redsys. memship no pot
comprovar el terminal, la passarel·la no ofereix cap manera de preguntar-ho, així que aquell
interruptor és la teva declaració que el banc ja ho ha fet, i el primer pagament real amb Bizum
continua sent la prova.

### 5.2 Obtenir les credencials del teu banc

No surten d'un tauler d'autoservei com les de Stripe, les emet el banc que t'ha venut el TPV, i
el portal canvia d'un banc a un altre. Redsys publica la documentació tècnica a
[pagosonline.redsys.es](https://pagosonline.redsys.es/).

- **Codi de comerç (FUC)**, el teu identificador de comerç, de 7 a 9 dígits.
- **ID de terminal**, numèric, normalment `1` tret que el banc te n'hagi emès diversos.
- **Clau de signatura**, el secret que serveix per signar les peticions i verificar les
  notificacions. Als portals dels bancs sol aparèixer com a *clave secreta de encriptación* o
  *clave de firma*. **Els entorns de proves i de producció tenen claus diferents.**
- **Codi de moneda**, numèric ISO 4217. Per a l'euro és **978**, que és el valor per defecte.

### 5.3 Per què no hi ha cap webhook per configurar

A diferència de Stripe, **no has de registrar cap URL de notificació enlloc.** memship inclou
l'adreça de retorn a cada petició de pagament, així que a la passarel·la se li diu on ha de
respondre cada vegada. No hi ha res a configurar al portal del banc ni res a mantenir
sincronitzat.

Per la mateixa raó no hi ha un secret de webhook separat. La **Clau de signatura** fa les dues
feines: memship signa amb ella les peticions sortints i verifica amb ella les notificacions
entrants. Un sol valor, introduït una sola vegada.

Si mai necessites saber l'adreça que envia memship, és
`https://<your-memship-address>/api/v1/webhooks/redsys`, però no l'hauries de configurar enlloc.

### 5.4 Omplir la pantalla

| Camp | Valor |
|---|---|
| Codi de comerç (FUC) | 7–9 dígits, del teu banc |
| ID de terminal | numèric, del teu banc |
| Clau de signatura | la clau de signatura **de l'entorn que has seleccionat** |
| Entorn | `test` mentre fas proves, `production` quan és real |
| Codi de moneda | `978` per a l'euro |

> **Confirma que el camp Entorn diu `production` abans de començar a cobrar de debò.** memship
> es nega a activar un proveïdor l'entorn del qual no sigui ni `test` ni `production`, així que
> un error tipogràfic es rebutja en lloc d'acceptar-se en silenci. El que no pot detectar és un
> valor vàlid que no volies: `test` s'activa sense queixes i envia socis reals al TPV de proves,
> on els seus pagaments no existeixen.

### 5.5 Proves

**El botó Provar connexió no contacta amb Redsys.** Redsys no té cap endpoint per fer-hi ping,
així que el botó valida la teva configuració localment. És deliberadament més estricte que desar:
rebutja un codi de comerç que no tingui de 7 a 9 dígits, que és la longitud que un TPV real
rebutja directament.

Provar de debò vol dir fer un pagament contra l'entorn de proves, amb la clau de signatura de
proves i els números de targeta que et doni el banc. Confirma després que el rebut passa a
**cobrat**, el navegador que torna a una pàgina d'èxit no és la confirmació, tal com s'explica a
la secció 3.

### 5.6 Resolució de problemes de Redsys

| Símptoma | Causa |
|---|---|
| El botó de prova informa que el codi de comerç ha de tenir 7–9 dígits | El FUC és incorrecte, o té espais o lletres |
| La passarel·la rebutja el pagament immediatament | La clau de signatura no correspon a l'entorn |
| Els pagaments van bé però no apareixen enlloc on els puguis trobar | L'Entorn és `test` (o un error tipogràfic que hi recau) mentre creies que era producció |
| El rebut es queda sense pagar després d'un pagament correcte | La notificació no ha pogut arribar a la teva instal·lació, comprova que sigui accessible des d'internet |
| `SIS0051, Pedido repetido` | Un número de comanda duplicat. memship genera un prefix aleatori nou a cada intent, així que hauria de ser estrany; reintentar-ho n'emet un de nou |
| `SIS0475` en un pagament amb Bizum, els pagaments amb targeta van bé | Bizum no està activat en aquell comerç i terminal. Demana al teu banc que l'activi, res de la configuració de memship no ho canvia |
| `SIS0027`, i la passarel·la mostra l'import en una altra moneda | El terminal no està configurat per a la moneda que envies. Comprova el camp Codi de moneda, i consulta amb el teu banc quin terminal has de fer servir per a l'euro |

---

## 6. Activació, mode de proves i què veuen els socis

Un proveïdor té tres estats:

| Estat | Significat |
|---|---|
| **Desactivat** | Configurat però no s'ofereix. Els socis no hi veuen cap botó |
| **Proves** | S'ofereix, per provar el flux de cap a cap |
| **Actiu** | S'ofereix als socis com a mètode de pagament real |

**Activar Redsys ofereix la targeta. Bizum és un interruptor separat.** Els socis veuen *Targeta*
als seus rebuts i a la pàgina de la seva quota tan bon punt l'entrada de Redsys és activa;
*Bizum* només apareix quan **Oferir Bizum** també està activat. Deixa'l desactivat fins que el
banc t'hagi confirmat Bizum al terminal, un botó de Bizum en un terminal que no el té falla a la
passarel·la per a cada soci que el prem, i res a la seva pantalla no explica per què.

Ofereixis el que ofereixis, fes servir primer l'estat **Proves** i completa un pagament real de
cada tipus que vulguis acceptar abans de passar a actiu.

**memship es nega a activar un proveïdor que no podria cobrar un pagament.** L'activació és
l'últim moment en què una configuració incompleta encara és un problema de configuració; un cop
passat, el camp que falta torna a sortir com un pagament fallit a la pantalla d'un soci. Si es
rebutja l'activació, el missatge indica els camps que fallen.

Aquesta comprovació és local. Confirma que la teva configuració és coherent internament; no pot
saber que ahir es va revocar una clau al proveïdor. És un motiu més per completar un pagament
real abans de confiar-hi.

### 6.1 Quan una notificació de pagament falla

Sota els proveïdors, **Notificacions de pagament** llista el que les passarel·les han enviat i
memship no ha aplicat:

- **Fallida**, memship no l'ha pogut aplicar. La passarel·la reintenta, així que una fallada que
  es resol sola és normal; una que es manté no ho és.
- **Ignorada**, memship l'ha rebuda i deliberadament no ha fet res: un tipus d'esdeveniment que
  no tracta, un import equivocat o un pagament d'un rebut **ja pagat**. Aquest últim cas és com
  es manifesta un doble cobrament, el soci ha pagat dues vegades i cal retornar el segon pagament
  a la passarel·la.
- **Rebutjades per la signatura**, que es mostren com un recompte per proveïdor a sobre de la
  llista, amb l'últim motiu. No es desen mai, perquè no es pot confiar en res d'un missatge no
  verificat. Un recompte que no para de créixer vol dir que el secret configurat és incorrecte i
  que no s'està confirmant **cap** pagament.

Perquè t'avisin en lloc d'haver-ho de mirar, indica l'adreça de notificacions de facturació.
memship envia aleshores un correu al dia, només quan alguna cosa ha anat malament en les 24 hores
anteriors. El correu és **Incidències en notificacions de pagament** a Configuració → Socis →
Comunicacions: activat per defecte en una instal·lació nova, i es pot desactivar allà. Una
instal·lació anterior comença amb ell desactivat, activa'l allà.

Si la passarel·la ha cobrat i el rebut continua sense pagar, marca'l com a pagat a mà triant
Redsys, Bizum o Stripe com a mètode: memship demana la referència de la passarel·la (el codi
d'autorització o l'identificador del pagament de la liquidació) perquè el pagament es pugui
continuar quadrant amb el banc.

---

## 7. Referència de camps

**Stripe**

| Camp | Obligatori | Secret | Format comprovat | D'on surt |
|---|---|---|---|---|
| Clau secreta | sí | sí | ha de començar per `sk_` | Stripe → Developers → API keys |
| Clau publicable | sí | no | ha de començar per `pk_` | Stripe → Developers → API keys |
| Secret del webhook | sí | sí | ha de començar per `whsec_` | Stripe → Developers → Webhooks, després de crear l'endpoint |

**Redsys**

| Camp | Obligatori | Secret | Format comprovat | D'on surt |
|---|---|---|---|---|
| Codi de comerç (FUC) | sí | no | només dígits; 7–9 amb Provar connexió | el teu banc |
| ID de terminal | sí | no | només dígits | el teu banc |
| Clau de signatura | sí | sí | no | el teu banc, per entorn |
| Entorn | sí | no | `test` o `production` | tria teva |
| Codi de moneda | sí | no | exactament 3 dígits | ISO 4217, `978` per a l'euro |
| Oferir Bizum | no | no | n/a | el teu banc, un cop et confirmi Bizum al terminal. Desactivat per defecte |

---

## Relacionat

- [Pagaments i rebuts](payments.md), l'ús dels pagaments en el dia a dia
- [Donacions](donations.md): un enllaç de donació al lloc web de la mateixa organització. Aquest
  enllaç es crea al tauler del proveïdor i no té res a veure amb el proveïdor configurat aquí
- [SEPA](sepa.md), la domiciliació, un mecanisme separat
- [Integracions](integrations.md), SSO i correu, i la descripció completa de l'emmagatzematge de
  secrets
- [Referència de configuració](../self-hosting/configuration.md), `BACKEND_PUBLIC_URL` i
  `FRONTEND_URL`
