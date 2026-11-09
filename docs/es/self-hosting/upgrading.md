<!-- source: en/self-hosting/upgrading.md -->
<!-- source-hash: 66ec9ee88995 -->

# Actualizar

Memship se publica como imágenes de Docker con versión, más un puñado de archivos que viven a su
lado: el archivo de Compose, la configuración de Caddy, los scripts. Actualizar consiste en
refrescar las dos cosas y después ejecutar una orden que hace la copia de seguridad, aplica la
versión y la verifica. Las migraciones de la base de datos se ejecutan automáticamente al arrancar.

> **En inglés:** [Upgrading](../../en/self-hosting/upgrading.md).
> **En català:** [Actualitzar](../../ca/self-hosting/upgrading.md).

## Versionado

Memship sigue el [versionado semántico](https://semver.org/). **Las etiquetas de git son la única
fuente de verdad** de la versión: no hay archivo `VERSION`. Las imágenes publicadas se etiquetan
con la versión de la release (p. ej. `2.19.0`) y con `latest`.

Cada instalación queda fijada a una versión en vez de seguir `latest`, así que las actualizaciones
son deliberadas y una instancia puede decir qué release ejecuta. La guarda `IMAGE_TAG` en `.env`;
`install.sh --tag` y `upgrade.sh` la escriben por ti, y `/api/v1/health` la devuelve:

```bash
curl -s http://127.0.0.1:8003/api/v1/health
{"status":"healthy","version":"2.19.0","environment":"production"}
```

## Procedimiento de actualización

**Revisa primero las notas de la release** de la versión de destino: los cambios incompatibles y
los ajustes obligatorios nuevos se indican ahí, en la
[página de releases](https://github.com/marcandreuf/memship/releases).

Después, dos órdenes. Refresca los archivos de despliegue y luego aplica la versión:

```bash
MEMSHIP_VERSION=3.2.0
MEMSHIP_APP=/srv/openmemship/app          # wherever your install lives

curl -fsSL "https://github.com/marcandreuf/memship/archive/refs/tags/v${MEMSHIP_VERSION}.tar.gz" \
  | tar -xz -C "$MEMSHIP_APP" --strip-components=1

cd "$MEMSHIP_APP"
./scripts/upgrade.sh "$MEMSHIP_VERSION"
```

**Por qué la primera orden.** Parte de una release se distribuye junto a las imágenes y no dentro
de ellas: `docker-compose.yml`, el `Caddyfile`, `scripts/`. Subir solo `IMAGE_TAG` deja una
instalación actualizada a medias: el backend nuevo funcionando detrás de la configuración antigua
del proxy. Desempaquetar encima del directorio sustituye esos archivos y deja `.env` intacto, ya
que `.env` no está en el archivo. No intervienen ni git ni una copia del código fuente.

`tar -xz` escribe en su directorio `-C`, así que indícalo en vez de fiarte del directorio actual
del shell: un `curl | tar` pegado suelto, sin el `cd`, desempaqueta una release allí donde estés y
no dice nada. Ten en cuenta también que desempaquetar *añade y sustituye*; nunca borra, así que un
archivo que una release haya eliminado se queda ahí hasta que lo borres tú.

**No tienes que acordarte de este paso.** `upgrade.sh` lo comprueba, ver el paso 5 más abajo.

**Lo que hace la segunda**, por orden, deteniéndose si falla cualquier paso. Los pasos 1 a 7 se
ejecutan todos **antes de sustituir nada en la instancia**, así que si cualquiera de ellos se
detiene, la versión en la que estabas sigue dando servicio, y cada rechazo indica el estado que ha
encontrado:

1. **Se niega a ir hacia atrás.** Volver a fijar `IMAGE_TAG` hace retroceder las imágenes pero no
   el esquema, así que una release más antigua se encuentra con una base de datos que no entiende.
   En su lugar, restaura la instantánea tomada antes de actualizar, ver
   [Volver atrás](#volver-atrás). Si sabes que la release que dejas no traía ninguna migración, o
   ya has restaurado la base de datos, `--allow-downgrade` sigue adelante. Solo se compara entre
   dos versiones de release: una instalación RC o `latest` no tiene un orden sobre el que razonar,
   así que se deja tal cual en vez de suponer.

2. **Comprueba que `.env` lleva lo que la release espera.** Compara los ajustes de tu `.env` con
   los que el instalador de esta release escribe en un `.env` que crea. Un `.env` escrito por la
   misma release los tiene todos, así que en una instancia al día no dice nada; en una más antigua
   indica lo que se ha añadido desde entonces, que es el párrafo de las notas de la release que
   quizá no hayas leído.

   Solo uno de ellos detiene la actualización: **un `.env` sin ninguna línea `IMAGE_TAG`.** Aplicar
   una versión reescribe esa línea en su sitio, y no hay nada que reescribir, así que la etiqueta se
   aceptaría, se perdería y el stack arrancaría con aquello a lo que apunte `latest`. Añade la línea
   y vuelve a ejecutarlo.

3. **Comprueba que hay espacio en disco** para las imágenes que va a descargar y para la
   instantánea que va a escribir, antes de hacer ninguna de las dos cosas. Una actualización que se
   queda sin espacio a medias es peor que una que se niega: la base de datos y el proxy escriben en
   el mismo disco que está llenando la descarga.

   Las cifras están medidas, no supuestas. Para las imágenes se reserva 1 GB en una actualización y
   1,8 GB en una primera instalación: una primera instalación descarga todo el stack (1,55 GB
   medidos), una actualización solo lo que ha cambiado (771 MB medidos entre dos releases
   consecutivas, porque la capa de dependencias del backend se reconstruye en cada release). No se
   pide nada por imágenes que ya están en local, así que volver a ejecutarlo contra la versión ya
   instalada nunca se rechaza por falta de espacio para descargarla. La instantánea se calcula a
   partir de **tu propio último volcado**, multiplicado por dos, y cuando no hay ningún volcado del
   que aprender no se pide nada en vez de inventar un número.

   `--skip-disk-check` sigue adelante de todos modos, para una máquina cuyo almacenamiento `df`
   informa mal, un sistema de archivos en red o un aprovisionamiento fino por debajo.

4. **Descarga las imágenes de la release.** Todas, antes de tocar nada en la instancia, así que una
   versión que no existe, o una release cuyas imágenes no se publicaron todas, es una actualización
   que se niega mientras la antigua sigue dando servicio. No se sustituye nada ni se escribe
   todavía ninguna instantánea, así que no cuesta nada si se detiene aquí.

5. **Confirma que los archivos de despliegue de aquí son los de la release.** Compara
   `docker-compose.yml` y el `Caddyfile` del directorio de instalación, por suma de comprobación,
   con lo que la release espera que sean, y se detiene si difieren, que es el aspecto que tiene una
   actualización en la que se saltó la primera orden. Esto se ejecuta antes de la instantánea, así
   que un refresco olvidado no cuesta nada.

   Las sumas de comprobación esperadas viajan **en la imagen**, escritas como una etiqueta cuando
   se construyó, y se leen de la copia que se acaba de descargar. Leerlas solo necesita el
   registro, que la actualización necesitaba de todos modos, así que un despliegue que puede
   descargar también puede comprobar, y ninguna parte de esto depende de llegar a GitHub.

   De ahí salen dos cosas. Una release que trae archivos de despliegue idénticos a los de la
   anterior no dice nada aquí, como debe ser: los bytes coinciden, así que no hay nada que contar. Y
   una release construida antes de que existiera esta etiqueta no lleva nada con lo que comparar;
   eso se dice claramente y la actualización continúa, para que las releases antiguas se puedan
   seguir instalando.

   Si mantienes tú estos archivos (un despliegue que conserva un archivo de Compose personalizado,
   por ejemplo), `--skip-file-check` sigue adelante sin compararlos.

6. **Hace una copia de seguridad de la base de datos** con `scripts/db-backup.sh`. Una release que
   trae una migración del esquema no se puede deshacer volviendo a fijar `IMAGE_TAG`: las imágenes
   vuelven atrás, el esquema migrado no, así que este volcado es la única salida de una mala
   actualización. Si falla, la actualización no se hace. En una primera instalación todavía no hay
   base de datos y lo dice en su lugar.

7. **Ejecuta las comprobaciones propias de la release contra la base de datos** que la versión
   antigua sigue sirviendo. Una migración que se negaría (ver más abajo) lo dice ahora, mientras la
   instancia sigue en marcha, y no se cambia nada. Que pase significa que no se incumple ninguna
   condición previa sobre los datos declarada por una migración, no que la actualización no pueda
   fallar por otros motivos.

8. **Aplica la versión** mediante `scripts/install.sh --tag "$MEMSHIP_VERSION"`, que escribe
   `IMAGE_TAG`, descarga y vuelve a crear el stack. Nunca sobrescribe un `.env` existente. También
   fuerza la recreación de Caddy, lo cual importa: el `Caddyfile` está montado con bind, así que
   cambiar su contenido no le da a `docker compose up -d` ningún motivo para recrear el contenedor,
   y de lo contrario seguiría sirviendo la configuración antigua.

9. **Verifica el resultado** con `scripts/verify-deployment.sh`, que espera a la API, comprueba que
   informa de la versión que acabas de desplegar y hace ping al worker de Celery. Que `docker compose
   up -d` termine solo dice que se crearon los contenedores; las migraciones se ejecutan antes de
   que la API sirva, así que una fallida parece una API que nunca responde y no un contenedor que
   ha muerto.

Es la misma orden que ejecuta el workflow de despliegue por SSH, a propósito: lo que está
automatizado y lo que teclea un operador no deberían separarse.

> El volcado previo a la actualización acaba en `$MEMSHIP_DATA_ROOT/backups`, en el mismo disco que
> la base de datos que protege. Cubre una mala actualización, no una máquina perdida; ver
> [Copias de seguridad y restauración](backups-and-restore.md#copias-fuera-del-servidor) para sacar
> copias de la máquina.

## Actualizar desde una release anterior al backend sin root

Los contenedores del backend se ejecutaban antes como root, así que todo lo que escribían en el
directorio de almacenamiento quedaba con root como propietario. Ahora se ejecutan como
`HOST_UID`/`HOST_GID`, que es lo que hace que los archivos subidos montados con bind se puedan leer
en el host sin `sudo`, pero el contenedor ya no puede escribir en los archivos que dejó su versión
de la época de root.

Toma la propiedad una vez, después de actualizar:

```bash
sudo chown -R $(id -u):$(id -g) "$MEMSHIP_DATA_ROOT/storage"
```

`scripts/install.sh` lo detecta y muestra la orden exacta; ejecutarla a mano tiene el mismo efecto.

Dos cambios relacionados en la misma release:

- **`uv run` ya no funciona dentro de los contenedores.** El virtualenv está en el `PATH` en su
  lugar, así que no se escribe nada bajo `/app` en tiempo de ejecución, que es lo que permite que
  el contenedor se ejecute con cualquier uid. Usa `docker compose exec api python -m …`, no
  `docker compose exec api uv run python -m …`. Todo lo que tengas automatizado contra los
  contenedores necesita el mismo cambio.
- **Los datos persistentes han pasado de volúmenes con nombre a montajes bind** bajo
  `MEMSHIP_DATA_ROOT`. Si actualizas una instalación que usaba volúmenes con nombre, copia cada uno
  antes de arrancar:

  ```bash
  docker run --rm -v pgdata:/from -v /srv/openmemship/data/postgres:/to \
      alpine cp -a /from/. /to/
  ```

## Migraciones de la base de datos

Las migraciones se ejecutan automáticamente al arrancar el backend cuando `RUN_MIGRATIONS=1` (el
valor por defecto en el stack de Compose). En una actualización normal no hace falta ningún paso
manual de migración, y casi siempre aquí no hay nada en lo que pensar.

**Una migración puede negarse.** Algunas llevan una salvaguarda: inspeccionan los datos antes de
cambiarlos y se detienen si encuentran algo que solo una persona debería decidir, por ejemplo dos
cuentas que solo se diferencian en las mayúsculas de su dirección de correo, donde unificarlas
supondría elegir un ganador entre los accesos de dos personas. La salvaguarda escribe un informe
que indica exactamente lo que ha encontrado, no hace **ningún cambio**, y la actualización se
detiene ahí.

Qué aspecto tiene: `upgrade.sh` se detiene en sus comprobaciones previas a la actualización y
muestra el informe, con el nombre de la migración que se negaría.

Tres cosas que conviene saber cuando ocurre:

- **La base de datos no se ha tocado.** Una salvaguarda no escribe nada antes de negarse, así que
  no hay ningún estado migrado a medias. No restaures la instantánea previa a la actualización: no
  hay nada que deshacer, y restaurar pierde todo lo que se haya escrito desde que se tomó.
- **Tu instancia sigue dando servicio.** Las comprobaciones se ejecutan antes de sustituir nada,
  así que la versión en la que estabas sigue respondiendo mientras resuelves el informe. Tómate el
  tiempo que necesites.
- **Resuelve los datos y vuelve a ejecutar la misma orden de actualización**: no hace falta volver
  a descargar ni a fijar nada.

> Las actualizaciones anteriores a esto ejecutaban la comprobación al arrancar la API, *después*
> de sustituir el stack, así que un rechazo hacía que la API se reiniciara en bucle y los socios
> recibieran errores hasta que alguien resolviera los datos
> ([issue #194](https://github.com/marcandreuf/memship/issues/194)). Si llegas a un rechazo por esa
> vía, porque ejecutaste `install.sh` directamente o actualizaste desde una release más antigua, el
> consejo sobre los datos de arriba no cambia; simplemente la instancia está caída mientras lo
> sigues.

[Resolución de problemas](troubleshooting.md#una-migración-se-negó-a-ejecutarse-y-la-api-no-arranca) tiene los pasos, incluido por qué la solución es
*cambiar* una fila en vez de borrarla.

Si prefieres ejecutar las migraciones a mano, pon `RUN_MIGRATIONS=0` y ejecútalas tú contra el
contenedor del backend después de descargar la imagen nueva.

## Volver atrás

Para volver atrás, vuelve a ejecutar la actualización contra la versión más antigua: refresca los
archivos desde el tarball de esa release y después `./scripts/upgrade.sh <older-version>`. Volver
por el mismo camino por el que llegaste mantiene los archivos de despliegue y las imágenes en la
misma release.

Ten en cuenta que **las migraciones de la base de datos no se deshacen automáticamente.** Si la
release que dejas incluía una, las imágenes vuelven atrás y el esquema migrado no, así que restaura
el volcado que tomó `upgrade.sh` antes de aplicar esa versión (está en
`$MEMSHIP_DATA_ROOT/backups`, con nombre por marca de tiempo) en vez de limitarte a bajar la versión
de la imagen.
