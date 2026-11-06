<!-- source: en/self-hosting/troubleshooting.md -->
<!-- source-hash: beba2acfbaab -->

# Resolució de problemes

Símptomes amb què es troba de debò un operador, i què els provoca. Si alguna cosa d'aquí és
incorrecta o hi falta, [obre una incidència](https://github.com/marcandreuf/memship/issues),
aquesta pàgina està feta a partir d'instal·lacions reals, no de la teoria.

> **En anglès:** [Troubleshooting](../../en/self-hosting/troubleshooting.md).

Primer de tot, dues ordres que val la pena executar abans que res més:

```bash
docker compose ps                       # what is up, and what is restarting
curl -s http://localhost/api/v1/health  # {"status":"healthy","version":"2.19.0",...}
```

`version` és l'etiqueta d'imatge que tens. Si diu `latest`, la instal·lació no està fixada a cap
versió i no pots saber què s'està executant: fixa-la amb `./scripts/upgrade.sh <version>`, que
comprova la versió contra les teves dades abans de reemplaçar res. `install.sh` es nega a
executar-se contra una instància que ja està en marxa, precisament perquè aquesta comprovació no
se salti.

## La plataforma no arrenca

### `Conflict. The container name "/memship-db" is already in use`

Ja hi ha una altra instància de memship en marxa en aquesta màquina. El fitxer de Compose posa nom
explícitament als contenidors, i aquests noms són globals al dimoni de Docker, així que una segona
còpia hi topa fins i tot des d'un altre directori, amb una altra arrel de dades i un altre nom de
projecte de Compose.

```bash
docker ps -a --filter name=memship-      # find the other instance
```

Executa la segona instància en una altra màquina o màquina virtual. Si l'altra està morta i vols
recuperar-ne el nom, fes `docker rm` dels contenidors que hagin quedat.

### Els contenidors es reinicien en bucle i els logs diuen permission denied

Gairebé sempre és l'arrel de dades. Docker crea **com a root** l'origen d'un bind mount que no
existeix, i el backend s'executa amb el teu uid, així que no pot escriure en un directori que
Docker ha creat per a ell:

```bash
ls -l "$MEMSHIP_DATA_ROOT"     # storage/ and celerybeat/ should be yours, postgres/ uid 70
sudo chown -R "$(id -u):$(id -g)" "$MEMSHIP_DATA_ROOT"/{storage,celerybeat,caddy,backups}
```

`postgres/` és diferent: mode `0700`, propietat de l'uid 70, i tu no el pots llegir. Això és
correcte: llegeix la base de dades amb `./scripts/db-backup.sh`, no amb `ls`.

Si actualitzes des d'una versió en què el backend s'executava com a root, mira la nota a
[Actualitzar](upgrading.md).

### Una migració s'ha negat a executar-se i l'API no arrenca

Després d'una actualització, `verify-deployment.sh` falla i l'API no respon mai.
`docker compose ps` mostra `api` reiniciant-se, i els seus logs acaben amb un informe, no amb una
traça de pila que hagis d'interpretar:

```
Cannot normalise email addresses: 1 address(es) are held by more than one account,
differing only by case or surrounding whitespace.

  marc@example.com
    34 <Marc@Example.com> [last signed in 2026-09-01] [has a member record]
    35 <marc@example.com> [inactive] [never signed in]

Decide which account keeps each address and remove or change the others, then run
the upgrade again.
Nothing has been changed, this migration made no writes.
```

**Això és deliberat, no una versió trencada.** Algunes migracions inspeccionen les dades abans de
canviar-les i s'aturen quan troben alguna cosa que només hauria de decidir una persona. La
comprovació no ha escrit res, així que la base de dades està exactament com estava. **No
restauris la instantània prèvia a l'actualització**, no hi ha res a desfer, i restaurar-la perd
tot el que s'hagi escrit des que es va fer.

Si l'informe ha passat de llarg, torna'l a llegir amb:

```bash
docker compose logs api --tail 40
```

**Soluciona-ho canviant una fila, no esborrant-ne una.** Esborrar el compte duplicat és el
moviment evident i l'equivocat: `members.user_id` és `ON DELETE SET NULL`, així que eliminar el
compte deslliga la fitxa de soci d'aquella persona i no deixa cap manera de tornar-la a connectar,
i si el compte ha llançat mai una execució de facturació o ha creat un avís, l'esborrat falla
directament per una clau forana.

Tria el compte que retiraràs fent servir les anotacions de l'informe, quan va entrar per última
vegada, si té fitxa de soci, i dona-li una adreça diferent:

```bash
docker compose exec -T db psql -U memship -d memship_db \
  -c "UPDATE users SET email = 'retired-35-' || email WHERE id = 35;"
```

Això és reversible, no toca res més i satisfà la comprovació. Després deixa que la migració
s'executi:

```bash
docker compose restart api
./scripts/verify-deployment.sh "$MEMSHIP_VERSION"
```

Un cop la instància torni a funcionar, resol el duplicat com cal a **Configuració → Comptes**, on
veus els dos comptes i pots desactivar o canviar l'adreça del que no vols. Fer-ho allà i no en SQL
vol dir que el canvi queda auditat.

Si l'informe esmenta més comptes dels que pots resoldre ràpidament, tingues en compte que la
instància està aturada durant tot el procés, la comprovació s'executa després que la plataforma
s'hagi reemplaçat. Avançar-la és la
[incidència #194](https://github.com/marcandreuf/memship/issues/194).

### Postgres no arrenca a RHEL, Fedora, Rocky o AlmaLinux

SELinux. Els bind mounts s'han de tornar a etiquetar, mira la secció de SELinux
d'[Instal·lació (Docker)](../getting-started/installation.md).

### `port is already allocated`

Alguna altra cosa ocupa el 80 o el 443:

```bash
sudo ss -ltnp | grep -E ':(80|443)\b'
```

Atura-la, o defineix `HTTP_PORT` / `HTTPS_PORT` al `.env` i torna a crear els contenidors. Tingues
en compte que l'HTTPS automàtic necessita el port 80 accessible des d'internet: Let's Encrypt
valida per HTTP-01.

## Està en marxa però no hi puc accedir

**Comprova des d'on mires.** Tots els URL amb `localhost` de la documentació són *des del
servidor*. L'API i la base de dades estan lligades deliberadament a `127.0.0.1`, així que des del
teu portàtil només són accessibles el frontend i `/api/...` a través del proxy, al domini o la IP
del servidor.

**`ufw` no limita Docker.** Docker escriu les seves regles d'iptables per davant de les del
tallafoc, així que un port publicat a `0.0.0.0` continua accessible des d'internet encara que
`ufw` el denegui. Comprova-ho des d'una altra màquina en lloc de fiar-te de `ufw status`:

```bash
nmap -Pn -p 22,80,443,5433,8003 your-host
```

El 8003 i el 5433 haurien d'estar tancats. Si estan oberts, alguna cosa ha posat `API_BIND` o
`DB_BIND` a `0.0.0.0`, o ha afegit una entrada `ports:`.

## HTTPS i certificats

### No s'emet cap certificat

Caddy valida per HTTP-01, així que el nom de màquina ja ha de resoldre cap a aquest servidor i el
port 80 ha d'estar obert. `install.sh` es nega a arrencar quan el DNS no coincideix, perquè les
validacions fallides tenen un límit de 5 per nom de màquina i per hora.

### "Too many certificates already issued"

Let's Encrypt permet **5 certificats per setmana per al mateix conjunt de noms de màquina**. El
certificat emès es guarda a `<data-root>/caddy/data`; esborrar aquest directori, com fa un
desmuntatge complet, fa que el pròxim arrencament demani un certificat *nou* en lloc de renovar-lo.
Conserva `caddy/data` entre reconstruccions, i assaja les instal·lacions sense `--domain`.

### Falten les capçaleres de seguretat després d'una actualització

El `Caddyfile` està muntat amb un bind mount, així que canviar-ne el contingut no canvia la
configuració del contenidor en marxa, i `docker compose up -d` no veu cap motiu per tornar-lo a
crear:

```bash
docker compose ps caddy                          # "Up 3 days" after an upgrade is the tell
docker compose up -d --force-recreate caddy
curl -sI https://your-host/api/v1/health | grep -i -E 'content-security|x-frame|strict-transport'
```

Comprova les capçaleres en una ruta de l'**API**, no només a la pàgina d'inici. El frontend en
posa algunes pel seu compte, així que `/` pot semblar protegida mentre totes les respostes de
l'API van sense res.

## Posada en marxa i inici de sessió

### `--admin-email needs the password in MEMSHIP_ADMIN_PASSWORD`

`docker compose exec` no passa l'entorn del teu shell al contenidor. Posa el nom de la variable
després de `-e`:

```bash
MEMSHIP_ADMIN_PASSWORD='...' docker compose exec -T -e MEMSHIP_ADMIN_PASSWORD \
  api python -m app.cli.seed --admin-email you@example.org
```

### Ningú no pot entrar / s'ha perdut la contrasenya del superadministrador

Restableix-la des de la màquina amb la mateixa ordre. És deliberadament l'única manera d'entrar,
no hi ha cap recuperació per a un superadministrador a través de la interfície web, i cada
restabliment s'escriu al registre d'auditoria sense usuari que l'executi, ja que qui l'ha fet
tenia accés al shell.

### Un soci no pot entrar: "Confirm your email address before signing in"

Per entrar cal tenir l'adreça confirmada, així que un compte que no ha seguit mai l'enllaç de
confirmació queda bloquejat. Normalment la persona demana un enllaç nou des de la pàgina d'inici
de sessió, però això necessita un transport de correu que funcioni, i un transport de correu que
fallava sense fer soroll és el motiu habitual pel qual l'adreça no es va confirmar mai.

En aquest cas, confirma-la des de la màquina, un cop sàpigues qui és la persona:

```bash
docker compose exec -T api python -m app.cli.verify_email --list
docker compose exec -T api python -m app.cli.verify_email --email member@example.org
```

`--list` mostra tots els comptes en aquest estat, que també és la manera més ràpida de saber si
l'enviament de correu fa temps que està trencat. Un cop arreglat l'enviament, pots buidar la
cua pendent d'una sola vegada:

```bash
docker compose exec -T api python -m app.cli.verify_email --all-unverified --yes
```

Això confirma adreces **sense que ningú demostri que són seves**, i per això exigeix `--yes`.
Fes-ho servir quan sàpigues que els comptes són legítims i el problema era el correu; fes servir
`--email`, d'un en un, quan no n'estiguis segur.

L'ordre no envia mai res, és per al cas en què el que està trencat és l'enviament.

### `SECRET_KEY` encara té el valor d'exemple

La clau d'exemple que porta `.env.example` i el valor per defecte de Compose són públics en aquest
repositori, i signen el testimoni de sessió, l'HMAC del QR del carnet i l'estat d'OAuth. Per això
el servidor tracta una clau d'exemple com si no n'hi hagués cap: en genera una i la desa a
`storage/session.key`, igual que quan `SECRET_KEY` és buida. No es trenca res mentre aquest fitxer
es conservi. Definir la clau explícitament és el que permet que una màquina reconstruïda, o una
arrel de dades perduda, mantingui les sessions funcionant:

```bash
openssl rand -hex 32
```

## Còpies de seguretat i restauració

### Una restauració ha fallat

L'script deixa l'API aturada a propòsit. Engegar-la executaria les migracions contra la base de
dades restaurada a mitges i et donaria una instància que diu `"healthy"` i no conté res.

Restaura el bolcat previ a la restauració que esmenta el missatge d'error, no simplement el més
recent, que després d'un segon intent fallit és una còpia de la base de dades ja malmesa.

### Una restauració diu que no hi ha terminal

El selector de còpies i la confirmació escrita en necessiten un. Des d'un script o des de cron,
indica el bolcat i passa `--yes`:

```bash
./scripts/db-restore.sh --confirm --yes memship_20260819_141405.sql.gz
```

### "Restore complete" però les dades han desaparegut

Les versions anteriors a la 2.3.0 podien informar d'èxit després d'una restauració fallida: `psql`
s'executava sense `ON_ERROR_STOP`, així que un bolcat corrupte o truncat buidava la base de dades i
igualment mostrava un resultat en verd. Actualitza, i torna a provar les restauracions. Una còpia
de seguretat que no has restaurat mai és una suposició.

## Logs

```bash
docker compose logs -f api             # backend, including migrations on startup
docker compose logs -f celery-worker   # scheduled jobs and email sending
docker compose logs -f caddy           # TLS issuance and proxying
docker compose logs --since 10m        # everything, recent
```

Celery és el component que falla sense fer soroll: si els recordatoris o els correus s'aturen,
mira primer allà.
