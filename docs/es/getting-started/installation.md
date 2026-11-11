<!-- source: en/getting-started/installation.md -->
<!-- source-hash: 9bdf6c2e4668 -->

# Instalación (Docker)

Esta guía cubre una instalación autoalojada **de producción**. Para una evaluación rápida en local,
usa en su lugar la [Prueba rápida](quickstart.md).

> **En inglés:** [Installation (Docker)](../../en/getting-started/installation.md).
> **En català:** [Instal·lació (Docker)](../../ca/getting-started/installation.md).

## Requisitos previos

- Un servidor con Docker Engine y el complemento Compose
- Un usuario normal (no root) del grupo `docker`: la plataforma no se instala como root
- `curl` y `tar`, para descargar una versión. `tar` está en todos los servidores Debian/Ubuntu; a
  las imágenes mínimas a veces les falta `curl`: `sudo apt-get update && sudo apt-get install -y curl`
- **`git`, no.** Una versión se descarga como un archivo tar, y el servidor no guarda ninguna copia
  del código fuente: nada de una instancia en marcha usa git, así que no hay motivo para instalarlo
- Un nombre de dominio, con un registro A del DNS apuntando ya al servidor, si quieres HTTPS
  automático. Si el dominio es de una organización y no tuyo, de forma que el nombre de máquina, la
  zona DNS y el dominio del correo son asunto de tres personas distintas, lee antes
  [El dominio de tu organización](../self-hosting/domain-and-dns.md)

> **Un Memship por máquina.** El archivo de Compose da nombre explícito a sus contenedores
> (`memship-db`, `memship-api`, …), que es lo que permite a los scripts y a la documentación
> referirse a ellos. Los nombres son globales en el demonio de Docker, así que una segunda
> instancia, aunque sea desde otro directorio, con su propio directorio de datos y su propio
> proyecto de Compose, falla a medias con
> `Conflict. The container name "/memship-db" is already in use`. Usa otro servidor, o una máquina
> virtual.

### Partiendo de un servidor vacío

`scripts/vps-bootstrap.sh` hace la mitad de la preparación que requiere root. Ejecútalo **una sola
vez, como root**, en una máquina recién creada con Debian 12 o Ubuntu 24.04:

