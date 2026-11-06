<!-- source: en/self-hosting/troubleshooting.md -->
<!-- source-hash: beba2acfbaab -->

# Resolución de problemas

Síntomas con los que de verdad se encuentra quien administra el servidor, y qué los causa. Si algo
de aquí está mal o falta, [abre una incidencia](https://github.com/marcandreuf/memship/issues):
esta página sale de instalaciones reales, no de la teoría.

> **En inglés:** [Troubleshooting](../../en/self-hosting/troubleshooting.md).
> **En català:** [Resolució de problemes](../../ca/self-hosting/troubleshooting.md).

Antes de nada, dos órdenes que vale la pena ejecutar:

```bash
docker compose ps                       # what is up, and what is restarting
curl -s http://localhost/api/v1/health  # {"status":"healthy","version":"2.19.0",...}
```

`version` es la etiqueta de imagen que tienes. Si pone `latest`, tienes una instalación sin versión
fijada y no puedes saber qué está en marcha: fíjala con `./scripts/upgrade.sh <version>`, que
comprueba la versión contra tus datos antes de reemplazar nada. `install.sh` se niega a ejecutarse
sobre una instancia que ya está levantada, precisamente para que esa comprobación no se salte.

## La plataforma no arranca

### `Conflict. The container name "/memship-db" is already in use`

Ya hay otra instancia de memship en marcha en esta máquina. El fichero de Compose da nombre
explícito a sus contenedores, y esos nombres son globales en el demonio de Docker, así que una
segunda copia choca aunque esté en otro directorio, con otro directorio de datos y con otro nombre
de proyecto de Compose.

```bash
docker ps -a --filter name=memship-      # find the other instance
```

Ejecuta la segunda instancia en otra máquina o en una máquina virtual. Si la otra está muerta y
quieres recuperar su nombre, borra con `docker rm` los contenedores que hayan quedado.

### Los contenedores se reinician en bucle y los logs dicen permission denied

Casi siempre es el directorio de datos. Docker crea **como root** el origen de un bind mount que no
existe, y el backend se ejecuta con tu uid, así que no puede escribir en un directorio que Docker
ha creado por él:

```bash
ls -l "$MEMSHIP_DATA_ROOT"     # storage/ and celerybeat/ should be yours, postgres/ uid 70
sudo chown -R "$(id -u):$(id -g)" "$MEMSHIP_DATA_ROOT"/{storage,celerybeat,caddy,backups}
```

`postgres/` es distinto: modo `0700` y propiedad del uid 70, que tú no puedes leer. Eso es lo
correcto: la base de datos se lee con `./scripts/db-backup.sh`, no con `ls`.

Si actualizas desde una versión en la que el backend se ejecutaba como root, mira la nota de
[Actualización](upgrading.md).

### Una migración se negó a ejecutarse y la API no arranca

Después de una actualización, `verify-deployment.sh` falla y la API no responde nunca.
`docker compose ps` muestra `api` reiniciándose, y sus logs terminan en un informe, no en una traza
de pila que tengas que interpretar:

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

**Es deliberado, no una versión rota.** Algunas migraciones inspeccionan los datos antes de
cambiarlos y se detienen cuando encuentran algo que solo una persona debe decidir. La
comprobación no ha escrito nada, así que la base de datos está exactamente como estaba. **No
restaures la instantánea previa a la actualización**: no hay nada que deshacer, y al restaurarla
pierdes todo lo escrito desde que se tomó.

Si el informe se te ha pasado, vuelve a leerlo con:

```bash
docker compose logs api --tail 40
```

**Arréglalo cambiando una fila, no borrándola.** Borrar la cuenta duplicada es lo evidente y lo
equivocado: `members.user_id` es `ON DELETE SET NULL`, así que eliminar la cuenta desvincula la
ficha de socio de esa persona y no deja forma de volver a conectarla, y si la cuenta lanzó alguna
vez una facturación o creó un anuncio, el borrado falla directamente por una clave foránea.

Elige la cuenta que vas a retirar con las anotaciones del informe (cuándo inició sesión por
última vez, si tiene ficha de socio) y dale otra dirección:

```bash
docker compose exec -T db psql -U memship -d memship_db \
  -c "UPDATE users SET email = 'retired-35-' || email WHERE id = 35;"
```

Es reversible, no toca nada más y satisface la comprobación. Después deja que la migración se
ejecute:

```bash
docker compose restart api
./scripts/verify-deployment.sh "$MEMSHIP_VERSION"
```

Cuando la instancia vuelva a estar en marcha, resuelve el duplicado como es debido en
**Configuración → Cuentas**, donde puedes ver las dos cuentas y desactivar o cambiar la dirección
de la que no quieras. Hacerlo ahí y no en SQL hace que el cambio quede auditado.

Si el informe nombra más cuentas de las que puedes resolver rápido, ten en cuenta que la instancia
sigue caída todo ese tiempo: la comprobación se ejecuta después de que se haya reemplazado la
plataforma. Adelantarla es la [incidencia #194](https://github.com/marcandreuf/memship/issues/194).

### Postgres no arranca en RHEL, Fedora, Rocky o AlmaLinux

SELinux. Los bind mounts necesitan reetiquetado, mira la sección de SELinux de la
[Instalación](../../en/getting-started/installation.md) _(en inglés)_.

### `port is already allocated`

Otra cosa está ocupando el 80 o el 443:

```bash
sudo ss -ltnp | grep -E ':(80|443)\b'
```

Detenla, o define `HTTP_PORT` / `HTTPS_PORT` en `.env` y vuelve a crear los contenedores. Ten en
cuenta que el HTTPS automático necesita el puerto 80 accesible desde internet: Let's Encrypt valida
por HTTP-01.

## Está en marcha pero no consigo acceder

**Comprueba desde dónde miras.** Todas las URL `localhost` de la documentación son *desde el
servidor*. La API y la base de datos están ligadas a `127.0.0.1` a propósito, así que desde tu
portátil solo se llega al frontend y a `/api/...` a través del proxy, en el dominio o la IP del
servidor.

**`ufw` no limita a Docker.** Docker escribe sus reglas de iptables por delante de las del
cortafuegos, así que un puerto publicado en `0.0.0.0` sigue accesible desde internet aunque `ufw`
lo deniegue. Compruébalo desde otra máquina en vez de fiarte de `ufw status`:

```bash
nmap -Pn -p 22,80,443,5433,8003 your-host
```

El 8003 y el 5433 deben estar cerrados. Si están abiertos, algo ha puesto `API_BIND` o `DB_BIND` a
`0.0.0.0`, o ha añadido una entrada `ports:`.

## HTTPS y certificados

### No se emite ningún certificado

Caddy valida por HTTP-01, así que el nombre de máquina ya tiene que resolver a este servidor y el
puerto 80 tiene que estar abierto. `install.sh` se niega a arrancar cuando el DNS no coincide,
porque las validaciones fallidas tienen un límite de 5 por nombre de máquina y hora.

### "Too many certificates already issued"

Let's Encrypt permite **5 certificados por semana para el mismo conjunto de nombres de máquina**.
El certificado emitido vive en `<data-root>/caddy/data`; borrar ese directorio, como hace un
desmontaje completo, hace que el siguiente arranque pida un certificado *nuevo* en vez de renovar.
Conserva `caddy/data` entre reconstrucciones, y ensaya las instalaciones sin `--domain`.

### Faltan las cabeceras de seguridad después de una actualización

El `Caddyfile` va montado con bind mount, así que cambiar su contenido no cambia la configuración
del contenedor en marcha, y `docker compose up -d` no ve motivo para volver a crearlo:

```bash
docker compose ps caddy                          # "Up 3 days" after an upgrade is the tell
docker compose up -d --force-recreate caddy
curl -sI https://your-host/api/v1/health | grep -i -E 'content-security|x-frame|strict-transport'
```

Comprueba las cabeceras en una ruta de la **API**, no solo en la portada. El frontend pone algunas
por su cuenta, así que `/` puede parecer protegida mientras todas las respuestas de la API van sin
ellas.

## Configuración inicial e inicio de sesión

### `--admin-email needs the password in MEMSHIP_ADMIN_PASSWORD`

`docker compose exec` no pasa el entorno de tu shell al contenedor. Nombra la variable después de
`-e`:

```bash
MEMSHIP_ADMIN_PASSWORD='...' docker compose exec -T -e MEMSHIP_ADMIN_PASSWORD \
  api python -m app.cli.seed --admin-email you@example.org
```

### Nadie puede iniciar sesión / se ha perdido la contraseña del superadministrador

Restablécela desde la máquina con la misma orden. Es a propósito la única forma de entrar: no hay
recuperación por la interfaz web para un superadministrador, y cada restablecimiento se escribe en
el registro de auditoría sin usuario que lo haga, ya que quien lo ejecutó tenía acceso a la shell.

### Un socio no puede iniciar sesión: "Confirm your email address before signing in"

Para iniciar sesión hace falta una dirección confirmada, así que una cuenta que nunca siguió su
enlace de confirmación se queda fuera. Lo normal es que pida un enlace nuevo desde la página de
inicio de sesión, pero para eso hace falta un transporte de correo que funcione, y un transporte de
correo que llevaba tiempo fallando sin avisar es el motivo habitual de que la dirección no se
confirmara en su momento.

En su lugar, confírmala desde la máquina, una vez sepas quién es la persona:

```bash
docker compose exec -T api python -m app.cli.verify_email --list
docker compose exec -T api python -m app.cli.verify_email --email member@example.org
```

`--list` muestra todas las cuentas en esta situación, y es también la forma más rápida de saber si
el envío de correo lleva tiempo roto. Después de arreglar el envío puedes despachar la cola
pendiente de una vez:

```bash
docker compose exec -T api python -m app.cli.verify_email --all-unverified --yes
```

Eso confirma direcciones **sin que nadie demuestre que son suyas**, y por eso exige `--yes`. Úsalo
cuando sepas que las cuentas son auténticas y que el problema era el correo; usa `--email` de una
en una cuando no estés seguro.

La orden no envía nada nunca: es para el caso en que lo que está roto es el envío.

### `SECRET_KEY` sigue con el valor de ejemplo

La clave de ejemplo que viene en `.env.example` y el valor por defecto de Compose están publicados
en este repositorio, y firman el token de sesión, el HMAC del QR del carné de socio y el estado de
OAuth. Por eso el servidor trata una clave de ejemplo como si no hubiera ninguna: genera una y la
guarda en `storage/session.key`, igual que cuando `SECRET_KEY` está vacía. Nada falla mientras ese
archivo se conserve. Definirla explícitamente es lo que permite que una máquina reconstruida, o
un directorio de datos perdido, mantenga las sesiones activas:

```bash
openssl rand -hex 32
```

## Copias de seguridad y restauración

### Una restauración ha fallado

El script deja la API detenida a propósito. Arrancarla ejecutaría las migraciones contra la base de
datos a medio restaurar y te daría una instancia que responde `"healthy"` y no contiene nada.

Restaura el volcado previo a la restauración que nombra el mensaje de error, no simplemente el más
reciente, que tras un segundo intento fallido es una copia de la base de datos ya dañada.

### Una restauración dice que no hay terminal

El selector de copias y la confirmación escrita necesitan uno. Desde un script o desde cron, nombra
el volcado y pasa `--yes`:

```bash
./scripts/db-restore.sh --confirm --yes memship_20260819_141405.sql.gz
```

### "Restore complete" pero los datos han desaparecido

Las versiones anteriores a la 2.3.0 podían informar de éxito tras una restauración fallida: `psql`
se ejecutaba sin `ON_ERROR_STOP`, así que un volcado corrupto o truncado vaciaba la base de datos y
aun así mostraba un resultado en verde. Actualiza y vuelve a probar tus restauraciones. Una copia
de seguridad que nunca has restaurado es una suposición.

## Logs

```bash
docker compose logs -f api             # backend, including migrations on startup
docker compose logs -f celery-worker   # scheduled jobs and email sending
docker compose logs -f caddy           # TLS issuance and proxying
docker compose logs --since 10m        # everything, recent
```

Celery es el componente que falla sin hacer ruido: si los recordatorios o los correos dejan de
salir, mira ahí primero.
