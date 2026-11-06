<!-- source: en/development/local-environment.md -->
<!-- source-hash: 2cf76cf56eb5 -->

# Entorn de desenvolupament local

El backend s'executa a Docker (API, worker i beat de Celery, PostgreSQL, Redis); el frontend
s'executa en local amb pnpm, així que tens el hot reload de Next.js sense cap contenidor pel mig.

> **En anglès:** [Local development environment](../../en/development/local-environment.md).

`scripts/dev.sh` ho governa tot.

## Requisits previs

| Eina | Per a què |
|---|---|
| Docker Engine + plugin de Compose | Tot el backend: API, base de dades, Redis, worker, beat, migracions i la bateria de tests |
| **Node 22** i **pnpm** | El servidor de desenvolupament del frontend |

Aquesta és la llista completa. **El backend no s'executa mai a l'amfitrió**: cap `uv sync`, cap
virtualenv, cap versió de Python per quadrar, així que el mateix checkout es comporta igual a
qualsevol màquina amb Docker. `backend/app`, `backend/tests` i `backend/alembic` es munten amb bind
mount dins dels contenidors: els edites al teu editor i el codi en execució canvia. L'API es
reinicia sola quan canvia alguna cosa sota `backend/app` (el reloader d'uvicorn, només amb
`APP_ENV=development`; mira `dev.sh logs backend` per veure "Reloading..."). El worker i el beat
no, reinicia'ls després d'editar una tasca. El contenidor és on s'executa el codi, no on viu.

Només el frontend es queda a l'amfitrió, i a propòsit: el servidor de desenvolupament de Next.js
hi és pel hot reload, que és l'única cosa que un contenidor no fa tan bé. Cypress necessita un
navegador real, així que la bateria e2e també és a l'amfitrió.

La versió major de Node està fixada a `frontend/.nvmrc` i `engines` a `frontend/package.json`
l'imposa en forma d'avís. **Fes servir la 22**: és la que executa la CI i sobre la qual es
construeix la imatge de producció, i una versió major diferent és el tipus de diferència que
només apareix com una compilació que funciona en una màquina i no en una altra. Amb `nvm`:

```bash
cd frontend
nvm install       # reads .nvmrc; `nvm use` on its own only switches to an already-installed major
corepack enable   # re-run this after every version switch, see below
```

Si no coincideix, imprimeix `WARN Unsupported engine` i continua, i això és deliberat: t'ho ha de
dir, no aturar-te a mitja sessió. `pnpm install --engine-strict` converteix la mateixa comprovació
en una fallada si mai vols que s'imposi.

La versió de pnpm està fixada per `packageManager` al mateix fitxer, així que `corepack enable` et
dona la correcta sense haver-la d'instal·lar tu.

> **Els shims de corepack viuen dins de cada instal·lació de Node**, així que canviar de versió
> major també canvia pnpm. Si arribes a la 22 des d'una altra versió, `./scripts/dev.sh start all`
> aixeca el backend i després falla el frontend amb `pnpm: command not found` a
> `frontend/logs/dev-server.log`. Executar `corepack enable` una vegada amb la nova versió major ho
> arregla per sempre.

> **No necessites Node per a res si només vols executar memship.** El frontend es distribueix com
> a contenidor, i el [Quick start](../../en/getting-started/quickstart.md) _(en anglès)_ executa
> tota l'aplicació a partir d'imatges publicades amb una sola ordre. Instal·la les eines quan
> vulguis *treballar en* el frontend: el servidor de desenvolupament local existeix pel hot
> reload, que és l'única cosa que un contenidor no pot fer tan bé.

## Arrencar

```bash
./scripts/dev.sh start all      # backend in Docker + frontend locally
./scripts/dev.sh status         # what is up
./scripts/dev.sh stop all       # stop everything
```

## Ordres

