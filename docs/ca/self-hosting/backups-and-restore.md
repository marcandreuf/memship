<!-- source: en/self-hosting/backups-and-restore.md -->
<!-- source-hash: 1349a9eb7e59 -->

# Còpies de seguretat i restauració

Configura les còpies de seguretat **abans** de posar-te en producció, i prova una restauració com
a mínim una vegada. Una còpia que no has restaurat mai és una suposició, no una còpia de
seguretat.

> **En anglès:** [Backups & restore](../../en/self-hosting/backups-and-restore.md).

## Què cal copiar

Dues coses, i necessites totes dues:

| Què | Per què |
|---|---|
| **L'arrel de dades** (`MEMSHIP_DATA_ROOT`, p. ex. `/srv/openmemship/data`) | La base de dades, els fitxers pujats, `secret.key`, `session.key`, els certificats TLS, tot el que ha de sobreviure |
| **`.env`** | Els teus secrets generats. Perdre `SECRET_KEY` i `MEMSHIP_SECRET_KEY` vol dir perdre l'accés a les dades xifrades fins i tot amb un bolcat de la base de dades perfecte |

Com que cada ruta persistent és un bind mount sota un sol directori, fer una còpia de memship és
copiar aquest directori:

```bash
sudo tar czf memship-$(date +%F).tar.gz \
    -C /srv/openmemship data \
    -C /srv/openmemship/app .env
```

Cal `sudo` perquè `data/postgres` és propietat de l'uid 70 amb mode `0700`: és Postgres que
protegeix els seus propis fitxers, no una configuració errònia.

### Fes-ho el mateix dia que instal·les

`install.sh` genera `SECRET_KEY` i `MEMSHIP_SECRET_KEY` al servidor, una sola vegada, a la primera
instal·lació. No es tornen a generar mai i no n'hi ha cap còpia enlloc més: ni al repositori, ni
als secrets de la teva CI, ni a cap bolcat. La instal·lació mostra un avís que ho diu; no mostra
els valors, perquè el mateix script s'executa des d'un pipeline de desplegament el registre del
qual pot ser públic.

Per tant, abans de posar-hi dades reals, treu `.env` del servidor i desa'l en algun lloc que
sobrevisqui al servidor:

```bash
scp -P <ssh-port> <user>@<host>:/srv/openmemship/app/.env  ~/memship-env-backup
```

Guarda'l en un gestor de contrasenyes, no només al teu portàtil, i dona-hi accés a un segon
administrador. Una recuperació que depèn de la màquina d'una sola persona s'encalla just quan la
necessites.

Això també s'aplica a un primer desplegament a través del pipeline: el pipeline crea `.env` al
servidor de la mateixa manera, i no en torna cap còpia.

> **Una còpia a nivell de fitxer de `data/postgres` mentre la base de dades s'executa no és
> consistent davant d'una fallada.** Per a una còpia fiable de la base de dades fes servir
> `db-backup.sh`, més avall, que executa `pg_dump` dins del contenidor. Fes servir la còpia amb
> `tar` per als fitxers pujats, els certificats i la configuració, o atura primer la pila si vols
> tot l'arbre en una sola presa consistent.

## Còpies de la base de dades

```bash
./scripts/db-backup.sh
```

El bolcat s'escriu a `$MEMSHIP_DATA_ROOT/backups/` com un `.sql.gz` amb marca de temps, amb mode
`600` i propietat del compte que executa l'script: és una còpia completa de les dades dels teus
socis, així que no es deixa llegible per a tothom. Els bolcats de més de 10 dies s'eliminen
automàticament.

Per a còpies desateses, programa-ho, per exemple cada nit a les 03:30:

```cron
30 3 * * *  cd /srv/openmemship/app && ./scripts/db-backup.sh
```

