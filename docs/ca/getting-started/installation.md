<!-- source: en/getting-started/installation.md -->
<!-- source-hash: 989a01ac9f69 -->

# Instal·lació (Docker)

Aquesta guia cobreix una instal·lació autoallotjada de **producció**. Per a una avaluació local
ràpida, fes servir l'[Inici ràpid](quickstart.md).

> **En anglès:** [Installation (Docker)](../../en/getting-started/installation.md).

## Requisits previs

- Un servidor amb Docker Engine i el connector de Compose
- Un usuari normal (no root) del grup `docker`: l'entorn no s'instal·la com a root
- `curl` i `tar`, per descarregar una versió. `tar` hi és a tots els servidors Debian/Ubuntu; a les
  imatges mínimes de vegades hi falta `curl`: `sudo apt-get update && sudo apt-get install -y curl`
- **No cal `git`.** Una versió es descarrega com a tarball i el servidor no conté cap còpia del
  codi font; res d'una instància en marxa fa servir git, així que no hi ha cap motiu per
  instal·lar-lo
- Un nom de domini, amb un registre DNS A que ja apunti al servidor, si vols HTTPS automàtic. Si el
  domini és de l'entitat i no teu, de manera que el nom de host, la zona DNS i el domini de correu
  són cosa de tres persones diferents, llegeix primer
  [El domini de la teva entitat](../self-hosting/domain-and-dns.md)

> **Una instància de memship per host.** El fitxer de Compose dona noms explícits als seus
> contenidors (`memship-db`, `memship-api`, …), i això és el que permet que els scripts i la
> documentació s'hi refereixin. Els noms són globals al dimoni de Docker, de manera que una segona
> instància, fins i tot des d'un altre directori, amb la seva pròpia arrel de dades i el seu propi
> projecte de Compose, falla a mig camí amb
> `Conflict. The container name "/memship-db" is already in use`. Fes servir un segon host, o una
> VM.

### Començar des d'un servidor buit

`scripts/vps-bootstrap.sh` fa la meitat de la preparació que correspon a root. Executa'l **una sola
vegada, com a root**, en una màquina Debian 12 o Ubuntu 24.04 acabada d'instal·lar:

