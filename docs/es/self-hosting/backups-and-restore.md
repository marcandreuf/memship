<!-- source: en/self-hosting/backups-and-restore.md -->
<!-- source-hash: 1349a9eb7e59 -->

# Copias de seguridad y restauración

Configura las copias de seguridad **antes** de ponerte en marcha, y prueba una restauración al
menos una vez. Una copia de seguridad que nunca has restaurado es una suposición, no una copia de
seguridad.

> **En inglés:** [Backups & restore](../../en/self-hosting/backups-and-restore.md).
> **En català:** [Còpies de seguretat i restauració](../../ca/self-hosting/backups-and-restore.md).

## Qué copiar

Dos cosas, y necesitas las dos:

| Qué | Por qué |
|---|---|
| **La raíz de datos** (`MEMSHIP_DATA_ROOT`, p. ej. `/srv/openmemship/data`) | La base de datos, los archivos subidos, `secret.key`, `session.key`, los certificados TLS, todo lo que tiene que sobrevivir |
| **`.env`** | Los secretos que se generaron. Perder `SECRET_KEY` y `MEMSHIP_SECRET_KEY` es perder el acceso a los datos cifrados aunque tengas un volcado perfecto de la base de datos |

Como todas las rutas persistentes son montajes bind bajo un mismo directorio, hacer una copia de
seguridad de memship es copiar ese directorio:

```bash
sudo tar czf memship-$(date +%F).tar.gz \
    -C /srv/openmemship data \
    -C /srv/openmemship/app .env
```

Hace falta `sudo` porque `data/postgres` pertenece al uid 70 y tiene el modo `0700`: es Postgres
protegiendo sus propios archivos, no un error de configuración.

### Hazlo el mismo día de la instalación

`install.sh` genera `SECRET_KEY` y `MEMSHIP_SECRET_KEY` en el servidor, una sola vez, en la primera
instalación. No se regeneran nunca y no existe ninguna copia en ningún otro sitio: ni en el
repositorio, ni en los secretos de tu CI, ni en ningún volcado. La instalación muestra un aviso que
lo dice; no muestra los valores, porque el mismo script se ejecuta desde un pipeline de despliegue
cuyo log puede ser público.

Así que, antes de meter datos reales, saca `.env` del servidor y guárdalo en algún sitio que
sobreviva al servidor:

```bash
scp -P <ssh-port> <user>@<host>:/srv/openmemship/app/.env  ~/memship-env-backup
```

Guárdalo en un gestor de contraseñas, no solo en tu portátil, y da acceso a un segundo
administrador. Una recuperación que depende del ordenador de una sola persona se atasca justo
cuando la necesitas.

Esto vale también para un primer despliegue a través del pipeline: el pipeline crea `.env` en el
servidor de la misma forma, y no copia nada de vuelta.

> **Una copia a nivel de archivos de `data/postgres` con la base de datos en marcha no es
> consistente ante una caída.** Para una copia de la base de datos fiable usa `db-backup.sh`, más
> abajo, que ejecuta `pg_dump` dentro del contenedor. Usa la copia con `tar` para los archivos
> subidos, los certificados y la configuración, o para antes el stack si quieres todo el árbol en
> una sola copia consistente.

## Copias de la base de datos

```bash
./scripts/db-backup.sh
```

El volcado se escribe en `$MEMSHIP_DATA_ROOT/backups/` como un `.sql.gz` con marca de tiempo, con
modo `600` y como propietaria la cuenta que ejecuta el script: es una copia completa de los datos
de tus socios, así que no se deja legible para todos. Los volcados de más de 10 días se borran
automáticamente.

Para copias desatendidas, prográmalo, por ejemplo cada noche a las 03:30:

```cron
30 3 * * *  cd /srv/openmemship/app && ./scripts/db-backup.sh
```

