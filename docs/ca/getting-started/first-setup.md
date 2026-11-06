<!-- source: en/getting-started/first-setup.md -->
<!-- source-hash: 8d263d302d8b -->

# Configuració inicial

> **En anglès:** [First-time setup](../../en/getting-started/first-setup.md).

Després d'[instal·lar](../../en/getting-started/installation.md) _(en anglès)_ Memship i engegar
els serveis, executa l'ordre de posada en marxa per crear el teu compte i configurar l'entitat. És
la mateixa ordre a tots els entorns, i és interactiva:

```bash
docker compose exec -it api python -m app.cli.seed
```

Fixa't en el `-it`: l'ordre fa preguntes, així que necessita un terminal connectat.

## Les tres preguntes

La posada en marxa fa tres preguntes independents, de manera que una sola ordre cobreix totes les
situacions.

### 1. Superadministrador

El compte propietari de la instància. Tu tries l'adreça i la contrasenya, no hi ha res predefinit,
i no existeixen credencials per a aquest compte enlloc d'aquest repositori.

Si ja existeix un superadministrador, la posada en marxa ofereix restablir-ne la contrasenya. Així
és com torna a entrar un operador que s'ha quedat fora, mira
[Recuperar la contrasenya del superadministrador](#recuperar-la-contrasenya-del-superadministrador).

### 2. Dades del club

Només s'ofereix quan la instància ja conté dades del club, cosa que en una instal·lació nova no
passa. Respondre *yes* esborra tots els socis, activitats, rebuts, mandats i la mateixa entitat,
després de mostrar-te el nombre de files i demanar-te que escriguis el nom de l'entitat per
confirmar-ho.

**Conserva** els comptes de superadministrador, els rols del sistema i els proveïdors de pagament
que tinguis configurats. Això últim és el motiu per fer servir aquesta opció en lloc d'esborrar el
volum de la base de dades: les credencials dels proveïdors viuen a la base de dades, xifrades, no
al `.env`, així que esborrar el volum vol dir tornar a introduir tots els secrets.

Així és com converteixes una instància que has avaluat amb dades de demostració en la de debò.

### 3. Configuració del club

O bé introdueixes les dades reals de l'entitat, o bé generes un club de demostració.

Per a un desplegament real, tria **1) real details**. Només el nom és obligatori; tot el que
deixis en blanc queda en blanc i es pot omplir més endavant des de **Configuració**. No s'inventa
res: una instància configurada així comença sense NIF i sense IBAN, en lloc d'amb valors de
farciment versemblants que hauries de detectar i corregir.

Tria **2) demo club** només per avaluar o per a una demostració que estiguis preparant. Genera un
any de dades d'exemple, més accessos per a un administrador del club i dos socis, les contrasenyes
generades dels quals es mostren una sola vegada al final de l'execució.

## Els tres rols

| Rol             | Què pot fer                                                               |
|-----------------|---------------------------------------------------------------------------|
| **Superadministrador** | És el propietari de la instància: rols, credencials, camps personalitzats, proveïdors de pagament. |
| **Administrador del club** | Porta el dia a dia de l'entitat: socis, activitats, facturació, comunicacions. |
| **Soci**        | Fa servir el portal del soci: perfil, activitats, pagaments, carnet, reserves. |

Els rols més restringits (un tresorer que només veu la facturació, per exemple) els crea el
superadministrador des de **Configuració → Rols**. Mira
[Rols i permisos](../reference/roles-and-permissions.md).

### Un segon superadministrador

Un sol superadministrador és un punt únic de fallada: si aquella persona se'n va, l'única manera de
tornar a entrar és l'accés al shell del servidor. Promou-ne un segon aviat.

Ho fa un superadministrador des de **Configuració → Comptes**: tria el compte i marca **Super
Admin**. Només un superadministrador veu aquesta casella activada; per a qualsevol altra persona
està desactivada i marcada com a exclusiva del superadministrador, perquè un compte no pot atorgar
un rol que no té. Memship també es nega a retirar l'últim superadministrador, així que no pots
deixar la instància sense accés degradant-te a tu mateix.

Primer cal que el compte existeixi. Avui això vol dir que la persona s'ha registrat ella mateixa
(quan el registre públic està activat) o que l'ha creada l'ordre de posada en marxa: encara no hi
ha cap flux de "convidar un usuari" des de l'administració.

## Recuperar la contrasenya del superadministrador

**Només des de la màquina, amb `python -m app.cli.seed`.** El flux de contrasenya oblidada del
navegador rebutja deliberadament els superadministradors: aquest compte té els permisos de rols i
credencials, així que permetre que una bústia de correu el restableixi faria que tenir accés a la
bústia equivalgués a ser el propietari de la instància. A més, no funcionaria a la majoria
d'instal·lacions: una de nova no té SMTP configurat, que és exactament quan necessites recuperar
l'accés.