Així els bolcats queden al mateix disc que la base de dades. Per treure'ls també del servidor,
programa en canvi `push-backup.sh`, que fa el bolcat ell mateix: mira
[Còpies fora del servidor](#còpies-fora-del-servidor).

> L'script resol el directori de còpies a partir de `MEMSHIP_DATA_ROOT` a `.env`, de la mateixa
> manera que ho fa Compose, així que sempre escriu on apunta el muntatge `/backups` del contenidor
> `db`. Si mous l'arrel de dades, tant les còpies com l'script la segueixen, sense cap segon
> paràmetre per actualitzar.

## Restauració

L'script de restauració llista els bolcats disponibles i et deixa triar-ne un. Per defecte és
una **prova en sec** (dry-run), així que pots confirmar l'objectiu abans que res canviï:

```bash
./scripts/db-restore.sh            # dry-run: shows what would happen
./scripts/db-restore.sh --confirm  # actually restore, asking you to type a confirmation
```

Totes dues necessiten un terminal: tant el selector com la confirmació en llegeixen. Per a una
restauració executada des d'un script, una tasca de cron o un `ssh host '…'` no interactiu,
indica el bolcat i passa `--yes`:

```bash
./scripts/db-restore.sh --confirm --yes memship_20260819_141405.sql.gz
```

> **Restaurar sobreescriu la base de dades actual.** Comprova que apuntes a l'entorn que creus.

Abans d'eliminar res, l'script comprova que l'arxiu es pot llegir i que sembla un fitxer de
`pg_dump`, i bolca la base de dades actual a `memship_pre-restore_<timestamp>.sql.gz` al mateix
directori. Si després la restauració falla a mig camí, ho diu, surt amb un codi diferent de zero i
**deixa l'API aturada a propòsit**: arrencar-la executaria les migracions contra la base de dades
mig restaurada i et deixaria una instància que respon "healthy" i no conté res. Recupera el que
tenies amb el bolcat previ a la restauració que indica.

Un cop carregat el bolcat, l'script estableix la contrasenya de la base de dades a `DB_PASSWORD`
de `.env`, arrenca la pila i espera que l'API respongui abans de mostrar `Restore complete`.
Establir la contrasenya és important en un servidor nou: la seva base de dades es va crear amb la
contrasenya que va generar la nova instal·lació, mentre que el `.env` que restaures porta l'antiga,
i un `pg_dump` no conté contrasenyes. Si l'API no respon, l'script diu `RESTORE INCOMPLETE`, mostra
les darreres línies del registre de l'API i surt amb un codi diferent de zero. Les dades
restaurades es queden on són.

> Quan fallen diverses restauracions seguides, cadascuna escriu el seu propi bolcat previ, i el
> més recent és el que s'ha pres de la base de dades ja malmesa. Restaura el fitxer que indicava
> el missatge d'error, no el que sigui més recent.

## Restaurar en un servidor nou

1. Executa [`vps-bootstrap.sh` i `install.sh`](../getting-started/installation.md) com sempre.
2. Atura la pila: `docker compose down`.
3. Restaura `.env` des de la teva còpia, **l'antic, no el que s'acaba de generar.** Una
   `MEMSHIP_SECRET_KEY` nova no pot desxifrar les credencials d'SSO i dels proveïdors de pagament
   desades a la base de dades antiga.
4. Desempaqueta l'arrel de dades sobre la nova, conservant la propietat:
   `sudo tar xzf … -C /srv/openmemship`.
5. `docker compose up -d`, i després `./scripts/db-restore.sh --confirm` si restaures a partir
   d'un `pg_dump` i no de la còpia del directori.

## Còpies fora del servidor

El directori `backups/` és al mateix disc que la base de dades que protegeix, així que tot sol no
sobreviu a res pitjor que una migració fallida. Copia els bolcats a un altre lloc de manera
programada, emmagatzematge d'objectes, una altra màquina, qualsevol lloc amb una manera de fallar
diferent, o la pèrdua d'un sol servidor s'endurà la teva única còpia.

El mateix passa amb la instantània prèvia a l'actualització que pren el pipeline de desplegament:
`upgrade.sh` executa `db-backup.sh` abans d'aplicar una versió, però aquest bolcat va a parar a
`backups/` a la mateixa instància. Cobreix una migració fallida. No cobreix perdre la màquina, i
un registre de desplegament en verd no demostra que res hagi sortit de l'edifici.

### Enviar des del servidor

`scripts/push-backup.sh` s'executa a la instància. Fa un bolcat nou i envia una **instantània**
a una altra màquina:

```
memship-20261106T033000Z/
├── db.sql.gz    the pg_dump
├── env          .env: the keys that decrypt the credentials inside the dump
└── storage/     uploads, plus session.key and secret.key
```

Aquestes són les tres coses que no es poden reconstruir un cop el servidor ha desaparegut. No
copia `data/postgres`; el bolcat és la còpia consistent de la base de dades.

La destinació és `BACKUP_TARGET` a `.env`, o bé una màquina SSH o bé emmagatzematge d'objectes
compatible amb S3. Els paràmetres es detallen a [Configuració](configuration.md#còpies-de-seguretat-fora-del-servidor).

**Una instantània que existeix és sencera.** Per SSH, s'escriu com a `memship-<stamp>.partial` i
només es reanomena quan han arribat tots els fitxers; llavors `latest` hi apunta. A S3, l'últim
objecte que es puja és `COMPLETE`. Una execució que falla a mig camí deixa enrere una instantània
incompleta. La restauració la ignora, i una execució posterior l'elimina.

**Retenció.** Després d'un enviament correcte, les instantànies de més de `BACKUP_RETENTION_DAYS`
dies (per defecte 30) s'eliminen de la destinació. Això és independent dels 10 dies de bolcats
que es conserven localment a `backups/`.

**Els errors fan soroll.** Qualsevol error surt amb un codi diferent de zero i mostra
`PUSH FAILED`, juntament amb què s'ha fet i què no, perquè una còpia que s'ha aturat no es
confongui amb una que funciona.

#### A una altra màquina per SSH

La màquina de còpies necessita un usuari amb shell i `rsync`. Res més, i sense root.

1. A la instància, crea una clau que només es faci servir per a les còpies:
   ```bash
   ssh-keygen -t ed25519 -N "" -f ~/.ssh/memship-backup
   ```
2. A la màquina de còpies, afegeix `~/.ssh/memship-backup.pub` al `~/.ssh/authorized_keys`
   d'aquest usuari.
3. Des de la instància, connecta't una vegada per acceptar la clau de la màquina. L'script
   executa SSH en mode batch, així que mai respondrà aquesta pregunta per tu:
   ```bash
   ssh -i ~/.ssh/memship-backup backup@backup.example.org true
   ```
4. A `.env`:
   ```bash
   BACKUP_TARGET=ssh://backup@backup.example.org/srv/memship-backups
   BACKUP_SSH_KEY=/home/deploy/.ssh/memship-backup
   ```
   Afegeix un port quan no sigui el 22: `ssh://backup@backup.example.org:2222/srv/memship-backups`.

Els fitxers pujats que no han canviat s'enllacen amb enllaços durs (hard links) a la instantània
anterior en lloc d'enviar-los i desar-los de nou. Per tant, un mes d'instantànies costa una còpia
de `storage/` més el que hagi canviat.

#### A emmagatzematge d'objectes compatible amb S3

Funciona amb AWS S3 i qualsevol emmagatzematge compatible (MinIO, Backblaze B2, Wasabi, OVH,
Scaleway…). Executa la imatge oficial `amazon/aws-cli` a través de Docker, que ja és al servidor,
així que no cal instal·lar res.

1. Crea un bucket, i una clau d'accés que pugui pujar, llistar i eliminar objectes sota el prefix
   que faràs servir, i res més.
2. A `.env`:
   ```bash
   BACKUP_TARGET=s3://club-backups/memship
   BACKUP_S3_ACCESS_KEY_ID=…
   BACKUP_S3_SECRET_ACCESS_KEY=…
   BACKUP_S3_REGION=eu-west-1
   # Only for a store that is not AWS:
   BACKUP_S3_ENDPOINT=https://s3.eu-central-003.backblazeb2.com
   ```

El secret arriba al contenidor a través de l'entorn, mai en una línia d'ordres.

#### Programa-ho

`push-backup.sh` fa el seu propi bolcat, així que substitueix la línia nocturna de
`db-backup.sh` en lloc d'executar-se al seu costat:

```cron
MAILTO=admin@example.org
30 3 * * *  cd /srv/openmemship/app && ./scripts/push-backup.sh
```

`MAILTO` només t'arriba si el servidor pot enviar correu. Un servei de check-in és més fiable.
T'avisa quan el ping **deixa** d'arribar, cosa que també cobreix que el mateix cron no
s'executi:

```cron
30 3 * * *  cd /srv/openmemship/app && ./scripts/push-backup.sh && curl -fsS https://hc-ping.com/<your-uuid>
```

> **El que envies ho conté tot.** `env` guarda les claus i `db.sql.gz` guarda tots els registres
> de socis. Memship no xifra les instantànies. Dona a la destinació la mateixa protecció que al
> servidor: un usuari o una clau dedicats, cap accés públic al bucket i xifratge al costat del
> servidor al bucket quan l'emmagatzematge l'ofereixi.

### Restaurar des d'una instantània enviada

Fes servir una instantània completa: per SSH, aquella a la qual apunta `latest` (o qualsevol
directori que no acabi en `.partial`); a S3, una que contingui `COMPLETE`.

1. Instal·la un servidor nou com a [Restaurar en un servidor nou](#restaurar-en-un-servidor-nou),
   passos 1–2.
2. Porta-hi la instantània:
   ```bash
   # SSH
   rsync -a backup@backup.example.org:/srv/memship-backups/latest/ ~/restore/
   # S3, using the same image the push used
   docker run --rm -v ~/restore:/restore -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY \
       amazon/aws-cli:2.27.0 s3 cp --recursive s3://club-backups/memship/memship-<stamp>/ /restore/
   ```
3. Torna a posar les peces al seu lloc. `.env` va primer, perquè sense ell la base de dades no es
   pot llegir:
   ```bash
   cp ~/restore/env /srv/openmemship/app/.env
   rsync -a ~/restore/storage/ /srv/openmemship/data/storage/
   cp ~/restore/db.sql.gz /srv/openmemship/data/backups/memship_<YYYYMMDD_HHMMSS>.sql.gz
   ```
   Posa al bolcat el nom de la instantània. Qualsevol nom que comenci per `memship_` funciona.
   Per a un emmagatzematge que no sigui AWS, afegeix `--endpoint-url <BACKUP_S3_ENDPOINT>` després
   del nom de la imatge al `docker run`.
4. `docker compose up -d db`, després
   `./scripts/db-restore.sh --confirm --yes memship_<YYYYMMDD_HHMMSS>.sql.gz`, i després
   `docker compose up -d`.

Fes-ho una vegada contra un servidor de proves abans de confiar-hi.

### Descarregar des de la teva pròpia màquina

`scripts/pull-backup.sh` és el contrari: s'executa a la teva estació de treball i descarrega des
del servidor. Fes-lo servir quan el servidor no hagi de tenir credencials de res més.

```bash
./scripts/pull-backup.sh <ssh-host> --dump              # fresh dump, then fetch .env + dumps
./scripts/pull-backup.sh <ssh-host> --with-data         # also uploads and TLS certificates
```

No necessita root a cap de les dues màquines, i se salta `data/postgres` pel mateix motiu. No té
programació ni retenció pròpies: executa'l des de cron en una màquina que estigui sempre
engegada, i apunta `--dest` a un emmagatzematge que tingui, al seu torn, còpia de seguretat.