Descárgalo en un sitio donde ya puedas escribir, tu propio directorio personal. La instalación en
sí vive bajo `/srv`, pero nadie puede escribir ahí hasta que se haya ejecutado el bootstrap. Elige
una versión de la [página de versiones](https://github.com/marcandreuf/memship/releases) y úsala en
todo el proceso:

```bash
MEMSHIP_VERSION=3.3.0

curl -fsSLO "https://raw.githubusercontent.com/marcandreuf/memship/v${MEMSHIP_VERSION}/scripts/vps-bootstrap.sh"
chmod +x vps-bootstrap.sh
sudo ./vps-bootstrap.sh --user deploy --ssh-key-file ~/.ssh/authorized_keys
```

El script es autónomo, no necesita ningún otro archivo del repositorio, y por eso basta con un solo
`curl`.

`--user` indica la cuenta que será dueña de la instalación; pasa la cuenta con la que ya has
entrado (`--user "$USER"`) para usarla en vez de crear un `deploy` aparte. `--ssh-key-file` recibe
un archivo que contenga una clave SSH **pública**: tu propio `~/.ssh/authorized_keys` es la opción
segura, ya que un servidor recién creado no tiene ningún archivo `.pub` a mano. Sin clave no puedes
entrar como el nuevo usuario. El `~` de arriba lo expande tu propio shell antes de que se ejecute
`sudo`, así que es tu directorio personal; desde un **shell de root** (`sudo -i`) sería el de root,
así que ahí pasa una ruta absoluta.

Crea el usuario de despliegue, instala Docker desde el repositorio del propio Docker, activa
`unattended-upgrades`, `fail2ban` y `ufw`, configura la zona horaria y añade una limpieza semanal
de imágenes.

A propósito, **no** refuerza el SSH: en su lugar imprime esas órdenes, en un orden que mantiene
abierta una sesión que funciona mientras compruebas cada paso. Un script no puede comprobar que
todavía puedes entrar, y equivocarse en el orden te deja fuera de un servidor que quizá no tenga
consola.

Después, sal y vuelve a entrar, para que la pertenencia del usuario de despliegue al grupo `docker`
surta efecto.

> **El grupo `docker` da, en la práctica, acceso de root.** Cualquiera que pueda ejecutar `docker`
> puede montar `/` en un contenedor y escribir en cualquier parte de la máquina. El usuario de
> despliegue es una cuenta privilegiada, no un entorno aislado.

## Instalar

`/srv` pertenece a root, así que primero se crean los dos directorios **como root**, y todo lo que
viene después se ejecuta como el usuario de despliegue. Nombra **los dos**: `install -d` da la
propiedad a los directorios que crea, no al padre, así que crear solo `app` deja
`/srv/openmemship` como propiedad de root y al usuario de despliegue sin poder crear el directorio
de datos, y entonces `install.sh` se detiene con `cannot create /srv/openmemship/data`.

```bash
sudo install -d -o deploy -g deploy /srv/openmemship/app /srv/openmemship/data
```

Si el usuario de despliegue es la cuenta con la que ya has entrado, usa `-o "$USER" -g "$USER"`.

> **El usuario de despliegue no puede usar `sudo`.** `vps-bootstrap.sh` lo crea con `adduser
> --disabled-password`, así que no tiene contraseña que escribir cuando sudo la pide. Es
> deliberado: la cuenta ya tiene el socket de Docker, que en la práctica es acceso de root, y una
> segunda vía hacia root no aporta nada. Por eso la orden de arriba se ejecuta como root y no como
> el usuario de despliegue.

Ahora conviértete en el usuario de despliegue; nada de lo que sigue necesita root. `install.sh`
escribe `.env` dentro del directorio de instalación y tiene que ser su dueño:

```bash
MEMSHIP_VERSION=3.3.0

curl -fsSL "https://github.com/marcandreuf/memship/archive/refs/tags/v${MEMSHIP_VERSION}.tar.gz" \
  | tar -xz -C /srv/openmemship/app --strip-components=1
cd /srv/openmemship/app
./scripts/install.sh --data-root /srv/openmemship/data --domain memship.example.com \
                     --tag "$MEMSHIP_VERSION"
```

El script de bootstrap de tu directorio personal ya ha cumplido su función y se puede borrar.

Eso llena el directorio de datos, genera secretos reales en `.env` (modo 600), descarga las
imágenes publicadas y arranca la plataforma.

**Copia `.env` fuera del servidor ahora, antes de meter datos reales.** `SECRET_KEY` y
`MEMSHIP_SECRET_KEY` se acaban de generar aquí, no se regeneran nunca y no existen en ningún otro
sitio. Descifran las credenciales de los proveedores de pago, del SSO y del correo guardadas en la
base de datos, así que sin este archivo un volcado perfecto de la base de datos las restaura como
texto cifrado ilegible. Guárdalo en un gestor de contraseñas al que pueda llegar un segundo
administrador; consulta
[Copias de seguridad y restauración](../self-hosting/backups-and-restore.md#hazlo-el-mismo-día-de-la-instalación).

En una primera instalación, `install.sh` también escribe **`POST-INSTALL.md`** junto a `.env`: este
paso más crear tu organización, programar las copias de seguridad y configurar el correo, con las
rutas ya rellenadas. Síguelo de principio a fin y bórralo.

**Tu instalación queda fijada a una versión.** `--tag` se convierte en `IMAGE_TAG`, así que el
despliegue se queda en esa versión hasta que lo muevas a propósito, y `/api/v1/health` informa de
cuál ejecuta.

**`--tag` es obligatorio aquí, y el instalador lo exige.** En un despliegue desempaquetado desde
el archivo tar de una versión no hay copia de git, así que no hay ninguna etiqueta de la que leer
una versión, y omitir `--tag` detiene la instalación:

```
Error: --tag is required here: there is no git tag to read a version from.
```

Antes se resolvía como `latest`, un objetivo que se mueve, y daba una instancia que informaba de su
propia versión como la cadena literal `latest`. Se niega antes de escribir `.env` o de generar
ningún secreto, así que indica la versión y vuelve a ejecutarlo. En una copia de git `--tag` todavía
se puede omitir, y entonces toma por defecto la etiqueta de versión más reciente; `--tag latest`
sigue disponible para seguir a propósito las imágenes que sean más nuevas en cada momento.

**Para actualizar más adelante, sigue [Actualizar](../self-hosting/upgrading.md).** Mover
`IMAGE_TAG` por sí solo no basta: `docker-compose.yml`, el `Caddyfile` y `scripts/` se distribuyen
junto a las imágenes y no dentro de ellas, así que una actualización empieza por refrescar esos
archivos desde la nueva versión.

**Apunta el DNS al servidor primero.** `install.sh` se niega a arrancar cuando el nombre de máquina
no resuelve a esta máquina, porque Caddy valida por HTTP-01 y Let's Encrypt limita las validaciones
*fallidas* a 5 por nombre de máquina y por hora: un arranque prematuro puede dejarte sin
certificados durante una hora. Usa `--skip-dns-check` solo si sabes por qué te lo saltas.

Volver a ejecutar el script es seguro. Nunca sobrescribe un `.env` existente, y volver a
ejecutarlo es como recoges más adelante un `IMAGE_TAG` nuevo.

> **Reinstalar desde cero gasta certificados.** El certificado emitido vive en
> `<data-root>/caddy/data`. Borra ese directorio, como hace un desmontaje completo, y el siguiente
> arranque pide un certificado **nuevo** en vez de renovar el anterior. Let's Encrypt permite **5
> certificados por semana para el mismo conjunto de nombres de máquina**, así que unas pocas
> reinstalaciones desde cero contra un mismo dominio lo agotan y te dejan sin HTTPS hasta que la
> ventana avance. Cuando ensayes una instalación, omite `--domain` y trabaja con HTTP simple, y
> añade el dominio en la pasada final. Conservar `caddy/data` a lo largo de una reconstrucción evita
> del todo la reemisión.

Luego ejecuta la configuración, que crea tu superadministrador y tu organización:

```bash
docker compose exec -it api python -m app.cli.seed
```

El `-it` importa: la orden hace preguntas. Consulta [Configuración inicial](first-setup.md) para
ver qué pregunta y los parámetros desatendidos que usa en su lugar un despliegue automatizado.

Abre tu dominio o, si instalaste sin él, **http://&lt;server-address&gt;**, el nombre de máquina o
la IP con la que llegas al servidor. `localhost` solo funciona cuando instalas en la máquina que
tienes delante.

### Sin dominio

Omite `--domain`. Caddy sirve entonces HTTP simple en el puerto 80, que es lo que quieres para una
instalación local o interna.

Así es también como se ensaya una instalación en un servidor real sin gastar certificados: instala
sin `--domain`, comprueba que la plataforma funciona y luego vuelve a ejecutarlo con `--domain`
para añadir HTTPS. Volver a ejecutarlo actualiza `SITE_ADDRESS` y las URL públicas a la vez, así
que nada se queda apuntando a la dirección anterior.

## El directorio de datos

Todo lo que tiene que sobrevivir a un nuevo despliegue vive bajo un único directorio:

| Ruta             | Contenido                                                       |
|------------------|-----------------------------------------------------------------|
| `postgres/`      | La base de datos                                                |
| `storage/`       | Archivos subidos (logotipos, imágenes de actividades, PDF generados) **y las claves generadas `secret.key` y `session.key`** |
| `celerybeat/`    | El estado del planificador                                      |
| `caddy/data`     | Clave de la cuenta ACME y certificados TLS emitidos             |
| `caddy/config`   | La configuración que Caddy guarda automáticamente               |
| `backups/`       | Volcados de la base de datos escritos por `scripts/db-backup.sh` |

Hacer copia de seguridad de Memship es hacer copia de seguridad de **ese único directorio, más
`.env`**. Consulta [Copias de seguridad y restauración](../self-hosting/backups-and-restore.md).

Tres cosas que conviene saber sobre él:

- Son montajes de enlace (bind mounts), no volúmenes con nombre, así que los datos sobreviven a
  `docker compose down -v` y a `docker system prune --volumes`.
- `storage/` lo escribe el backend ejecutándose con tu uid, así que los archivos subidos se pueden
  leer sin `sudo`.
- `postgres/` tiene modo `0700` y es propiedad del uid 70: lo ves como ruta pero no lo puedes leer.
  Es correcto y es lo esperado. Lee la base de datos con `scripts/db-backup.sh`, no con `ls`.

> **Pon el directorio de datos en `/srv`, no en un directorio personal.** `/srv` es el sitio que
> marca la FHS para los datos de servicios, sobrevive a que se borre el usuario y sigue accesible
> cuando cambian los permisos de un directorio personal. Un directorio de datos bajo `$HOME` sí
> funciona con Docker normal (el demonio resuelve como root el origen de los montajes de enlace,
> así que un directorio personal con `0700` no impide que arranque Postgres), pero falla con
> **Docker sin root (rootless) y con Podman**, donde el uid del propio contenedor tiene que poder
> recorrer la ruta.

### Máquinas con SELinux (RHEL, Fedora, Rocky, AlmaLinux)

En sistemas con SELinux en modo enforcing, los montajes de enlace necesitan reetiquetarse o los
contenedores reciben "permission denied" aunque la propiedad sea correcta. O bien añade `:z` a cada
montaje de enlace de `docker-compose.yml`:

```yaml
- ${MEMSHIP_DATA_ROOT:-./data}/postgres:/var/lib/postgresql/data:z
```

…o reetiqueta el árbol una sola vez, lo que sobrevive a las actualizaciones de Compose:

```bash
sudo semanage fcontext -a -t container_file_t "/srv/openmemship/data(/.*)?"
sudo restorecon -Rv /srv/openmemship/data
```

Las máquinas con Debian y Ubuntu no se ven afectadas.

## Instalar a mano

Si prefieres no usar `install.sh`, los pasos manuales equivalentes son:

```bash
MEMSHIP_VERSION=3.3.0

mkdir -p memship
curl -fsSL "https://github.com/marcandreuf/memship/archive/refs/tags/v${MEMSHIP_VERSION}.tar.gz" \
  | tar -xz -C memship --strip-components=1
cd memship
cp .env.example .env
```

Luego define, como mínimo:

- **`MEMSHIP_DATA_ROOT`**, ruta absoluta al directorio de datos descrito arriba
- **`SECRET_KEY`** y **`DB_PASSWORD`**, valores aleatorios, nunca los de ejemplo. `SECRET_KEY` se
  puede dejar en blanco (el servidor genera una en `storage/session.key`), pero definirla
  explícitamente es lo que permite que una máquina reconstruida mantenga las sesiones activas y
  las credenciales de pago legibles
- **`MEMSHIP_SECRET_KEY`**, cifra las credenciales guardadas del SSO y de los proveedores de pago.
  Defínela explícitamente para que una máquina reconstruida pueda seguir descifrando una copia de
  seguridad restaurada
- **`HOST_UID`** / **`HOST_GID`**, tu `id -u` y tu `id -g`, para que los archivos subidos en los
  montajes de enlace sean tuyos
- **`SITE_ADDRESS`**, tu nombre de máquina para HTTPS automático, o vacío para HTTP simple
- **`IMAGE_TAG`**, fija una versión publicada; consulta [Actualizar](../self-hosting/upgrading.md)

Crea el árbol de directorios y luego arranca la plataforma. `.env` lo lee Compose, no tu shell,
así que exporta aquí también la ruta, o escríbela entera:

```bash
export MEMSHIP_DATA_ROOT=/srv/openmemship/data
mkdir -p "$MEMSHIP_DATA_ROOT"/{postgres,storage,celerybeat,caddy/data,caddy/config,backups}
docker compose pull
docker compose up -d
```

No te saltes el `mkdir`. Docker crea él mismo el origen de un montaje de enlace que falte, pero
como **root**, y el backend se ejecuta con tu uid, así que luego no puede escribir sus propios
archivos subidos.

Consulta la [Referencia de configuración](../self-hosting/configuration.md) para ver todos los
ajustes disponibles.

## Servicios

La plataforma de Compose por defecto funciona detrás de un proxy inverso Caddy. Estas URL son
**vistas desde el propio servidor**: la API y la base de datos están ligadas a `127.0.0.1`, así que
`localhost` es la única forma de llegar a ellas. Desde cualquier otro sitio, usa tu dominio o la
dirección del servidor, que solo llega a las dos primeras filas:

| Servicio    | URL (en el servidor)             | Descripción                    |
|-------------|----------------------------------|--------------------------------|
| Frontend    | `http://localhost`               | Portal del socio (vía Caddy)   |
| API         | `http://localhost/api/v1/health` | API del backend (vía Caddy)    |
| API directa | `http://localhost:8003`          | API del backend (directa)      |

> **`ufw` no limita a Docker.** Docker inserta sus propias reglas de iptables por delante de las
> del cortafuegos, así que un puerto publicado en todas las interfaces sigue siendo accesible desde
> internet aunque `ufw` lo deniegue. Por eso la plataforma tal como se distribuye publica la API
> (8003) y Postgres (5433) **solo en `127.0.0.1`**, y por eso se llega a ellos desde el propio
> servidor y desde ningún otro sitio. Poner `API_BIND` o `DB_BIND` a `0.0.0.0`, o añadir tu propia
> entrada `ports:`, deja ese servicio en internet sin importar las reglas de tu cortafuegos.
> Compruébalo desde otra máquina con `nmap -Pn -p 22,80,443,5433,8003 <your-host>` en vez de fiarte
> de `ufw status`.

## Siguientes pasos

1. [Configuración inicial](first-setup.md): crea tu organización y tu administrador.
2. [Referencia de configuración](../self-hosting/configuration.md): revisa los ajustes de
   producción.
3. [Envío de correo](../self-hosting/email.md): necesario para las confirmaciones de dirección, los
   restablecimientos de contraseña y los avisos de pago.
4. [Copias de seguridad y restauración](../self-hosting/backups-and-restore.md): configúralas antes
   de ponerlo en marcha.