La petició retorna la mateixa resposta "si el correu existeix…" que dona per a una adreça
desconeguda, així que la pàgina d'inici de sessió no revela mai quins comptes són de
superadministrador. No arriba res per correu.

En lloc d'això, a la màquina on s'executen els contenidors:

```bash
docker compose exec -it api python -m app.cli.seed
```

Respon **yes** a "Reset the password for one of them?", indica l'adreça i escriu la contrasenya
nova dues vegades. Respon *no* a la pregunta de les dades del club i tria **3) Skip for now** a la
configuració del club: un restabliment no canvia res més.

Sense intervenció, per a una recuperació amb script:

```bash
MEMSHIP_ADMIN_PASSWORD='...' docker compose exec -T -e MEMSHIP_ADMIN_PASSWORD api \
  python -m app.cli.seed --admin-email you@example.org
```

Cada restabliment s'escriu al registre d'auditoria com una actualització del compte, sense usuari
que l'executi: qui l'ha fet tenia accés al shell de la màquina, i el registre no el pot
identificar. Si en trobes un que no has fet tu, tracta'l com qualsevol altre accés de root sense
explicació.

Els socis i els administradors del club no es veuen afectats: fan servir el flux normal de
contrasenya oblidada, que necessita que l'[enviament de correu](../self-hosting/email.md)
funcioni.

## Posada en marxa sense intervenció

Per a desplegaments automatitzats, els mateixos tres passos prenen opcions en lloc de preguntes.
La contrasenya es llegeix de l'entorn, mai de la línia d'ordres, on acabaria a l'historial del
shell i a `ps`:

```bash
MEMSHIP_ADMIN_PASSWORD='...' docker compose exec -T -e MEMSHIP_ADMIN_PASSWORD api \
  python -m app.cli.seed --admin-email you@example.org --club-name "Your Club"
```

**El `-e MEMSHIP_ADMIN_PASSWORD` no és opcional.** `docker compose exec` no passa l'entorn del
shell que el crida al contenidor, així que sense ell la variable està definida a la teva màquina i
sense definir on s'executa l'ordre, i la posada en marxa s'atura amb
`--admin-email needs the password in MEMSHIP_ADMIN_PASSWORD`. Posar el nom de la variable després
de `-e`, sense `=value`, és el que la passa sense posar la contrasenya a la sortida de `ps`.

| Opció | Efecte |
|------|--------|
| `--admin-email EMAIL` | Crea el superadministrador, o en restableix la contrasenya si ja existeix. Requereix `MEMSHIP_ADMIN_PASSWORD`. Rebutja una adreça que ja pertany a un compte que *no* és de superadministrador, en lloc de restablir la contrasenya d'un desconegut. |
| `--reset-club-data` | Esborra totes les dades del club. Sense demanar confirmació: és la petició explícita. |
| `--club-name NAME` | Crea l'entitat amb aquest nom. |
| `--demo` | Genera el club de demostració i les seves dades d'exemple. |

## Iniciar sessió

Obre l'URL del teu Memship i entra com el superadministrador que acabes de crear. L'autenticació
és amb **correu + contrasenya**.

## 3. Configura l'entitat

Des del tauler d'administració, ves a **Configuració** i completa:

- **Imatge de marca**, nom de l'entitat, color de marca i logotip.
- **Adreça**, que es fa servir als rebuts i als documents legals.
- **Banca**, IBAN/BIC, necessari per a la domiciliació SEPA.
- **Facturació**, prefix del número de factura, tipus d'IVA per defecte i reinici anual opcional
  (p. ex. `FAC-2026-0001`).
- **Idioma per defecte**, castellà, català o anglès.

## 4. Comprova l'enviament de correu

La confirmació d'adreces, el restabliment de contrasenyes i les notificacions de pagament depenen
que el correu estigui configurat. Configura l'[enviament de correu](../self-hosting/email.md) i
envia una prova abans d'incorporar socis reals: llança un restabliment de contrasenya des d'un
compte de **soci o d'administrador del club**, ja que el flux rebutja els superadministradors i
semblaria una fallada de l'enviament.

Fes-ho abans d'obrir l'autoregistre: fins que no hi hagi un proveïdor configurat, els registres es
rebutgen, perquè l'enllaç de confirmació del qual depenen no es pot enviar. Mira
[Els socis no poden entrar abans que el correu funcioni](../self-hosting/email.md#els-socis-no-poden-entrar-fins-que-funcioni-el-correu).

## Passos següents

- [Guia de l'administrador → Introducció](../admin-guide/overview.md), com està organitzat el
  tauler d'administració.
- [Còpies de seguretat i restauració](../self-hosting/backups-and-restore.md), configura-les abans
  de posar-te en marxa.