| Ordre | Descripció |
|---------|-------------|
| `./scripts/dev.sh start all` | Arrenca el backend (Docker) + el frontend (local) |
| `./scripts/dev.sh start backend` | Arrenca només el backend: API, BD, Redis, worker, beat |
| `./scripts/dev.sh start frontend` | Arrenca només el servidor de desenvolupament de Next.js |
| `./scripts/dev.sh stop all` | Atura tots els serveis |
| `./scripts/dev.sh restart all` | Reinicia tots els serveis |
| `./scripts/dev.sh status` | Estat de cada servei |
| `./scripts/dev.sh logs backend` | Logs de l'API |
| `./scripts/dev.sh logs frontend` | Logs del frontend (`tail -f`) |
| `./scripts/dev.sh logs worker` | Logs del worker de Celery |
| `./scripts/dev.sh logs beat` | Logs de Celery beat (el planificador) |
| `./scripts/dev.sh seed` | Configuració interactiva, la mateixa que fa servir qualsevol entorn |
| `./scripts/dev.sh seed demo` | Club de demostració amb credencials **generades**, és la preferida |
| `./scripts/dev.sh seed test` | Comptes de test e2e fixos, amb contrasenyes públiques |
| `./scripts/dev.sh passwd [email]` | Substitueix la contrasenya del super administrador per una de generada |
| `./scripts/dev.sh test [args]` | Bateria de tests del backend, en un contenidor; els arguments extra van a pytest |
| `./scripts/dev.sh shell` | Un shell dins del contenidor de l'API |
| `./scripts/dev.sh shelltest [run\|mutate\|lint]` | Les guardes de shell dels scripts de desplegament, en un contenidor Linux sobre una còpia de l'arbre |
| `./scripts/dev.sh migration "msg"` | Genera automàticament una revisió d'Alembic a partir dels canvis als teus models |
| `./scripts/dev.sh e2e` | Cypress, sense interfície (headless) |
| `./scripts/dev.sh e2e:open` | Cypress amb interfície gràfica |
| `./scripts/dev.sh e2e:parallel` | Cypress, 4 workers |
| `./scripts/dev.sh reset` | **Destructiu**, vegeu més avall |

`start`, `stop` i `restart` accepten `backend`, `frontend`, `worker`, `beat` o `all` (el valor per
defecte). `start all` aixeca el worker i el beat al costat de l'API i la base de dades.

`shelltest` és la manera d'executar les guardes de shell obligatòries després de qualsevol canvi
sota `scripts/`. Dona la resposta de la CI des de qualsevol màquina, Windows inclòs, i triga
aproximadament un minut. `./tests/shell/run.sh` també s'executa de manera nativa. A Git Bash se
salta les dues comprovacions que necessiten permisos de fitxer i enllaços simbòlics, que NTFS no
conserva, i triga diverses vegades més. Executa `shelltest mutate` en lloc de
`./tests/shell/mutate-check.sh`. Tots dos demostren que cada guarda està provada, però el natiu
reescriu els teus scripts versionats mentre treballa, i `shelltest` només toca una còpia.

> **`reset` esborra els teus volums.** Executa `docker compose down -v`, que destrueix la base de
> dades de desenvolupament *i* el volum d'emmagatzematge, i amb ell les pujades i
> `storage/secret.key`. Perdre aquesta clau vol dir que les credencials de proveïdors de pagament o
> d'SSO desades en aquella base de dades ja no es poden desxifrar. No demana confirmació. Fes-lo
> servir quan vulguis començar de zero, no per arreglar un contenidor encallat.

## URL dels serveis

