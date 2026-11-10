<!-- source: en/admin-guide/integrations.md -->
<!-- source-hash: ea5f99d8c47e -->

# Integracions: guia de configuració

**Per a qui és:** la persona que gestiona una instal·lació de memship per al seu club o associació
(el **superadministrador**).
**Què cobreix:** tot el que hi ha a **Configuració → Integracions**, l'inici de sessió amb
Google / Apple (**Inici de sessió (SSO)**) i l'enviament de correu (**Correu**), més les opcions
de registre que hi van associades.

> **En anglès:** [Integrations: Setup Guide](../../en/admin-guide/integrations.md).

No cal editar cap fitxer ni reiniciar res. Totes les credencials d'aquesta guia s'introdueixen a
la interfície web i tenen efecte a la petició següent.

---

## Taula de continguts

1. [Abans de començar](#1-abans-de-començar)
2. [Com es protegeixen els secrets](#2-com-es-protegeixen-els-secrets)
3. [Inici de sessió únic (SSO)](#3-inici-de-sessió-únic-sso)
   - [Com funciona per a un soci](#31-com-funciona-per-a-un-soci)
   - [Pas comú: la teva URL pública i les URI de redirecció](#32-pas-comú-la-teva-url-pública-i-les-uri-de-redirecció)
   - [Google: obtenir les credencials](#33-google-obtenir-les-credencials)
   - [Apple: obtenir les credencials](#34-apple-obtenir-les-credencials)
   - [Omplir la pantalla](#35-omplir-la-pantalla)
   - [Resolució de problemes de l'SSO](#36-resolució-de-problemes-de-lsso)
4. [Correu](#4-correu)
   - [Com funciona](#41-com-funciona)
   - [Resend: obtenir les credencials](#42-resend-obtenir-les-credencials)
   - [SMTP: les dades del teu servidor, o Gmail](#43-smtp-les-dades-del-teu-servidor-o-gmail)
   - [Omplir la pantalla, provar i activar](#44-omplir-la-pantalla-provar-i-activar)
   - [Resolució de problemes del correu](#45-resolució-de-problemes-del-correu)
5. [Opcions de registre que acompanyen aquestes integracions](#5-opcions-de-registre-que-acompanyen-aquestes-integracions)
6. [Alternativa amb el fitxer de configuració (`.env`)](#6-alternativa-amb-el-fitxer-de-configuració-env)
7. [Referència de camps](#7-referència-de-camps)

---

## 1. Abans de començar

**Accés.** Integracions només és visible per als usuaris amb el rol de **superadministrador**. Un
administrador normal no veu la pestanya. Ves a **Configuració → Integracions**; a dins hi ha dues
subpestanyes: **Inici de sessió (SSO)** i **Correu**.

**Una adreça pública.** Totes dues integracions donen per fet que la teva instal·lació és
accessible en una adreça real (per exemple `https://socios.myclub.org`), configurada un sol cop en
instal·lar a `BACKEND_PUBLIC_URL` i `FRONTEND_URL`. La pantalla d'Integracions mostra la URL del
backend en només lectura, amb un botó de copiar.

**HTTPS.** Google funciona sobre `http://localhost` per fer proves, però **Apple no**: rebutja
`localhost` i l'HTTP pla, i exigeix un domini real amb un certificat vàlid. Compta a configurar
Apple només a la instal·lació en producció.

**Comptes que potser hauràs de crear:**

| Integració | Necessites | Cost |
| ----------- | -------- | ---- |
| Inici de sessió amb Google | Un compte de Google (Google Cloud Console) | Gratuït |
| Inici de sessió amb Apple | Una subscripció a l'**Apple Developer Program** | Quota anual de pagament |
| Correu amb Resend | Un compte de Resend + un domini que controlis | Hi ha un pla gratuït |
| Correu per SMTP | Les dades SMTP del teu allotjament de correu actual, o un compte de Google amb la verificació en 2 passos activada per a Gmail | Normalment ja pagat / Gratuït |

No cal configurar-ho tot. Els proveïdors d'inici de sessió són opcionals (els socis sempre poden
fer servir correu + contrasenya). El correu és, a la pràctica, obligatori: sense ell no s'envien
els correus de verificació, d'aprovació ni de rebuts.

---

## 2. Com es protegeixen els secrets

Alguns dels valors que escrius aquí són secrets de debò: un secret de client de Google, una clau
privada d'Apple, una clau d'API de Resend, una contrasenya SMTP (per a Gmail, una contrasenya
d'aplicació).

- Es **xifren abans de desar-los** a la base de dades.
- **Mai no es tornen a enviar al navegador**. Un cop desat un secret, el camp deixa de ser una
  casella d'entrada: es mostra com a text (`••••` més els quatre últims caràcters, i la paraula
  *desat*) al costat d'un botó **Substitueix**. És el comportament esperat; no hi ha manera de
  tornar a llegir un secret desat des de la interfície, ni cap casella que un gestor de
  contrasenyes pugui omplir, i aquesta és la idea. Abans, una casella plena amagava l'únic senyal
  que ja hi havia un valor desat, i en desar s'enviava el que el navegador hi hagués injectat per
  sobre d'una credencial que funcionava.
- La clau de xifratge la **genera automàticament** el servidor el primer cop que es fa servir i
  l'escriu en un fitxer de clau al volum d'emmagatzematge (mai a la base de dades). No l'has de
  crear tu.

A la part superior de cada pantalla d'Integracions veuràs un d'aquests dos avisos:

- 🟢 **"Xifratge actiu"**, estat normal. No cal fer res.
- 🟠 **"El servidor no té una clau de xifratge vàlida: o no ha pogut crear el fitxer de clau
  (comprova que el volum d'emmagatzematge té permisos d'escriptura) o MEMSHIP_SECRET_KEY no és una
  clau vàlida."**, el servidor no ha pogut ni llegir ni crear el fitxer de clau, o
  `MEMSHIP_SECRET_KEY` conté una cosa que no és una clau vàlida. Fins que no se solucioni, els
  camps secrets no es poden desar (els no secrets, sí). Corregeix els permisos del volum
  d'emmagatzematge muntat al contenidor del backend, o corregeix o treu `MEMSHIP_SECRET_KEY`, i
  després recarrega la pàgina.

> **Fes la còpia de seguretat del fitxer de clau juntament amb la base de dades.** Si restaures
> un bolcat de la base de dades en una màquina que té un fitxer de clau *diferent*, els secrets
> desats ja no es poden desxifrar. No peta res, memship recorre al que hi hagi a `.env` i els
> camps afectats simplement es comporten com si estiguessin buits, però hauràs de tornar a
> introduir tots els secrets. El fitxer de clau és al volum d'emmagatzematge; la seva ruta és
> `SECRETS_KEY_FILE`, per defecte `<storage>/secret.key`.

**Regles d'edició per a tots els camps secrets** (iguals a les dues subpestanyes):

- **No el toquis** → es conserva el valor desat sense canvis. Per a un camp que encara no té res
  desat, deixar-lo en blanc fa el mateix.
- Fes clic a **Substitueix** → apareix una casella, i només el valor que hi escriguis s'envia com
  a secret nou. **Cancel·lar** torna el camp al seu estat sense canviar res.
- Fes clic a **Esborra** → el valor desat s'elimina en desar (fes clic a **Desfés** per
  cancel·lar-ho abans de desar).

---

## 3. Inici de sessió únic (SSO)

**Configuració → Integracions → Inici de sessió (SSO)**

### 3.1 Com funciona per a un soci

Un cop actives un proveïdor, apareix un botó **"Continuar amb Google"** / **"Continuar amb
Apple"** tant a la pàgina d'inici de sessió com a la de registre. Els botons només apareixen per
als proveïdors activats i configurats del tot: ningú no veu un botó que fallaria.

Què passa quan una persona el fa servir:

1. L'envien a Google / Apple, hi inicia sessió i torna a memship.
2. **Si ja té un compte de memship amb la mateixa adreça de correu, verificada pel proveïdor**, el
   proveïdor es vincula a aquest compte existent. A partir d'aquí pot iniciar sessió de les dues
   maneres, amb contrasenya o amb el proveïdor.
3. **Si és nova**, se li crea un compte i una fitxa de soci amb l'estat **pendent**, i s'apliquen
   les regles d'alta habituals: arriba a la pantalla *Pendent d'aprovació* fins que un
   administrador l'aprova des de **Socis → Altes pendents**. El número de soci s'assigna en
   aprovar-la.
4. El seu correu compta com a ja verificat (el proveïdor n'ha respost), així que no rep cap correu
   de verificació.

Coses que convé saber:

- Els comptes creats a través d'un proveïdor **no tenen contrasenya**. Si més endavant la persona
  vol iniciar sessió amb contrasenya, fa servir el flux de "Has oblidat la contrasenya?" per
  definir-ne una.
- Una sola persona pot tenir contrasenya + Google + Apple apuntant al mateix compte.
- El registre públic ha d'estar activat perquè les persones *noves* es puguin donar d'alta així,
  mira la [secció 5](#5-opcions-de-registre-que-acompanyen-aquestes-integracions).

### 3.2 Pas comú: la teva URL pública i les URI de redirecció

A la part superior de la pantalla d'SSO hi ha una targeta que mostra la teva **URL del backend**,
i cada targeta de proveïdor mostra la seva **URI de redirecció**. Totes dues tenen un botó de
copiar. Són els valors que demanen les consoles dels proveïdors. Tenen aquest aspecte:

```
Backend URL   https://socios.myclub.org
Google        https://socios.myclub.org/api/v1/auth/oauth/google/callback
Apple         https://socios.myclub.org/api/v1/auth/oauth/apple/callback
```

Copia-les de la pantalla en lloc d'escriure-les: han de coincidir **caràcter per caràcter** a
totes dues bandes, inclòs el `https://` i l'absència de barra final. Una discrepància és, de
lluny, la causa més habitual d'un inici de sessió fallit.

Si la URL del backend que es mostra és incorrecta (per exemple `http://localhost:8003` en un
servidor en producció), s'ha de corregir a la variable `BACKEND_PUBLIC_URL` de la instal·lació;
expressament no es pot editar des de la pantalla, perquè descriu com està publicat el teu
servidor, no com està configurat un proveïdor.

### 3.3 Google: obtenir les credencials

Necessites dos valors: un **ID de client** i un **secret de client**.

1. Ves a **[Google Cloud Console](https://console.cloud.google.com/)** i inicia sessió.
2. Crea un projecte (barra superior → selector de projectes → **New project**), posa-li un nom
   com `Memship – My Club` i selecciona'l.
3. Al menú de l'esquerra obre **APIs & Services → OAuth consent screen**.
   - User type: **External** (tret que tots els socis tinguin un compte a la teva organització de
     Google Workspace; en aquest cas, Internal ja va bé).
   - App name: el nom del teu club, tal com el veuran els socis a la pantalla de consentiment de
     Google.
   - User support email i developer contact email: la teva adreça.
   - Scopes: els per defecte `email`, `profile`, `openid` són tot el que cal. No n'afegeixis cap
     més: els scopes addicionals activen la revisió de verificació de Google.
   - Afegeix el teu logotip i un enllaç al teu web si vols que la pantalla de consentiment
     s'assembli a vosaltres. Opcional.
   - **Publica l'aplicació** (botó **Publish app** → *In production*). Mentre és a *Testing*,
     només poden iniciar sessió les adreces de correu que hagis afegit com a usuaris de prova.
4. Obre **APIs & Services → Credentials → Create credentials → OAuth client ID**.
   - Application type: **Web application**.
   - Name: el que vulguis, p. ex. `memship web`.
   - **Authorised redirect URIs → Add URI**: enganxa la URI de redirecció de Google copiada de la
     pantalla de memship.
   - (Authorised JavaScript origins es pot deixar buit: memship fa l'intercanvi al servidor.)
   - **Create**.
5. Google mostra el **Client ID** (acaba en `.apps.googleusercontent.com`) i el **Client secret**
   (comença per `GOCSPX-`). Copia'ls tots dos ara; el secret es pot tornar a copiar més tard des de
   la mateixa pàgina.

### 3.4 Apple: obtenir les credencials

Apple necessita **quatre** valors: un ID de client (Services ID), un ID d'equip, un ID de clau i
un fitxer de clau privada. Fa més feina que Google, compta 20 minuts.

Requisits: una subscripció de pagament a l'**Apple Developer Program** i un domini HTTPS en
producció (Apple rebutja `localhost` i els certificats autosignats).

1. Ves a **[developer.apple.com/account](https://developer.apple.com/account)** → **Certificates,
   Identifiers & Profiles**.
2. **Crea un App ID**, *Identifiers* → **+** → **App IDs** → **App**.
   - Description: el nom del teu club. Bundle ID: p. ex. `org.myclub.memship`.
   - A la llista de capacitats, marca **Sign in with Apple**. Register.
3. **Crea un Services ID**, *Identifiers* → **+** → **Services IDs**.
   - Description: p. ex. `Memship Web`. Identifier: p. ex. `org.myclub.memship.web`.
   - ⚠️ **Aquest identificador és el valor que memship anomena ID de client.** *No* és l'App ID
     del pas 2, i confondre'ls és l'error clàssic en configurar Apple.
   - Registra'l, després **torna a obrir el Services ID** i marca **Sign in with Apple →
     Configure**:
     - Primary App ID: l'App ID del pas 2.
     - **Domains and Subdomains**: el teu domini sense l'esquema, `socios.myclub.org`.
     - **Return URLs**: enganxa la URI de redirecció d'Apple copiada de la pantalla de memship
       (amb `https://`).
     - Desa, i després **Continue / Save** al mateix Services ID.
4. **Crea una clau**, *Keys* → **+**.
   - Key name: p. ex. `Memship Sign in with Apple`.
   - Marca **Sign in with Apple** → **Configure** → selecciona el Primary App ID → Save →
     Continue → Register.
   - **Descarrega el fitxer `.p8`.** ⚠️ Apple només et deixa descarregar-lo **un cop**. Si el
     perds, revoca la clau i crea'n una de nova.
   - Anota el **Key ID** que es mostra en aquesta pàgina (10 caràcters, p. ex. `A1B2C3D4E5`).
5. **Troba el teu Team ID**, a dalt a la dreta de la pàgina del compte d'Apple Developer, sota el
   teu nom / a **Membership details**. 10 caràcters, p. ex. `9XYZ8ABCDE`.

Ara tens:

| Camp de memship | Valor d'Apple | Exemple |
| ------------- | ----------- | ------- |
| ID de client | l'identificador del **Services ID** | `org.myclub.memship.web` |
| ID d'equip | Membership details → Team ID | `9XYZ8ABCDE` |
| ID de clau | la clau que has creat | `A1B2C3D4E5` |
| Clau privada (.p8) | **tot el contingut** del fitxer descarregat | `-----BEGIN PRIVATE KEY-----…` |

Per a la clau privada, obre el fitxer `.p8` amb un editor de text pla i copia-ho tot, incloses
les línies `-----BEGIN PRIVATE KEY-----` i `-----END PRIVATE KEY-----`.

### 3.5 Omplir la pantalla

Per a cada targeta de proveïdor:

1. Enganxa els camps no secrets (ID de client i, per a Apple, també ID d'equip i ID de clau).
2. Enganxa el camp secret (secret de client de Google / clau privada d'Apple). És una casella de
   tipus contrasenya; es manté emmascarada.
3. Prem **Desar**.
4. **Activa l'interruptor** del proveïdor. L'interruptor està desactivat fins que tots els camps
   d'aquell proveïdor estan plens: desar credencials mai no activa un proveïdor per si sol, així
   que tu decideixes quan entra en funcionament.
5. Torna a prémer **Desar**. La insígnia de la targeta canvia a **Actiu**.

Obre la pàgina d'inici de sessió en una finestra privada i comprova que el botó hi és i que
completa un inici de sessió.

Altres marques que pots veure:

- **"de l'entorn"** al costat d'una etiqueta, aquest valor ara mateix ve del fitxer `.env` de la
  instal·lació, no del que has escrit aquí. Escriure un valor a la pantalla el substitueix per a
  aquell camp. Mira la [secció 6](#6-alternativa-amb-el-fitxer-de-configuració-env).
- **"desat"** al costat d'una etiqueta de secret, hi ha un secret desat per a aquell camp.

### 3.6 Resolució de problemes de l'SSO

| Símptoma | Causa i solució |
| ------- | ------------- |
| Google: `Error 400: redirect_uri_mismatch` | La URI de redirecció de la consola de Google és diferent de la de la pantalla de memship. Torna-la a copiar amb el botó de copiar; comprova `https` vs `http`, `www` i la barra final. |
| Google: "Access blocked: this app has not completed the verification process" | La pantalla de consentiment encara és a *Testing*. Publica-la, o afegeix la persona com a usuari de prova. |
| Google: `invalid_client` | L'ID de client i el secret de client no pertanyen al mateix client OAuth, o el secret s'ha retallat en enganxar-lo. Torna a copiar tots dos. |
| Apple: `invalid_client` | Gairebé sempre és una d'aquestes: s'ha fet servir l'App ID en lloc del **Services ID**; un Team ID o Key ID incorrecte; un `.p8` enganxat només en part. Revisa els quatre valors. |
| Apple: "Invalid redirect_uri" / no es pot desar el Services ID | La Return URL ha de ser `https`, exactament al domini indicat a *Domains and Subdomains*, i no pot ser una adreça IP ni `localhost`. |
| L'inici de sessió amb Apple torna a la pàgina d'inici de sessió amb un error | La crida de retorn d'Apple és un POST entre llocs i requereix que el lloc se serveixi per HTTPS. Apple no funciona contra una instal·lació de desenvolupament. |
| El nom d'un soci queda buit després d'iniciar sessió amb Apple | Apple envia el nom **només la primera vegada** que la persona autoritza la teva aplicació. Si estaves fent proves, elimina la teva aplicació d'*Apple ID → Sign in with Apple* al compte i torna-ho a provar; és el comportament normal i no fa cap mal. |
| Un usuari d'Apple té una adreça com `abc123@privaterelay.appleid.com` | La persona ha triat "Hide My Email". El correu enviat a aquesta adreça Apple li reenvia. Desa-la tal qual. |
| El botó del proveïdor no apareix a la pàgina d'inici de sessió | El proveïdor no està activat, falta un camp obligatori o les credencials s'han desat però l'interruptor no s'ha activat mai. En aquest cas, la insígnia de la targeta mostra **Inactiu**. |
| Una persona inicia sessió amb un proveïdor i arriba a una pantalla *Pendent d'aprovació* | És l'esperat per als registres nous. Aprova-la des de la llista d'altes pendents dels socis. |
| Algú amb un compte amb contrasenya existent ha iniciat sessió amb Google i ha obtingut un compte **nou** en lloc de l'antic | El proveïdor ha informat que el correu no estava verificat, així que memship s'ha negat a vincular-lo (vincular una adreça no verificada permetria a qualsevol apropiar-se d'un compte). Fes que verifiquin l'adreça amb el proveïdor. |

---

## 4. Correu

**Configuració → Integracions → Correu**

### 4.1 Com funciona

memship envia correus per a la verificació del registre, els avisos d'aprovació/rebuig, el
restabliment de contrasenyes, els rebuts, els recordatoris de pagament i les comunicacions als
socis. Tot passa per **un sol** proveïdor, que tries aquí.

S'admeten dos proveïdors:

- **Resend**, un servei d'enviament gestionat, que es fa servir a través de la seva API. Millor
  entregabilitat, més volum, necessita un domini que controlis.
- **Servidor SMTP**, qualsevol servidor de correu que accepti SMTP: l'allotjament de correu que la
  teva entitat ja paga, un servei d'enviament o un compte de Gmail. No t'has de registrar enlloc
  si ja tens allotjament de correu.

**Hi ha exactament un proveïdor actiu alhora.** La pantalla té un sol selector de *Proveïdor
actiu* amb tres posicions, **Cap / Resend / Servidor SMTP**. No hi ha interruptors per proveïdor,
així que l'estat "tots dos activats" no es pot donar. Pots tenir desades les credencials de tots
dos i canviar d'un a l'altre en qualsevol moment.

Amb el proveïdor actiu a **Cap**, memship no envia absolutament res. Els correus s'ometen sense
avís (queden registrats al log, no en cua per a més tard). Els socis no rebran enllaços de
verificació, avisos d'aprovació ni rebuts, així que tracta *Cap* com un estat temporal.

### 4.2 Resend: obtenir les credencials

Necessites una **clau d'API** i, idealment, un **correu del remitent** en un domini que hagis
verificat.

1. Crea un compte a **[resend.com](https://resend.com)**.
2. **Domains → Add domain**, introdueix el domini des del qual envies (p. ex. `myclub.org`).
   Resend mostra un conjunt de registres DNS (normalment DKIM més una entrada SPF/MX per a un
   subdomini `send.`).
3. Afegeix aquests registres al teu proveïdor de DNS (qui gestioni el teu domini) i després prem
   **Verify**. La propagació sol trigar minuts, de vegades hores.
4. **API Keys → Create API Key**.
   - Name: `memship`.
   - Permission: amb **Sending access** n'hi ha prou.
   - Domain: el que acabes de verificar (o *All domains*).
   - Copia la clau: comença per `re_` i es mostra **només un cop**.
5. Decideix el teu **correu del remitent**, p. ex. `no-reply@myclub.org`. Ha de ser d'un domini
   verificat; Resend rebutja qualsevol altre.

> Només estàs fent proves? Resend et deixa enviar des de `onboarding@resend.dev` sense cap domini,
> però només a l'adreça de correu propietària del compte de Resend. Serveix per a un enviament de
> prova, no per a l'ús real.

### 4.3 SMTP: les dades del teu servidor, o Gmail

**El teu propi servidor de correu.** Qui et proporciona l'allotjament de correu publica aquests
valors, normalment sota un títol com *SMTP*, *correu sortint* o *configuració del client de
correu*:

- **Servidor**, p. ex. `mail.myclub.org` o `smtp.yourprovider.com`.
- **Port**, `587` en gairebé tots els casos.
- **Xifratge**, *STARTTLS*. Deixa l'interruptor activat tret que el proveïdor digui que el
  servidor no està xifrat.
- **Usuari i contrasenya**, normalment l'adreça completa d'una bústia i la seva contrasenya.
  Alguns proveïdors donen una contrasenya SMTP a part; si és així, fes servir aquesta. Un relay
  que accepta correu des de l'adreça del teu servidor no necessita cap de les dues: deixa-les
  totes dues en blanc.
- **Correu del remitent**, l'adreça que veuen els socis. La majoria de servidors només accepten
  l'adreça d'una bústia que sigui teva; deixa-ho en blanc per enviar com l'usuari.

**Xifratge** tria com es protegeix la connexió: **STARTTLS**, normalment al port 587, que millora
una connexió en clar; **SSL/TLS directe**, normalment al port 465, xifrat des del primer byte; o
**sense xifratge**, per a un servidor de la teva xarxa. Posa-ho com ho documenti el teu proveïdor
per al port que facis servir. Gairebé tots els proveïdors que ofereixen el 465 també ofereixen el
587, i el 587 continua sent el valor per defecte.

**Gmail.** Prem **Fer servir la configuració de Gmail** a la targeta: omple `smtp.gmail.com`, el
port `587` i STARTTLS. L'usuari és l'**adreça de Gmail**, i la contrasenya és una **contrasenya
d'aplicació** de Google, una contrasenya de 16 caràcters generada per a una sola aplicació. La
contrasenya normal del compte no funcionarà; Google la bloqueja.

1. El compte ha de tenir la **verificació en 2 passos activada amb un número de telèfon o una
   aplicació d'autenticació**: [myaccount.google.com/security](https://myaccount.google.com/security)
   → *2-Step Verification*. Sense això, les contrasenyes d'aplicació no existeixen.
   - **Una passkey o una clau de seguretat soles no n'hi ha prou.** Google indica que la
     verificació en 2 passos està activada, però la pàgina de contrasenyes d'aplicació continua
     sense estar disponible. Afegeix un segon mètode, un número de telèfon (SMS/veu) o Google
     Authenticator, al costat de la passkey; pots conservar la passkey.
   - La via de Gmail **no està disponible en absolut**, sense cap alternativa, quan el compte està
     inscrit a la **Protecció avançada**, o quan és un **compte de feina, d'escola o d'una altra
     organització** l'administrador del qual no permet contrasenyes d'aplicació. Fes servir
     Resend, el teu propi servidor de correu o un altre compte de Google.
2. Ves a **[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)**.
3. Posa un nom a l'aplicació (p. ex. `memship`) i crea-la.
4. Google mostra una contrasenya de 16 caràcters com ara `abcd efgh ijkl mnop`. Copia-la: com tots
   els secrets d'aquí, només es mostra un cop. Els espais són estètics; funciona amb ells o sense.

Coses a saber sobre la via de Gmail:

- **Límits d'enviament:** aproximadament 500 missatges al dia per a un compte gratuït de Gmail,
  ~2.000 per a Google Workspace. Superar-los fa que es bloquegi temporalment l'enviament del
  compte. Un club amb uns quants centenars de socis que faci una comunicació massiva hi pot
  arribar.
- Gmail **reescriu el correu del remitent** amb l'adreça del mateix compte, tret que l'adreça
  alternativa estigui registrada en aquell compte de Gmail ("Send mail as"). Per tant, el camp
  *Correu del remitent* és millor deixar-lo en blanc, i en aquest cas es fa servir l'adreça de
  Gmail.
- En un compte de feina, d'escola o de Google Workspace, les contrasenyes d'aplicació només
  existeixen si l'administrador d'aquella organització les permet. Si no, aquesta via no està
  disponible per a aquell compte, mira el pas 1.

### 4.4 Omplir la pantalla, provar i activar

Ordre recomanat: configurar, **provar** i després activar:

1. Omple la targeta del proveïdor:
   - **Resend**: *Clau d'API* (secret) i *Correu del remitent*.
   - **Servidor SMTP**: *Servidor*, *Port*, l'interruptor *STARTTLS*, *Usuari SMTP*,
     *Contrasenya* (secret) i *Correu del remitent*, o prem primer **Fer servir la configuració
     de Gmail** i després afegeix l'adreça de Gmail i la contrasenya d'aplicació. Són obligatoris
     el servidor i un remitent (un usuari o un correu del remitent).
2. Prem **Desar**. La insígnia de la targeta passa a **A punt**.
3. Prem **Envia una prova** en aquesta targeta. S'envia un missatge de prova **específicament a
   través d'aquest proveïdor**, encara que no sigui l'actiu: aquesta és tota la gràcia del botó,
   verificar les credencials abans de passar-hi el trànsit real. Va a la teva pròpia adreça (el
   correu del superadministrador que ha iniciat sessió).
   - Èxit → una confirmació "Correu de prova enviat". Mira la safata d'entrada, i la carpeta de
     correu brossa.
   - Error → l'error del proveïdor es mostra al missatge (un error d'autenticació SMTP, un rebuig
     de Resend, etc.).
   - El botó està desactivat mentre tens canvis sense desar ("Desa els canvis abans d'enviar la
     prova") o mentre falten camps obligatoris.
4. Quan arribi la prova, posa el selector **Proveïdor actiu** en aquest proveïdor i prem
   **Desar**. La insígnia passa a **Actiu**.

L'ordre s'imposa, no és només una recomanació. El selector de *Proveïdor actiu* mostra un
proveïdor en gris, i n'explica el motiu en passar-hi el ratolí, en tres casos:

- **Falten camps obligatoris**, "Emplena les credencials abans d'activar-lo".
- **Els seus camps tenen canvis sense desar**, "Desa i prova les noves credencials abans
  d'activar-lo". Una prova només demostra les credencials desades, així que les noves s'han de
  desar i provar primer.
- **Cap enviament no ha funcionat amb les credencials actuals**, "Envia una prova correcta abans
  d'activar-lo". La prova ha de ser l'enviament més recent, i també compta un correu real que
  hagi sortit bé. Si l'últim enviament ha fallat, el proveïdor continua en gris fins que una
  prova torni a funcionar.

El proveïdor que ja està actiu mai no es mostra en gris per aquest motiu. Desar altres canvis no
el desactiva, encara que no s'hagi provat mai. Posar el selector a **Cap** sempre és possible.

Un cop una targeta té les credencials, una línia sota la capçalera indica si se sap que
funcionen. Cada correu enviat a través d'aquest proveïdor l'actualitza: la prova, i també cada
missatge real.

- **Sense verificar** (ambre), encara no s'ha enviat res amb aquestes credencials. Substituir
  una clau o una contrasenya, o canviar-la a `.env`, torna la targeta a aquest estat, perquè el
  resultat anterior era per a unes altres credencials.
- **Funciona** (verd), el proveïdor ha acceptat el correu més recent, amb la data.
- **Falla** (vermell), el proveïdor ha rebutjat el correu més recent, amb la data i un motiu
  breu (credencials rebutjades, proveïdor inaccessible, límit d'enviament assolit…). **Envia una
  prova** mostra el missatge d'error complet del proveïdor.

*Funciona* vol dir que el proveïdor ha acceptat el missatge. No vol dir que el missatge hagi
arribat a la safata d'entrada: un rebot o la carpeta de correu brossa passen després, així que
per a això consulta el registre del mateix proveïdor.

Canviar de proveïdor més endavant és qüestió de dos clics: selecciona l'altre proveïdor i desa.
Les credencials del que deixes es conserven, així que pots tornar-hi, un cop tornin a superar una
prova, si han canviat des d'aleshores.

### 4.5 Resolució de problemes del correu

| Símptoma | Causa i solució |
| ------- | ------------- |
| La prova falla amb un error d'autenticació SMTP (`535`, "Username and Password not accepted") | L'usuari o la contrasenya són incorrectes. A Gmail: la contrasenya d'aplicació és incorrecta, s'ha revocat o s'ha desactivat la verificació en 2 passos (cosa que invalida totes les contrasenyes d'aplicació); genera'n una de nova. Al teu propi servidor: comprova si el proveïdor dona una contrasenya SMTP a part. |
| La prova falla: connexió rebutjada, temps d'espera esgotat o la connexió es talla de seguida | Servidor o port incorrectes, o **Xifratge** no concorda amb el port: el 465 necessita SSL/TLS directe i el 587 necessita STARTTLS. Algunes xarxes d'allotjament també bloquegen l'SMTP de sortida; pregunta-ho a l'administrador del servidor. |
| [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) diu *"The setting that you are looking for is not available for your account."* | No es pot crear cap contrasenya d'aplicació per a aquest compte. O bé la verificació en 2 passos només està configurada amb passkeys/claus de seguretat (afegeix un número de telèfon o una aplicació d'autenticació i recarrega la pàgina), o bé el compte té la Protecció avançada, o bé és un compte de feina/escola l'administrador del qual bloqueja les contrasenyes d'aplicació (sense alternativa, fes servir Resend o un altre compte). Mira el pas 1 de la 4.3. |
| La prova falla: Resend "domain is not verified" / 403 | El correu del remitent no és d'un domini verificat a Resend, o els registres DNS no s'han propagat. Comprova *Domains* a Resend. |
| La prova falla: Resend 401 / "API key is invalid" | Clau mal escrita, revocada o creada sense permís d'enviament. Crea una clau nova. |
| La prova indica èxit però no arriba res | Mira el correu brossa. Per a Resend, consulta el registre *Emails* del seu tauler per si hi ha un rebot. Per a Gmail, mira la carpeta *Enviats* del compte que envia. |
| No s'envia res de res, sense errors enlloc | El proveïdor actiu és **Cap**. Selecciona un proveïdor i desa. |
| Els socis deixen de rebre correu després d'un període en què funcionava | S'ha arribat al límit diari de Gmail o s'ha revocat la contrasenya d'aplicació; a Resend, un domini suspès. La targeta del proveïdor passa a **Falla** i dona un motiu breu. Fes servir **Envia una prova** per veure l'error real. |
| L'etiqueta diu "de l'entorn" | Aquest valor ve del fitxer `.env` de la instal·lació. Funciona, però el que escriguis a la pantalla té prioritat per a aquell camp. |
| Els correus arriben des d'una adreça que no has configurat | Gmail ha reescrit el remitent amb l'adreça del compte (és l'esperat), el teu servidor només permet enviar com la bústia amb què has iniciat sessió, o encara el proporciona un valor del fitxer d'entorn. |

---

## 5. Opcions de registre que acompanyen aquestes integracions

Dues opcions a nivell d'organització regeixen el flux d'alta que alimenta l'SSO. **No són a la
pantalla d'Integracions**, encara no tenen interfície, i viuen a l'objecte `features` de la
configuració de l'organització. Totes dues valen **true** per defecte, que és la configuració
normal:

| Opció | Per defecte | Efecte |
| ------ | ------- | ------ |
| `public_registration` | `true` | Si algú es pot registrar, ja sigui amb el formulari o amb un proveïdor. Posa-la a `false` per a un club tancat on els socis els crea un administrador. Si està desactivada, la pàgina de registre i els botons de proveïdor per a persones *noves* es rebutgen. |
| `registration_requires_approval` | `true` | Si un registre nou espera en *pendent* que un administrador l'aprovi. Posa-la a `false` i un registre nou es converteix en soci actiu immediatament (amb el número de soci assignat a l'acte), sense passar per la cua d'aprovació. |

Canviar-les requereix una crida a l'API de configuració (`PUT /api/v1/settings/`,
superadministrador) amb l'objecte `features`, o una actualització directa de la fila
`organization_settings`. Demana-ho a qui administri la teva instal·lació si necessites canviar-ne
alguna.

Relacionat, i independent del que hi ha a dalt: els enllaços de **verificació** del correu
s'envien sempre, i apunten a `FRONTEND_URL`. Si els enllaços de verificació dels teus correus són
incorrectes (p. ex. `localhost`), aquesta variable està mal configurada a la teva instal·lació.

---

## 6. Alternativa amb el fitxer de configuració (`.env`)

Tot el que hi ha a la pantalla d'Integracions també es pot proporcionar a través del fitxer
`.env` de la instal·lació. Això existeix per dos motius: les instal·lacions configurades abans
que existissin aquestes pantalles continuen funcionant sense tocar res, i un operador pot
precarregar credencials en el moment del desplegament.

**La prioritat és per camp: el que desis a la pantalla guanya; si un camp hi és buit, es fa
servir la variable d'entorn.** La insígnia **"de l'entorn"** t'indica exactament quins camps
vénen ara mateix del fitxer. Esborrar un camp a la pantalla fa que torni a fer servir el valor
de l'entorn, si n'hi ha.

| Camp de la pantalla | Variable d'entorn |
| ------------ | -------------------- |
| Google → ID de client | `GOOGLE_CLIENT_ID` |
| Google → Secret de client | `GOOGLE_CLIENT_SECRET` |
| Apple → ID de client (Services ID) | `APPLE_CLIENT_ID` |
| Apple → ID d'equip | `APPLE_TEAM_ID` |
| Apple → ID de clau | `APPLE_KEY_ID` |
| Apple → Clau privada (.p8) | `APPLE_PRIVATE_KEY` |
| Resend → Clau d'API | `RESEND_API_KEY` |
| Resend → Correu del remitent | `RESEND_FROM_EMAIL`, després `SMTP_FROM` |
| Servidor SMTP → Servidor | `SMTP_HOST` |
| Servidor SMTP → Port | `SMTP_PORT` |
| Servidor SMTP → Xifratge | `SMTP_SECURITY` i, si no, l'obsoleta `SMTP_TLS` |
| Servidor SMTP → Usuari SMTP | `SMTP_USER` |
| Servidor SMTP → Contrasenya | `SMTP_PASSWORD` |
| Servidor SMTP → Correu del remitent | `SMTP_FROM` |
| URL del backend (només lectura) | `BACKEND_PUBLIC_URL` |
| _(cap camp)_ (clau de xifratge dels secrets) | `MEMSHIP_SECRET_KEY`, `SECRETS_KEY_FILE` |

Notes:

- `BACKEND_PUBLIC_URL` és **només d'entorn** per disseny: descriu com està publicat el teu
  servidor. Ha de ser correcta, perquè les URI de redirecció se'n deriven.
- `MEMSHIP_SECRET_KEY` només cal definir-la si vols proporcionar tu mateix la clau de xifratge en
  lloc de deixar que la generi el servidor. `SECRETS_KEY_FILE` tria on s'escriu la clau generada;
  ha de ser en un volum **persistent**.
- En una instal·lació que no ha fet servir mai aquestes pantalles, el correu continua comportant-se
  exactament com abans: Resend si `RESEND_API_KEY` està definida, si no, SMTP si `SMTP_HOST` està
  definida. Tan bon punt desis qualsevol cosa a la pantalla de Correu, passa a manar la selecció
  explícita de *Proveïdor actiu*.

---

## 7. Referència de camps

### Inici de sessió (SSO)

| Proveïdor | Camp | Secret | D'on surt | Exemple |
| -------- | ----- | ------ | ------------------- | ------- |
| Google | ID de client | no | Cloud Console → Credentials → OAuth client | `1234-abc.apps.googleusercontent.com` |
| Google | Secret de client | **sí** | la mateixa pantalla | `GOCSPX-…` |
| Apple | ID de client | no | Developer → Identifiers → **Services ID** | `org.myclub.memship.web` |
| Apple | ID d'equip | no | Developer → Membership details | `9XYZ8ABCDE` |
| Apple | ID de clau | no | Developer → Keys → la teva clau | `A1B2C3D4E5` |
| Apple | Clau privada (.p8) | **sí** | el contingut del fitxer de clau descarregat | `-----BEGIN PRIVATE KEY-----…` |

Tots els camps d'un proveïdor són obligatoris abans que es pugui activar.

### Correu

| Proveïdor | Camp | Secret | Obligatori | Notes |
| -------- | ----- | ------ | -------- | ----- |
| Resend | Clau d'API | **sí** | sí | Comença per `re_`; es mostra un cop, en crear-la. |
| Resend | Correu del remitent | no | no | Ha de ser d'un domini verificat a Resend. |
| Servidor SMTP | Servidor | no | sí | p. ex. `mail.myclub.org`; `smtp.gmail.com` per a Gmail. |
| Servidor SMTP | Port | no | no | Per defecte, `587`. Fes servir el `465` amb SSL/TLS directe. |
| Servidor SMTP | STARTTLS | no | no | Activat per defecte. |
| Servidor SMTP | Usuari SMTP | no | mira les notes | Normalment l'adreça d'una bústia; per a Gmail, l'adreça de Gmail. |
| Servidor SMTP | Contrasenya | **sí** | no | Per a Gmail, una contrasenya d'aplicació de 16 caràcters, no la contrasenya del compte. |
| Servidor SMTP | Correu del remitent | no | mira les notes | Deixa-ho en blanc per enviar com l'usuari. |

Un servidor SMTP necessita un remitent: un usuari o un correu del remitent. **Fer servir la
configuració de Gmail** omple el servidor, el port i STARTTLS per a un compte de Gmail.

---

## Llista de comprovació ràpida

**Inici de sessió amb Google**
- [ ] La URL del backend de la pantalla és la teva adreça pública real
- [ ] URI de redirecció copiada de memship a la consola de Google, exactament
- [ ] Pantalla de consentiment publicada
- [ ] ID de client + secret desats, interruptor activat, la insígnia diu **Actiu**
- [ ] El botó apareix a la pàgina d'inici de sessió i un inici de sessió es completa

**Inici de sessió amb Apple**
- [ ] Domini HTTPS en producció (no localhost)
- [ ] App ID amb *Sign in with Apple* activat
- [ ] Services ID creat, domini + return URL configurats, **el Services ID és l'ID de client**
- [ ] Clau creada, `.p8` descarregat i guardat en un lloc segur, Key ID anotat
- [ ] Team ID anotat; els quatre camps desats, interruptor activat, la insígnia diu **Actiu**

**Correu**
- [ ] Credencials del proveïdor desades, la insígnia diu **A punt**
- [ ] **Envia una prova** ha funcionat i el missatge ha arribat de debò
- [ ] Selector de proveïdor actiu posat en aquest proveïdor i desat, la insígnia diu **Actiu**
- [ ] L'avís de xifratge és verd
- [ ] El fitxer de clau i la base de dades tenen còpia de seguretat conjunta