Eso deja los volcados en el mismo disco que la base de datos. Para sacarlos además del servidor,
programa en su lugar `push-backup.sh`, que hace el volcado por sí mismo: ver
[Copias fuera del servidor](#copias-fuera-del-servidor).

> El script obtiene el directorio de copias a partir de `MEMSHIP_DATA_ROOT` en `.env`, igual que
> hace Compose, así que siempre escribe donde apunta el montaje `/backups` del contenedor `db`. Si
> mueves la raíz de datos, tanto las copias como el script la siguen, sin un segundo ajuste que
> actualizar.

## Restaurar

El script de restauración lista los volcados disponibles y te deja elegir uno. **Por defecto es
una simulación (dry-run)**, así que puedes confirmar el destino antes de que cambie nada:

```bash
./scripts/db-restore.sh            # dry-run: shows what would happen
./scripts/db-restore.sh --confirm  # actually restore, asking you to type a confirmation
```

Las dos necesitan un terminal: tanto el selector como la confirmación leen de uno. Para una
restauración lanzada desde un script, un trabajo de cron o un `ssh host '…'` no interactivo, indica
el volcado y pasa `--yes`:

```bash
./scripts/db-restore.sh --confirm --yes memship_20260819_141405.sql.gz
```

> **Restaurar sobrescribe la base de datos actual.** Comprueba que estás apuntando al entorno que
> crees.

Antes de borrar nada, el script comprueba que el archivo se puede leer y que parece un fichero de
`pg_dump`, y vuelca la base de datos actual a `memship_pre-restore_<timestamp>.sql.gz` en el mismo
directorio. Si después la restauración falla a medias, lo dice, sale con un código distinto de cero
y **deja la API parada a propósito**: arrancarla ejecutaría las migraciones contra la base de datos
restaurada a medias y te dejaría con una instancia que responde "healthy" y no contiene nada.
Recupera lo que tenías con el volcado previo a la restauración que indica.

Una vez cargado el volcado, el script pone como contraseña de la base de datos `DB_PASSWORD` de
`.env`, arranca el stack y espera a que la API responda antes de mostrar `Restore complete`.
Establecer la contraseña importa en un servidor nuevo: su base de datos se creó con la contraseña
que generó la nueva instalación, mientras que el `.env` que restauras lleva la antigua, y un
`pg_dump` no contiene contraseñas. Si la API no responde, el script dice `RESTORE INCOMPLETE`,
muestra las últimas líneas del log de la API y sale con un código distinto de cero. Los datos
restaurados se quedan en su sitio.

> Cuando fallan varias restauraciones seguidas, cada una escribe su propio volcado previo, y el más
> reciente es el que se tomó de la base de datos ya dañada. Restaura el archivo que indicó el
> mensaje de error, no el que sea más reciente.

## Restaurar en un servidor nuevo

1. Ejecuta [`vps-bootstrap.sh` e `install.sh`](../../en/getting-started/installation.md) _(en
   inglés)_ de la forma habitual.
2. Para el stack: `docker compose down`.
3. Restaura `.env` desde tu copia, **el antiguo, no el que se acaba de generar.** Una
   `MEMSHIP_SECRET_KEY` nueva no puede descifrar las credenciales de SSO y de los proveedores de
   pago guardadas en la base de datos antigua.
4. Desempaqueta la raíz de datos encima de la nueva, conservando los propietarios:
   `sudo tar xzf … -C /srv/openmemship`.
5. `docker compose up -d`, y después `./scripts/db-restore.sh --confirm` si estás restaurando desde
   un `pg_dump` y no desde la copia del directorio.

## Copias fuera del servidor

El directorio `backups/` está en el mismo disco que la base de datos que protege, así que por sí
solo no sobrevive a nada peor que una mala migración. Copia los volcados a otro sitio de forma
programada (almacenamiento de objetos, otra máquina, cualquier lugar con un modo de fallo
distinto), o perder un solo servidor se llevará tu única copia.

Lo mismo vale para la instantánea previa a la actualización que toma el pipeline de despliegue:
`upgrade.sh` ejecuta `db-backup.sh` antes de aplicar una versión, pero ese volcado acaba en
`backups/` en la instancia. Cubre una migración fallida. No cubre perder la máquina, y un log de
despliegue en verde no demuestra que nada haya salido del edificio.

### Enviar desde el servidor

`scripts/push-backup.sh` se ejecuta en la instancia. Hace un volcado nuevo y envía una
**instantánea** a otra máquina:

```
memship-20261106T033000Z/
├── db.sql.gz    the pg_dump
├── env          .env: the keys that decrypt the credentials inside the dump
└── storage/     uploads, plus session.key and secret.key
```

Esas son las tres cosas que no se pueden reconstruir una vez que el servidor ha desaparecido. No
copia `data/postgres`; el volcado es la copia consistente de la base de datos.

El destino es `BACKUP_TARGET` en `.env`: una máquina por SSH o un almacenamiento de objetos
compatible con S3. Los ajustes están en la [Configuración](configuration.md#copias-de-seguridad-fuera-del-servidor).

**Una instantánea que existe está entera.** Por SSH se escribe como `memship-<stamp>.partial` y se
renombra solo cuando han llegado todos los archivos; después `latest` apunta a ella. En S3 se sube
al final un objeto `COMPLETE`. Una ejecución que falla a medias deja atrás una instantánea
incompleta. La restauración la ignora, y una ejecución posterior la borra.

**Retención.** Tras un envío correcto, las instantáneas de más de `BACKUP_RETENTION_DAYS` (30 por
defecto) se borran del destino. Esto es independiente de los 10 días de volcados que se guardan en
local en `backups/`.

**Los fallos se notan.** Cualquier error sale con un código distinto de cero y muestra
`PUSH FAILED`, junto con lo que se hizo y lo que no, para que una copia que se ha parado no se
confunda con una que funciona.

#### A otra máquina por SSH

La máquina de copias necesita un usuario con shell y `rsync`. Nada más, y sin root.

1. En la instancia, crea una clave que se use solo para las copias:
   ```bash
   ssh-keygen -t ed25519 -N "" -f ~/.ssh/memship-backup
   ```
2. En la máquina de copias, añade `~/.ssh/memship-backup.pub` al `~/.ssh/authorized_keys` de ese
   usuario.
3. Desde la instancia, conéctate una vez para aceptar la clave del host. El script ejecuta SSH en
   modo batch, así que nunca responderá a esa pregunta por ti:
   ```bash
   ssh -i ~/.ssh/memship-backup backup@backup.example.org true
   ```
4. En `.env`:
   ```bash
   BACKUP_TARGET=ssh://backup@backup.example.org/srv/memship-backups
   BACKUP_SSH_KEY=/home/deploy/.ssh/memship-backup
   ```
   Añade un puerto cuando no sea el 22: `ssh://backup@backup.example.org:2222/srv/memship-backups`.

Los archivos subidos que no han cambiado se enlazan con enlaces duros a la instantánea anterior en
vez de enviarse y guardarse otra vez. Por eso un mes de instantáneas cuesta una copia de `storage/`
más lo que haya cambiado.

#### A un almacenamiento de objetos compatible con S3

Funciona con AWS S3 y con cualquier almacenamiento compatible (MinIO, Backblaze B2, Wasabi, OVH,
Scaleway…). Ejecuta la imagen oficial `amazon/aws-cli` a través de Docker, que ya está en el
servidor, así que no hay que instalar nada.

1. Crea un bucket, y una clave de acceso con permiso para subir, listar y borrar objetos bajo el
   prefijo que vayas a usar, y nada más.
2. En `.env`:
   ```bash
   BACKUP_TARGET=s3://club-backups/memship
   BACKUP_S3_ACCESS_KEY_ID=…
   BACKUP_S3_SECRET_ACCESS_KEY=…
   BACKUP_S3_REGION=eu-west-1
   # Only for a store that is not AWS:
   BACKUP_S3_ENDPOINT=https://s3.eu-central-003.backblazeb2.com
   ```

El secreto llega al contenedor a través del entorno, nunca en una línea de órdenes.

#### Prográmalo

`push-backup.sh` hace su propio volcado, así que sustituye a la línea nocturna de `db-backup.sh` en
vez de ejecutarse junto a ella:

```cron
MAILTO=admin@example.org
30 3 * * *  cd /srv/openmemship/app && ./scripts/push-backup.sh
```

`MAILTO` solo te llega si el servidor puede enviar correo. Un servicio de check-in es más fiable.
Te avisa cuando el ping **deja** de llegar, lo que cubre también que el propio cron no se ejecute:

```cron
30 3 * * *  cd /srv/openmemship/app && ./scripts/push-backup.sh && curl -fsS https://hc-ping.com/<your-uuid>
```

> **Lo que envías lo contiene todo.** `env` guarda las claves y `db.sql.gz` guarda todos los
> registros de socios. memship no cifra las instantáneas. Dale al destino la misma protección que
> al servidor: un usuario o una clave dedicados, ningún acceso público al bucket y cifrado del lado
> del servidor en el bucket allí donde el almacenamiento lo ofrezca.

### Restaurar desde una instantánea enviada

Usa una instantánea completa: por SSH, aquella a la que apunta `latest` (o cualquier directorio
que no termine en `.partial`); en S3, una que contenga `COMPLETE`.

1. Instala un servidor nuevo como en [Restaurar en un servidor nuevo](#restaurar-en-un-servidor-nuevo),
   pasos 1–2.
2. Trae la instantánea a él:
   ```bash
   # SSH
   rsync -a backup@backup.example.org:/srv/memship-backups/latest/ ~/restore/
   # S3, using the same image the push used
   docker run --rm -v ~/restore:/restore -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY \
       amazon/aws-cli:2.27.0 s3 cp --recursive s3://club-backups/memship/memship-<stamp>/ /restore/
   ```
3. Vuelve a poner las piezas en su sitio. `.env` va primero, porque sin él la base de datos no se
   puede leer:
   ```bash
   cp ~/restore/env /srv/openmemship/app/.env
   rsync -a ~/restore/storage/ /srv/openmemship/data/storage/
   cp ~/restore/db.sql.gz /srv/openmemship/data/backups/memship_<YYYYMMDD_HHMMSS>.sql.gz
   ```
   Pon al volcado el nombre de la instantánea. Vale cualquier nombre que empiece por `memship_`.
   Para un almacenamiento que no sea AWS, añade `--endpoint-url <BACKUP_S3_ENDPOINT>` después del
   nombre de la imagen en el `docker run`.
4. `docker compose up -d db`, después
   `./scripts/db-restore.sh --confirm --yes memship_<YYYYMMDD_HHMMSS>.sql.gz`, y después
   `docker compose up -d`.

Haz esto una vez contra un servidor de pruebas antes de confiar en ello.

### Traer desde tu propia máquina

`scripts/pull-backup.sh` es lo contrario: se ejecuta en tu estación de trabajo y trae los datos
desde el servidor. Úsalo cuando el servidor no deba tener credenciales de nada más.

```bash
./scripts/pull-backup.sh <ssh-host> --dump              # fresh dump, then fetch .env + dumps
./scripts/pull-backup.sh <ssh-host> --with-data         # also uploads and TLS certificates
```

No necesita root en ninguna de las dos máquinas, y se salta `data/postgres` por el mismo motivo.
No tiene programación ni retención propias: ejecútalo desde cron en una máquina que esté siempre
encendida, y apunta `--dest` a un almacenamiento que a su vez tenga copia de seguridad.