Descarrega'l en un lloc on ja puguis escriure, el teu propi directori personal. La instal·lació en
si viu a `/srv`, però ningú no hi pot escriure fins que no s'ha executat el bootstrap. Tria una
versió de la [pàgina de versions](https://github.com/marcandreuf/memship/releases) i fes-la servir
a tot arreu:

```bash
MEMSHIP_VERSION=3.3.1

curl -fsSLO "https://raw.githubusercontent.com/marcandreuf/memship/v${MEMSHIP_VERSION}/scripts/vps-bootstrap.sh"
chmod +x vps-bootstrap.sh
sudo ./vps-bootstrap.sh --user deploy --ssh-key-file ~/.ssh/authorized_keys
```

L'script és autònom, no necessita cap altre fitxer del repositori, i per això n'hi ha prou amb un
sol `curl`.

`--user` indica el compte que serà propietari de la instal·lació; passa-hi el compte amb què ja has
iniciat la sessió (`--user "$USER"`) per fer-lo servir en lloc de crear un `deploy` a part.
`--ssh-key-file` rep un fitxer que contingui una clau SSH **pública**: el teu propi
`~/.ssh/authorized_keys` és l'opció fiable, perquè un servidor nou no té cap fitxer `.pub` per
enlloc. Sense clau no pots iniciar la sessió com a usuari nou. La `~` de dalt l'expandeix el teu
propi shell abans que s'executi `sudo`, així que és el teu directori personal; des d'un **shell de
root** (`sudo -i`) seria el de root, així que allà passa-hi un camí absolut.

Crea l'usuari de desplegament, instal·la Docker des del repositori del mateix Docker, activa
`unattended-upgrades`, `fail2ban` i `ufw`, configura el fus horari i afegeix una neteja setmanal
d'imatges.

Deliberadament **no** reforça l'SSH: en lloc d'això imprimeix aquestes ordres, en un ordre que
manté oberta una sessió que funciona mentre verifiques cada pas. Un script no pot comprovar que
encara pots iniciar la sessió, i equivocar-se d'ordre et deixa fora d'un servidor que potser no té
consola.

Després tanca la sessió i torna a entrar, perquè la pertinença de l'usuari de desplegament al grup
`docker` tingui efecte.

> **El grup `docker` dona l'equivalent de root.** Qualsevol que pugui executar `docker` pot muntar
> `/` dins d'un contenidor i escriure a qualsevol lloc del host. L'usuari de desplegament és un
> compte privilegiat, no un entorn aïllat.

## Instal·lació

`/srv` pertany a root, així que primer es creen els dos directoris **com a root**, i tot el que ve
després s'executa com a usuari de desplegament. Anomena'ls **tots dos**: `install -d` dona la
propietat als directoris que crea, no al pare, de manera que si només crees `app`, `/srv/openmemship`
queda en mans de root i l'usuari de desplegament no pot crear l'arrel de dades; aleshores
`install.sh` s'atura amb `cannot create /srv/openmemship/data`.

```bash
sudo install -d -o deploy -g deploy /srv/openmemship/app /srv/openmemship/data
```

Si l'usuari de desplegament és el compte amb què ja has iniciat la sessió, fes servir
`-o "$USER" -g "$USER"`.

> **L'usuari de desplegament no pot fer `sudo`.** `vps-bootstrap.sh` el crea amb `adduser
> --disabled-password`, així que no té cap contrasenya per escriure en un indicador de sudo. És
> deliberat: el compte ja té el sòcol de docker, que equival a root, i una segona via cap a root no
> aporta res. Per això l'ordre de dalt s'executa com a root i no com a usuari de desplegament.

Ara passa a ser l'usuari de desplegament; res del que segueix necessita root. `install.sh` escriu
`.env` dins del directori d'instal·lació i n'ha de ser el propietari:

```bash
MEMSHIP_VERSION=3.3.1

curl -fsSL "https://github.com/marcandreuf/memship/archive/refs/tags/v${MEMSHIP_VERSION}.tar.gz" \
  | tar -xz -C /srv/openmemship/app --strip-components=1
cd /srv/openmemship/app
./scripts/install.sh --data-root /srv/openmemship/data --domain memship.example.com \
                     --tag "$MEMSHIP_VERSION"
```

L'script de bootstrap del teu directori personal ja ha fet la seva feina i el pots esborrar.

Això omple l'arrel de dades, genera secrets reals a `.env` (mode 600), descarrega les imatges
publicades i arrenca l'entorn.

**Copia `.env` fora del servidor ara, abans d'hi posar dades reals.** `SECRET_KEY` i
`MEMSHIP_SECRET_KEY` s'acaben de generar aquí, no es tornen a generar mai i no existeixen enlloc
més. Desxifren les credencials dels proveïdors de pagament, de l'SSO i del correu desades a la base
de dades, de manera que sense aquest fitxer un bolcat perfecte de la base de dades les restaura com
a text xifrat il·legible. Desa'l en un gestor de contrasenyes al qual pugui accedir un segon
administrador; consulta [Còpies de seguretat i restauració](../self-hosting/backups-and-restore.md#fes-ho-el-mateix-dia-que-installes).

`install.sh` també escriu **`POST-INSTALL.md`** al costat de `.env` en una primera instal·lació:
aquest pas, més crear la teva entitat, programar les còpies de seguretat i configurar el correu,
amb els camins ja omplerts. Segueix-lo pas a pas i esborra'l.

**La teva instal·lació queda fixada a una versió.** `--tag` es converteix en `IMAGE_TAG`, de
manera que el desplegament es manté en aquella versió fins que el moguis deliberadament, i
`/api/v1/health` informa de quina executa.

**Aquí `--tag` és obligatori, i l'instal·lador ho fa complir.** En un desplegament desempaquetat
d'un tarball de versió no hi ha cap còpia de git, així que no hi ha cap etiqueta d'on llegir la
versió, i ometre `--tag` atura la instal·lació:

```
Error: --tag is required here: there is no git tag to read a version from.
```

Abans es resolia a `latest`, un objectiu mòbil, i donava una instància que informava de la seva
pròpia versió com la cadena literal `latest`. Es nega abans d'escriure `.env` o de generar cap
secret, així que indica la versió i torna-ho a executar. En una còpia de git encara es pot ometre
`--tag`, i aleshores pren per defecte l'etiqueta de versió més recent; `--tag latest` continua
disponible per seguir deliberadament les imatges que siguin més noves en cada moment.

**Per actualitzar més endavant, segueix [Actualitzar](../self-hosting/upgrading.md).** Moure
només `IMAGE_TAG` no n'hi ha prou: `docker-compose.yml`, el `Caddyfile` i `scripts/` es distribueixen
al costat de les imatges i no dins d'elles, així que una actualització comença refrescant aquests
fitxers des de la nova versió.

**Primer fes que el DNS apunti al servidor.** `install.sh` es nega a arrencar quan el nom de host no
es resol cap a aquest host, perquè Caddy valida per HTTP-01 i Let's Encrypt limita les validacions
*fallides* a 5 per nom de host i per hora: una arrencada prematura et pot deixar sense certificats
durant una hora. Fes servir `--skip-dns-check` només si saps per què te'l saltes.

L'script es pot tornar a executar sense perill. No sobreescriu mai un `.env` existent, i tornar-lo a
executar és com agafes més endavant un `IMAGE_TAG` nou.

> **Reinstal·lar des de zero gasta certificats.** El certificat emès viu a
> `<data-root>/caddy/data`. Esborra aquest directori, com fa un desmuntatge complet, i la propera
> arrencada demana un certificat **nou** en lloc de renovar el vell. Let's Encrypt permet **5
> certificats per setmana per al mateix conjunt de noms de host**, de manera que unes quantes
> reinstal·lacions des de zero contra un mateix domini l'esgotaran i et deixaran sense HTTPS fins
> que la finestra avanci. Quan assagis una instal·lació, omet `--domain` i treballa amb HTTP pla, i
> afegeix el domini a la passada final. Conservar `caddy/data` en una reconstrucció evita del tot
> la reemissió.

Després executa la configuració inicial, que crea el teu superadministrador i la teva entitat:

```bash
docker compose exec -it api python -m app.cli.seed
```

El `-it` és important: l'ordre fa preguntes. Consulta
[Configuració inicial](first-setup.md) per saber què pregunta i quins indicadors desatesos fa
servir en el seu lloc un desplegament automatitzat.

Obre el teu domini o, si has instal·lat sense, **http://&lt;server-address&gt;**, el nom de host o
la IP amb què arribes a la màquina. `localhost` només funciona quan instal·les a la màquina que
tens al davant.

### Sense domini

Omet `--domain`. Aleshores Caddy serveix HTTP pla pel port 80, que és el que vols per a una
instal·lació local o interna.

Aquesta és també la manera d'assajar una instal·lació en un servidor real sense gastar certificats:
instal·la sense `--domain`, confirma que l'entorn funciona i després torna-ho a executar amb
`--domain` per afegir HTTPS. Tornar-ho a executar actualitza `SITE_ADDRESS` i els URL públics
alhora, així que res no queda apuntant a l'adreça antiga.

## L'arrel de dades

Tot el que ha de sobreviure a un redesplegament viu sota un sol directori:

| Camí             | Contingut                                                       |
|------------------|-----------------------------------------------------------------|
| `postgres/`      | La base de dades                                                 |
| `storage/`       | Fitxers pujats (logotips, imatges d'activitats, PDF generats) **i les claus generades `secret.key` i `session.key`** |
| `celerybeat/`    | L'estat del planificador                                         |
| `caddy/data`     | Clau del compte ACME i certificats TLS emesos                    |
| `caddy/config`   | Configuració desada automàticament per Caddy                     |
| `backups/`       | Bolcats de la base de dades escrits per `scripts/db-backup.sh`   |

Fer una còpia de seguretat de memship vol dir fer-ne una d'**aquest únic directori, més `.env`**.
Consulta [Còpies de seguretat i restauració](../self-hosting/backups-and-restore.md).

Tres coses que val la pena saber-ne:

- Són bind mounts, no volums amb nom, així que les dades sobreviuen a
  `docker compose down -v` i a `docker system prune --volumes`.
- `storage/` l'escriu el backend executant-se amb el teu uid, així que els fitxers pujats es poden
  llegir sense `sudo`.
- `postgres/` té mode `0700` i és propietat de l'uid 70: el veus com a camí però no el pots llegir.
  Això és correcte i esperat. Llegeix la base de dades amb `scripts/db-backup.sh`, no amb `ls`.

> **Posa l'arrel de dades a `/srv`, no en un directori personal.** `/srv` és la ubicació FHS per a
> les dades de serveis, sobreviu a l'esborrat de l'usuari i continua accessible quan canvien els
> permisos d'un directori personal. Una arrel de dades sota `$HOME` sí que funciona amb Docker
> normal (el dimoni resol els orígens dels bind mounts com a root, així que un directori personal
> `0700` no impedeix que arrenqui Postgres), però falla amb **Docker rootless i Podman**, on l'uid
> del mateix contenidor ha de poder travessar el camí.

### Hosts amb SELinux (RHEL, Fedora, Rocky, AlmaLinux)

En sistemes amb SELinux en mode enforcing, els bind mounts necessiten reetiquetatge o els
contenidors reben "permission denied" malgrat que la propietat sigui correcta. O bé afegeixes `:z`
a cada bind mount de `docker-compose.yml`:

```yaml
- ${MEMSHIP_DATA_ROOT:-./data}/postgres:/var/lib/postgresql/data:z
```

…o bé reetiquetes l'arbre una sola vegada, cosa que sobreviu a les actualitzacions de Compose:

```bash
sudo semanage fcontext -a -t container_file_t "/srv/openmemship/data(/.*)?"
sudo restorecon -Rv /srv/openmemship/data
```

Els hosts Debian i Ubuntu no es veuen afectats.

## Instal·lació manual

Si prefereixes no fer servir `install.sh`, els passos manuals equivalents són:

```bash
MEMSHIP_VERSION=3.3.1

mkdir -p memship
curl -fsSL "https://github.com/marcandreuf/memship/archive/refs/tags/v${MEMSHIP_VERSION}.tar.gz" \
  | tar -xz -C memship --strip-components=1
cd memship
cp .env.example .env
```

Després defineix, com a mínim:

- **`MEMSHIP_DATA_ROOT`**: camí absolut a l'arrel de dades descrita més amunt
- **`SECRET_KEY`** i **`DB_PASSWORD`**: valors aleatoris, mai els de mostra. `SECRET_KEY` es pot
  deixar en blanc (el servidor en genera una a `storage/session.key`), però definir-la explícitament
  és el que permet que un host reconstruït mantingui les sessions actives i les credencials de
  pagament llegibles
- **`MEMSHIP_SECRET_KEY`**: xifra les credencials desades de l'SSO i dels proveïdors de pagament.
  Defineix-la explícitament perquè un host reconstruït encara pugui desxifrar una còpia de
  seguretat restaurada
- **`HOST_UID`** / **`HOST_GID`**: el teu `id -u` i `id -g`, perquè els fitxers pujats en bind
  mounts siguin teus
- **`SITE_ADDRESS`**: el teu nom de host per a HTTPS automàtic, o deixa-ho buit per a HTTP pla
- **`IMAGE_TAG`**: fixa una versió publicada; consulta [Actualitzar](../self-hosting/upgrading.md)

Crea l'arbre de directoris i després arrenca l'entorn. `.env` el llegeix Compose, no el teu shell,
així que exporta-hi també el camí aquí, o escriu-lo sencer:

```bash
export MEMSHIP_DATA_ROOT=/srv/openmemship/data
mkdir -p "$MEMSHIP_DATA_ROOT"/{postgres,storage,celerybeat,caddy/data,caddy/config,backups}
docker compose pull
docker compose up -d
```

No et saltis el `mkdir`. Docker crea ell mateix l'origen d'un bind mount que falta, però com a
**root**, i el backend s'executa amb el teu uid, així que després no pot escriure els seus propis
fitxers pujats.

Consulta la [Referència de configuració](../self-hosting/configuration.md) per veure tots els
paràmetres disponibles.

## Serveis

L'entorn de Compose per defecte s'executa darrere d'un proxy invers Caddy. Aquests URL són **tal com
es veuen des del mateix servidor**: l'API i la base de dades estan lligades a `127.0.0.1`, així que
`localhost` és l'única manera d'arribar-hi. Des de qualsevol altre lloc, fes servir el teu domini o
l'adreça del servidor, que només arriba a les dues primeres files:

| Servei      | URL (al servidor)                | Descripció                   |
|-------------|----------------------------------|------------------------------|
| Frontend    | `http://localhost`               | Portal de socis (via Caddy)  |
| API         | `http://localhost/api/v1/health` | API del backend (via Caddy)  |
| API directa | `http://localhost:8003`          | API del backend (directa)    |

> **`ufw` no limita Docker.** Docker insereix les seves pròpies regles d'iptables per davant de les
> del tallafoc, de manera que un port publicat a totes les interfícies continua accessible des
> d'internet encara que `ufw` el denegui. Per això l'entorn que es distribueix publica l'API (8003) i
> Postgres (5433) **només a `127.0.0.1`**, i per això s'hi pot arribar des del mateix servidor i des
> d'enlloc més. Posar `API_BIND` o `DB_BIND` a `0.0.0.0`, o afegir la teva pròpia entrada `ports:`,
> deixa aquell servei a internet públic sigui quina sigui la configuració del tallafoc. Verifica-ho
> des d'una altra màquina amb `nmap -Pn -p 22,80,443,5433,8003 <your-host>` en lloc de fiar-te de
> `ufw status`.

## Passos següents

1. [Configuració inicial](first-setup.md): crea la teva entitat i l'administrador.
2. [Referència de configuració](../self-hosting/configuration.md): revisa els paràmetres de
   producció.
3. [Enviament de correu](../self-hosting/email.md): necessari per a les confirmacions d'adreça,
   els restabliments de contrasenya i les notificacions de pagament.
4. [Còpies de seguretat i restauració](../self-hosting/backups-and-restore.md): configura-ho abans
   de posar-te en marxa.