| Servei | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API del backend | http://localhost:8003 |
| Documentació de l'API (Swagger) | http://localhost:8003/api/docs |
| Base de dades | localhost:5433 |
| Base de dades de test | localhost:5434 (l'arrenca `dev.sh test`) |
| Redis | localhost:6379 |
| Adminer (interfície de BD) | http://localhost:8181, no l'arrenca `dev.sh`, vegeu més avall |

Adminer és darrere d'un perfil de Compose i no té cap ordre a `dev.sh`:

```bash
docker compose -f backend/docker/docker-compose.yml --profile tools up -d adminer
```

## L'entorn de desenvolupament no està blindat, tot escolta a localhost

L'entorn de desenvolupament porta ajustos febles a propòsit: una contrasenya de base de dades fixa
(`memship`), Redis sense autenticació i, després de `seed test`, **credencials de super
administrador publicades en aquest repositori**. Això està bé en un portàtil i és desastrós en una
xarxa compartida, així que **per defecte no s'exposa res més enllà del loopback**: l'API, la base
de dades, Redis i Adminer escolten a `127.0.0.1`, i el servidor de desenvolupament de Next.js
també.

Lligar els contenidors no n'hi ha prou per si sol. Next.js escolta a `0.0.0.0` d'entrada, i el
frontend fa de proxy cap a l'API des del servidor, així que un servidor de desenvolupament a totes
les interfícies és un camí complet cap a l'aplicació, login inclòs, encara que tots els
contenidors siguin al loopback. Les dues meitats estan fixades.

### Treballar en una xarxa pública

Escoltar només al loopback és el que fa segura la xarxa d'una cafeteria o d'un coworking, i és tota
la defensa. Posa la resta a sobre:

- **Fes servir `./scripts/dev.sh seed demo`** en lloc de `seed test` per a la feina habitual.
  Sembra les mateixes dades d'exemple però genera la contrasenya del super administrador i els
  accessos de demostració, i els imprimeix una sola vegada. `seed test` existeix per a la bateria
  de Cypress, les credencials de la qual són un contracte i, per tant, públiques.
- **Si ja has executat `seed test`**, `./scripts/dev.sh passwd` substitueix la contrasenya del
  super administrador per una de generada. Tornar a executar `seed test` hi torna a posar les fixes
  quan tornis a necessitar la bateria.
- **No combinis mai `DEV_BIND=0.0.0.0` amb dades de `seed test`.** Llavors qualsevol persona de la
  xarxa pot llegir la contrasenya en aquest repositori i entrar com a super administrador.
  `dev.sh start` comprova si hi ha aquests comptes i t'avisa.

### Accedir a l'entorn des d'un altre dispositiu

Per provar-ho en un mòbil o des d'una VM, activa-ho per a aquella sessió:

```bash
DEV_BIND=0.0.0.0 ./scripts/dev.sh start all
```

Això publica els contenidors a totes les interfícies i arrenca Next.js amb `-H 0.0.0.0`. Fes-ho
només en una xarxa que controlis, i torna a sembrar abans amb `seed demo`.

### Notes per plataforma

El mecanisme `DEV_BIND` és la sintaxi `HOST:PORT:PORT` del mateix Docker més un flag de Next.js,
així que es comporta igual a les tres plataformes. El que canvia és el que l'envolta:

| Plataforma | Què cal saber |
|---|---|
| **Linux (Ubuntu 24.04+)** | Docker insereix les seves regles d'iptables **per davant de `ufw`**, així que un port publicat és accessible encara que el tallafoc el denegui. `ufw` no et salvarà de `DEV_BIND=0.0.0.0`: l'adreça on s'escolta és el control que funciona. |
| **macOS (Docker Desktop)** | La VM reenvia els ports a l'amfitrió i es respecta l'adreça on s'escolta, així que el loopback continua sent loopback. macOS pot demanar permís per a connexions entrants la primera vegada que facis servir `dev:lan`. |
| **Windows (Docker Desktop + WSL2)** | Escoltar al loopback funciona gràcies al reenviament de localhost de WSL2. En el mode de xarxa **mirrored** (Windows 11, `networkingMode=mirrored` a `.wslconfig`) la instància de WSL comparteix les interfícies de l'amfitrió, així que `0.0.0.0` dins de WSL és realment a la LAN, i qui demana permís és el Tallafoc de Windows, no `ufw`. Executa `dev.sh` des de WSL o Git Bash; és un script de bash. |

`0.0.0.0` vol dir *totes* les interfícies, incloses les de VPN i Tailscale, que arriben més lluny
que el wifi de la cafeteria.

## Configuració inicial

```bash
./scripts/dev.sh seed          # interactive, the same setup every environment uses
./scripts/dev.sh seed demo     # demo club, generated credentials, the everyday choice
./scripts/dev.sh seed test     # fixed test accounts + sample data, for the e2e suite
```

`seed test` crea els comptes amb què entra la bateria de Cypress, més 4 activitats d'exemple amb
modalitats i preus, inscripcions d'exemple i ~22 socis addicionals. Aquestes adreces i
contrasenyes són un contracte amb la bateria de tests més que no pas una decisió de la sembra,
així que viuen amb ella a
[`e2e/cypress/support/commands.ts`](https://github.com/marcandreuf/memship/blob/main/e2e/cypress/support/commands.ts).

> **`seed test` es nega a executar-se fora de desenvolupament.** Planta contrasenyes fixes i
> visibles al repositori, així que requereix `APP_ENV=development` o `CI`. Per a qualsevol cosa
> real, fes servir la configuració interactiva, vegeu
> [Configuració inicial](../getting-started/first-setup.md).

## Correu en desenvolupament

L'entorn de desenvolupament no envia res fins que es configura un proveïdor: cada enviament es
registra al log i se salta. Hi ha dues vies, i guanya la primera:

1. **Configuració > Correu** a l'aplicació en marxa. Es desa a la base de dades, així que l'API i
   el worker de Celery l'agafen tots dos sense reiniciar. És la preferida: és el mateix camí que fa
   servir un operador que allotja Memship, i és l'únic que llegeix el contenidor de l'API.
2. **`backend/.env`**, copia `backend/.env.example` i omple `RESEND_API_KEY` o el bloc `SMTP_*`.
   El fitxer és opcional, cap pas de configuració el crea, i el worker només el llegeix si hi és.
   Els seus `DATABASE_URL` i `CELERY_BROKER_URL` s'ignoren dins dels contenidors (guanyen les claus
   `environment:` de Compose), així que els valors de localhost que porta no poden trencar
   l'entorn.

Compte amb l'asimetria: el correu que s'envia directament des d'una petició (restabliment de
contrasenya, verificació de correu, l'enviament de prova de la mateixa pantalla Correu) surt del
contenidor `api`, que no llegeix `backend/.env`. Només el correu encuat passa pel worker.
Configura'l des de la pantalla Correu per provar tots dos camins.

## Tests

```bash
./scripts/dev.sh test                                # the whole backend suite
./scripts/dev.sh test tests/unit                     # one directory
./scripts/dev.sh test tests/unit/test_email.py -k layout   # anything else is passed to pytest
```

1.368 tests en uns 40 segons. S'executen en un contenidor `tests` d'un sol ús contra `db-test`,
el directori de dades del qual és un tmpfs, així que una execució no deixa res al darrere. Tot el
que va després de `test` passa directament a pytest.

El contenidor apunta Celery a `redis://redis:6379/15` en lloc del valor per defecte. La bateria
encua tasques (registrar un soci dispara correus de verificació i de confirmació), i la URL del
broker per defecte és `localhost:6379`, que en una màquina amfitriona resulta ser el Redis de
desenvolupament. Així, una execució a l'amfitrió publicava les tasques provocades pels tests al
broker *de desenvolupament* a la base de dades 0, on el worker de desenvolupament les recollia i
les executava contra la base de dades de desenvolupament. La base de dades 15 no té cap
consumidor, així que una tasca que provoca una asserció no va enlloc. (També és el que manté la
bateria ràpida: sense cap listener, kombu reintenta cada publicació durant ~19 segons, i només
això va fer passar un fitxer de 3s a 9m53s.)

Aquest contenidor és l'únic lloc on es construeix l'etapa `dev` de `backend/docker/Dockerfile`.
Porta l'extra `dev` (pytest, xdist, factory-boy) que la imatge distribuïda deixa fora a propòsit,
mentre que els contenidors de l'API, el worker i el beat continuen construint l'etapa de
producció. Així l'entorn contra el qual desenvolupes continua sent el que es distribueix, i les
dependències de test no arriben mai a cap registre. `backend/tests` està muntat amb bind mount,
així que un test editat s'executa immediatament; només un canvi de dependències necessita
reconstruir. La base de dades de test es recrea a cada execució (`dev.sh test` elimina `db-test`
abans de començar), així que una columna afegida a un model hi és la propera vegada que s'executa
la bateria.

Per als tests end-to-end, **executa la bateria completa contra una compilació de producció**:

```bash
cd e2e && pnpm test:parallel:prod
```

`next dev` compila cada ruta a la primera petició, i amb 4 workers compartint un sol servidor de
desenvolupament aquesta espera empeny les navegacions més enllà dels seus temps d'espera: els
specs fallen, o només passen en reintentar, i quins ho fan varia entre execucions.
`test:parallel:prod` compila, serveix, executa i ho desmunta tot.

**Tots dos executors en paral·lel tornen a sembrar la base de dades de desenvolupament abans que
comenci la bateria** (`seed --test --reset-club-data`, uns 11 segons). La sembra escriu finestres
d'inscripció relatives al dia en què es va executar, així que un conjunt de dades reutilitzat
envelleix fins que aquestes finestres es tanquen i els specs fallen per un comportament correcte.
Això esborra les dades del club que tinguis a la base de dades de desenvolupament; els super
administradors, els rols del sistema i els proveïdors de pagament es conserven. Per executar-la
contra les dades tal com són, defineix `E2E_KEEP_DATA=1`:

```bash
cd e2e && E2E_KEEP_DATA=1 pnpm test:parallel:prod
```

Totes les peticions e2e arriben a l'API des de la mateixa adreça de loopback, així que els límits
d'autenticació per IP veuen tota la bateria com un sol client. L'entorn de desenvolupament apuja
el límit de registre a 1.000 per hora (`REGISTER_LIMIT_PER_IP` a
`backend/docker/docker-compose.yml`; producció es queda en 5), així que les execucions seguides ja
no fan fallar els specs de registre amb `429`. La resta de límits no canvien. Els comptadors són
en memòria, així que `docker compose restart api` els buida tots.

Els reintents amaguen les fallades, així que llegeix les captures de pantalla de
`e2e/cypress/screenshots/` (ignorat per git, se sobreescriu a cada execució): una captura sense el
sufix `attempt N` vol dir que un test ha fallat una vegada i ha passat en reintentar. Una execució
neta no en deixa cap. Les passades intermitents només en reintentar sota càrrega en paral·lel són
un problema obert conegut, vegeu la [issue #58](https://github.com/marcandreuf/memship/issues/58).

## Afegir una dependència al backend

Les dependències s'instal·len al virtualenv de la imatge en temps de compilació, així que una de
nova no és als contenidors en execució fins que no reconstrueixes. El contenidor de test és una
compilació separada d'una etapa separada, així que necessita la seva:

```bash
docker compose -f backend/docker/docker-compose.yml build --no-cache api
docker compose -f backend/docker/docker-compose.yml up -d --force-recreate api celery-worker celery-beat
docker compose -f backend/docker/docker-compose.yml --profile test build tests
```

`backend/pyproject.toml` *sí* que està muntat al contenidor de test, però només perquè la
configuració pròpia de pytest segueixi el checkout. Un manifest muntat no instal·la res.

## Logs

| On | Com |
|---|---|
| Frontend | `frontend/logs/dev-server.log`, o `./scripts/dev.sh logs frontend` |
| Backend | `./scripts/dev.sh logs backend` |
| Celery | `./scripts/dev.sh logs worker` / `logs beat` |

Celery és el component que falla en silenci. Si s'aturen la facturació programada o els correus
de recordatori, mira-hi abans que enlloc més.

## Migracions

El contenidor de l'API aplica `alembic upgrade head` a cada arrencada, així que una migració
baixada ja és a la teva base de dades quan el contenidor està aixecat. Per crear-ne una:

```bash
./scripts/dev.sh migration "add attachment type allowlist"
```

Es genera automàticament contra la base de dades de desenvolupament en marxa i escriu la revisió a
`backend/alembic/versions` a l'amfitrió. L'ordre s'executa amb el **teu** uid en lloc del de la
imatge, que és el que fa que el fitxer nou sigui teu per editar-lo: l'usuari integrat del
contenidor és l'uid 1001, i aquest no és l'operador a totes les màquines.

## Eines de l'editor

El backend s'executa en un contenidor; el teu editor, no. L'autocompletat, el go-to-definition i
la comprovació de tipus en línia necessiten un intèrpret que pugui resoldre `fastapi`,
`sqlalchemy` i la resta, i aquesta és l'única raó per la qual unes eines de Python encara podrien
tocar la teva màquina:

- **Apunta l'editor al contenidor**, amb VS Code Dev Containers o un intèrpret remot de
  JetBrains, contra el servei `api`. No s'instal·la res a l'amfitrió.
- **Mantén un virtualenv a l'amfitrió només com a objectiu del language server**,
  `cd backend && uv sync --extra dev`. Mai no s'hi executa res: `dev.sh` no el llegeix, i els
  tests tampoc.

Totes dues són opcionals. L'entorn, la bateria i les migracions funcionen sense cap de les dues
instal·lada.

## El frontend directament

```bash
cd frontend
pnpm install
./dev.sh start      # background, with logs
./dev.sh stop
./dev.sh status
./dev.sh logs
pnpm build          # production build
pnpm lint
```
