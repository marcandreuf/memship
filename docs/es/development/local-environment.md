<!-- source: en/development/local-environment.md -->
<!-- source-hash: 2cf76cf56eb5 -->

# Entorno de desarrollo local

El backend corre en Docker (API, worker y beat de Celery, PostgreSQL, Redis); el frontend corre en
local con pnpm, así que tienes la recarga en caliente de Next.js sin un contenedor por en medio.

> **En inglés:** [Local development environment](../../en/development/local-environment.md).
> **En català:** [Entorn de desenvolupament local](../../ca/development/local-environment.md).

`scripts/dev.sh` lo gobierna todo.

## Requisitos previos

| Herramienta | Para qué |
|---|---|
| Docker Engine + complemento Compose | Todo el backend: API, base de datos, Redis, worker, beat, migraciones y la batería de pruebas |
| **Node 22** y **pnpm** | El servidor de desarrollo del frontend |

Esa es la lista completa. **El backend nunca corre en el host**: ni `uv sync`, ni virtualenv, ni
versión de Python que cuadrar, así que el mismo checkout se comporta igual en cualquier máquina con
Docker. `backend/app`, `backend/tests` y `backend/alembic` se montan en los contenedores con un bind
mount: los editas en tu editor y el código en ejecución cambia. La API se reinicia sola cuando hay
un cambio bajo `backend/app` (el reloader de uvicorn, solo con `APP_ENV=development`; vigila
`dev.sh logs backend` para ver "Reloading..."). El worker y beat no lo hacen: reinícialos después de
editar una tarea. El contenedor es donde se ejecuta el código, no donde vive.

Solo el frontend se queda en el host, y a propósito: el servidor de desarrollo de Next.js está ahí
por la recarga en caliente, que es lo único que un contenedor no hace igual de bien. Cypress
necesita un navegador de verdad, así que la batería e2e también está en el host.

La versión mayor de Node está fijada en `frontend/.nvmrc` y `engines` en `frontend/package.json` la
hace cumplir como aviso. **Usa la 22**: es la que ejecuta la CI y sobre la que se construye la
imagen de producción, y una versión mayor distinta es el tipo de diferencia que solo aparece como
una build que funciona en una máquina y no en otra. Con `nvm`:

```bash
cd frontend
nvm install       # reads .nvmrc; `nvm use` on its own only switches to an already-installed major
corepack enable   # re-run this after every version switch, see below
```

Una discrepancia imprime `WARN Unsupported engine` y sigue adelante, y es deliberado: debe
avisarte, no pararte a mitad de sesión. `pnpm install --engine-strict` convierte esa misma
comprobación en un fallo de verdad si alguna vez quieres que se cumpla a rajatabla.

La versión de pnpm la fija `packageManager` en el mismo fichero, así que `corepack enable` te da la
correcta sin que tengas que instalarla tú.

> **Los shims de corepack viven dentro de cada instalación de Node**, así que cambiar de versión
> mayor se lleva pnpm por delante. Si llegas a la 22 desde otra versión, `./scripts/dev.sh start all`
> levanta el backend y luego hace fallar el frontend con `pnpm: command not found` en
> `frontend/logs/dev-server.log`. Ejecutar `corepack enable` una vez en la nueva versión mayor lo
> arregla para siempre.

> **No necesitas Node para nada si solo quieres ejecutar memship.** El frontend se distribuye como
> contenedor, y la [Prueba rápida](../../en/getting-started/quickstart.md) _(en inglés)_ ejecuta
> toda la aplicación a partir de las imágenes publicadas con una sola orden. Instala las
> herramientas cuando quieras *trabajar en* el frontend: el servidor de desarrollo local existe por
> la recarga en caliente, que es lo único que un contenedor no puede hacer igual de bien.

## Arrancar

```bash
./scripts/dev.sh start all      # backend in Docker + frontend locally
./scripts/dev.sh status         # what is up
./scripts/dev.sh stop all       # stop everything
```

## Órdenes

| Orden | Descripción |
|---------|-------------|
| `./scripts/dev.sh start all` | Arranca el backend (Docker) + el frontend (local) |
| `./scripts/dev.sh start backend` | Arranca solo el backend: API, base de datos, Redis, worker, beat |
| `./scripts/dev.sh start frontend` | Arranca solo el servidor de desarrollo de Next.js |
| `./scripts/dev.sh stop all` | Para todos los servicios |
| `./scripts/dev.sh restart all` | Reinicia todos los servicios |
| `./scripts/dev.sh status` | Estado de cada servicio |
| `./scripts/dev.sh logs backend` | Logs de la API |
| `./scripts/dev.sh logs frontend` | Logs del frontend (`tail -f`) |
| `./scripts/dev.sh logs worker` | Logs del worker de Celery |
| `./scripts/dev.sh logs beat` | Logs de Celery beat (el planificador) |
| `./scripts/dev.sh seed` | Configuración interactiva, la misma que usa cualquier entorno |
| `./scripts/dev.sh seed demo` | Club de demostración con credenciales **generadas**, usa preferentemente esta |
| `./scripts/dev.sh seed test` | Cuentas fijas para las pruebas e2e, cuyas contraseñas son públicas |
| `./scripts/dev.sh passwd [email]` | Sustituye la contraseña del superadministrador por una generada |
| `./scripts/dev.sh test [args]` | Batería de pruebas del backend, en un contenedor; los argumentos extra van a pytest |
| `./scripts/dev.sh shell` | Un shell dentro del contenedor de la API |
| `./scripts/dev.sh shelltest [run\|mutate\|lint]` | Las guardas de shell de los scripts de despliegue, en un contenedor Linux sobre una copia del árbol |
| `./scripts/dev.sh migration "msg"` | Autogenera una revisión de Alembic a partir de tus cambios en los modelos |
| `./scripts/dev.sh e2e` | Cypress, sin interfaz (headless) |
| `./scripts/dev.sh e2e:open` | Cypress con interfaz gráfica |
| `./scripts/dev.sh e2e:parallel` | Cypress, 4 workers |
| `./scripts/dev.sh reset` | **Destructiva**, ver más abajo |

`start`, `stop` y `restart` aceptan `backend`, `frontend`, `worker`, `beat` o `all` (el valor por
defecto). `start all` levanta el worker y beat junto con la API y la base de datos.

`shelltest` es la forma de ejecutar las guardas de shell obligatorias después de cualquier cambio
bajo `scripts/`. Da la misma respuesta que la CI desde cualquier máquina, Windows incluido, y tarda
alrededor de un minuto. `./tests/shell/run.sh` también se ejecuta de forma nativa. En Git Bash se
salta las dos comprobaciones que necesitan permisos de fichero y enlaces simbólicos, que NTFS no
conserva, y tarda varias veces más. Ejecuta `shelltest mutate` en lugar de
`./tests/shell/mutate-check.sh`. Las dos demuestran que cada guarda está cubierta por las pruebas,
pero la nativa reescribe tus scripts versionados mientras trabaja, y `shelltest` solo toca una
copia.

> **`reset` borra tus volúmenes.** Ejecuta `docker compose down -v`, que destruye la base de datos
> de desarrollo *y* el volumen de almacenamiento, y con él lo subido y `storage/secret.key`. Perder
> esa clave significa que las credenciales de proveedores de pago o de SSO guardadas en esa base de
> datos ya no se pueden descifrar. No hay pregunta de confirmación. Úsalo cuando quieras empezar de
> cero, no para arreglar un contenedor atascado.

## URL de los servicios

| Servicio | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API del backend | http://localhost:8003 |
| Documentación de la API (Swagger) | http://localhost:8003/api/docs |
| Base de datos | localhost:5433 |
| Base de datos de pruebas | localhost:5434 (la arranca `dev.sh test`) |
| Redis | localhost:6379 |
| Adminer (interfaz de la base de datos) | http://localhost:8181, no lo arranca `dev.sh`, ver más abajo |

Adminer está detrás de un perfil de Compose y no tiene orden en `dev.sh`:

```bash
docker compose -f backend/docker/docker-compose.yml --profile tools up -d adminer
```

## El entorno de desarrollo no está blindado: todo escucha en localhost

El entorno de desarrollo trae a propósito una configuración débil: una contraseña fija de la base
de datos (`memship`), Redis sin autenticación y, después de `seed test`, **credenciales de
superadministrador publicadas en este repositorio**. Eso está bien en un portátil y es un desastre
en una red compartida, así que **por defecto nada queda expuesto más allá de loopback**: la API, la
base de datos, Redis y Adminer escuchan en `127.0.0.1`, y el servidor de desarrollo de Next.js
también.

Atar los contenedores no basta por sí solo. Next.js escucha en `0.0.0.0` de serie, y el frontend
hace de proxy hacia la API del lado del servidor, así que un servidor de desarrollo en todas las
interfaces es un camino completo hasta la aplicación, inicio de sesión incluido, aunque todos los
contenedores estén en loopback. Las dos mitades están fijadas.

### Trabajar en una red pública

Escuchar solo en loopback es lo que hace segura la red de una cafetería o de un coworking, y es
toda la defensa. Pon el resto encima:

- **Usa preferentemente `./scripts/dev.sh seed demo`** en lugar de `seed test` para el trabajo
  normal. Siembra los mismos datos de ejemplo, pero genera la contraseña del superadministrador y
  los accesos de demostración, y los imprime una sola vez. `seed test` existe para la batería de
  Cypress, cuyas credenciales son un contrato y por tanto públicas.
- **Si ya has ejecutado `seed test`**, `./scripts/dev.sh passwd` sustituye la contraseña del
  superadministrador por una generada. Volver a ejecutar `seed test` repone las fijas cuando vuelvas
  a necesitar la batería.
- **Nunca combines `DEV_BIND=0.0.0.0` con datos de `seed test`.** Cualquiera en la red puede
  entonces leer la contraseña en este repositorio y entrar como superadministrador. `dev.sh start`
  comprueba si existen esas cuentas y te avisa.

### Acceder al entorno desde otro dispositivo

Para probar desde un móvil o desde una máquina virtual, actívalo para esa sesión:

```bash
DEV_BIND=0.0.0.0 ./scripts/dev.sh start all
```

Eso publica los contenedores en todas las interfaces y arranca Next.js con `-H 0.0.0.0`. Hazlo solo
en una red que controles, y vuelve a sembrar con `seed demo` antes.

### Notas por plataforma

El mecanismo `DEV_BIND` es la propia sintaxis `HOST:PORT:PORT` de Docker más un flag de Next.js,
así que se comporta igual en las tres plataformas. Lo que cambia es lo que lo rodea:

| Plataforma | Qué tienes que saber |
|---|---|
| **Linux (Ubuntu 24.04+)** | Docker inserta sus reglas de iptables **por delante de `ufw`**, así que un puerto publicado es accesible aunque el cortafuegos lo deniegue. `ufw` no te va a salvar de `DEV_BIND=0.0.0.0`; la dirección de escucha es el control que funciona. |
| **macOS (Docker Desktop)** | La máquina virtual reenvía los puertos al host y respeta la dirección de escucha, así que loopback sigue siendo loopback. macOS puede pedir permiso para las conexiones entrantes la primera vez que uses `dev:lan`. |
| **Windows (Docker Desktop + WSL2)** | Escuchar en loopback funciona gracias al reenvío de localhost de WSL2. En el modo de red **mirrored** (Windows 11, `networkingMode=mirrored` en `.wslconfig`) la instancia de WSL comparte las interfaces del host, así que `0.0.0.0` dentro de WSL está de verdad en la LAN, y quien pregunta es el Firewall de Windows, no `ufw`. Ejecuta `dev.sh` desde WSL o Git Bash; es un script de bash. |

`0.0.0.0` significa *todas* las interfaces, incluidos los adaptadores de VPN y de Tailscale, que
llegan bastante más lejos que el wifi de la cafetería.

## Configuración inicial

```bash
./scripts/dev.sh seed          # interactive, the same setup every environment uses
./scripts/dev.sh seed demo     # demo club, generated credentials, the everyday choice
./scripts/dev.sh seed test     # fixed test accounts + sample data, for the e2e suite
```

`seed test` crea las cuentas con las que entra la batería de Cypress, más 4 actividades de ejemplo
con modalidades y precios, inscripciones de ejemplo y ~22 socios más. Esas direcciones y
contraseñas son un contrato con la batería de pruebas, no una decisión de la siembra, así que viven
con ella en
[`e2e/cypress/support/commands.ts`](https://github.com/marcandreuf/memship/blob/main/e2e/cypress/support/commands.ts).

> **`seed test` se niega a ejecutarse fuera de desarrollo.** Planta contraseñas fijas y visibles en
> el repositorio, así que exige `APP_ENV=development` o `CI`. Para cualquier cosa real, usa la
> configuración interactiva: consulta la [Primera configuración](../getting-started/first-setup.md).

## Correo en desarrollo

El entorno de desarrollo no envía nada hasta que se configura un proveedor: cada envío se registra
en el log y se omite. Hay dos formas de configurarlo, y gana la primera:

1. **Configuración > Correo** en la aplicación en marcha. Se guarda en la base de datos, así que la
   API y el worker de Celery lo recogen sin reiniciar. Es la preferible: es el mismo camino que usa
   quien opera una instalación autoalojada, y es el único que lee el contenedor de la API.
2. **`backend/.env`**: copia `backend/.env.example` y rellena `RESEND_API_KEY` o el bloque
   `SMTP_*`. El fichero es opcional, ningún paso de instalación lo crea, y el worker solo lo lee si
   existe. Su `DATABASE_URL` y su `CELERY_BROKER_URL` se ignoran dentro de los contenedores, ganan
   las claves `environment:` de Compose, así que los valores de localhost con los que viene no
   pueden romper el entorno.

Ojo con la asimetría: el correo que se envía directamente desde una petición (restablecimiento de
contraseña, verificación del correo, el envío de prueba de la propia pantalla de Correo) sale del
contenedor `api`, que no lee `backend/.env`. Solo el correo en cola pasa por el worker. Configúralo
desde la pantalla de Correo para probar los dos caminos.

## Pruebas

```bash
./scripts/dev.sh test                                # the whole backend suite
./scripts/dev.sh test tests/unit                     # one directory
./scripts/dev.sh test tests/unit/test_email.py -k layout   # anything else is passed to pytest
```

1.368 pruebas en unos 40 segundos. Se ejecutan en un contenedor `tests` desechable contra
`db-test`, cuyo directorio de datos es un tmpfs, así que una ejecución no deja nada detrás. Todo lo
que va después de `test` pasa directamente a pytest.

El contenedor apunta Celery a `redis://redis:6379/15` en lugar de al valor por defecto. La batería
encola tareas (dar de alta un socio dispara los correos de verificación y de confirmación), y la URL
del broker por defecto es `localhost:6379`, que en una máquina host resulta ser el Redis de
desarrollo. Así que una ejecución en el host publicaba tareas disparadas por las pruebas en el
broker *de desarrollo*, en la base de datos 0, donde el worker de desarrollo las recogía y las
ejecutaba contra la base de datos de desarrollo. La base de datos 15 no tiene consumidor, así que
una tarea que provoca una aserción no va a ninguna parte. (Es también lo que mantiene rápida la
batería: sin ningún oyente, kombu reintenta cada publicación durante ~19 segundos, y solo eso
llevó un fichero de 3s a 9m53s.)

Ese contenedor es el único sitio donde se construye la etapa `dev` de `backend/docker/Dockerfile`.
Lleva el extra `dev` (pytest, xdist, factory-boy) que la imagen distribuida deja fuera a propósito,
mientras que los contenedores de la API, el worker y beat siguen construyendo la etapa de
producción. Así, el entorno contra el que desarrollas sigue siendo el que se distribuye, y las
dependencias de pruebas nunca llegan a un registro de imágenes. `backend/tests` está montado con
bind mount, así que una prueba editada se ejecuta al momento; solo un cambio de dependencias
necesita reconstruir. La base de datos de pruebas se recrea en cada ejecución (`dev.sh test` borra
`db-test` antes de arrancar), así que una columna añadida a un modelo está ahí la próxima vez que se
ejecuta la batería.

Para las pruebas de extremo a extremo, **ejecuta la batería completa contra una build de
producción**:

```bash
cd e2e && pnpm test:parallel:prod
```

`next dev` compila cada ruta en la primera petición, y con 4 workers compartiendo un servidor de
desarrollo ese parón empuja las navegaciones más allá de sus tiempos de espera: los specs fallan, o
pasan solo al reintentar, y cuáles lo hacen cambia de una ejecución a otra. `test:parallel:prod`
construye, sirve, ejecuta y desmonta.

**Los dos ejecutores en paralelo vuelven a sembrar la base de datos de desarrollo antes de que
empiece la batería** (`seed --test --reset-club-data`, unos 11 segundos). La siembra escribe
periodos de inscripción relativos al día en que se ejecutó, así que un conjunto de datos reutilizado
envejece hasta que esos periodos se cierran y los specs fallan ante un comportamiento correcto.
Esto borra los datos del club que tengas en la base de datos de desarrollo; los superadministradores,
los roles del sistema y los proveedores de pago se conservan. Para ejecutar contra los datos tal
como están, define `E2E_KEEP_DATA=1`:

```bash
cd e2e && E2E_KEEP_DATA=1 pnpm test:parallel:prod
```

Todas las peticiones e2e llegan a la API desde la misma dirección loopback, así que los límites de
autenticación por IP ven toda la batería como un único cliente. El entorno de desarrollo sube el
límite de registro a 1.000 por hora (`REGISTER_LIMIT_PER_IP` en
`backend/docker/docker-compose.yml`; producción se queda en 5), así que las ejecuciones seguidas ya
no hacen fallar los specs de registro con `429`. Los demás límites no cambian. Los contadores están
en memoria, así que `docker compose restart api` los borra todos.

Los reintentos ocultan los fallos, así que mira las capturas en `e2e/cypress/screenshots/`
(ignoradas por git, se sobrescriben en cada ejecución): una captura sin el sufijo `attempt N`
significa que una prueba falló una vez y pasó al reintentar. Una ejecución limpia no deja ninguna.
Los pases intermitentes solo al reintentar bajo carga en paralelo son un problema abierto conocido,
consulta la [incidencia #58](https://github.com/marcandreuf/memship/issues/58).

## Añadir una dependencia al backend

Las dependencias se instalan en el virtualenv de la imagen al construirla, así que una nueva no
está en los contenedores en marcha hasta que reconstruyes. El contenedor de pruebas es una build
aparte de una etapa aparte, así que necesita la suya:

```bash
docker compose -f backend/docker/docker-compose.yml build --no-cache api
docker compose -f backend/docker/docker-compose.yml up -d --force-recreate api celery-worker celery-beat
docker compose -f backend/docker/docker-compose.yml --profile test build tests
```

`backend/pyproject.toml` *sí* está montado en el contenedor de pruebas, pero solo para que la
configuración propia de pytest siga al checkout. Un manifiesto montado no instala nada.

## Logs

| Dónde | Cómo |
|---|---|
| Frontend | `frontend/logs/dev-server.log`, o `./scripts/dev.sh logs frontend` |
| Backend | `./scripts/dev.sh logs backend` |
| Celery | `./scripts/dev.sh logs worker` / `logs beat` |

Celery es el componente que falla en silencio. Si dejan de salir la facturación programada o los
correos de recordatorio, mira ahí antes que en ningún otro sitio.

## Migraciones

El contenedor de la API aplica `alembic upgrade head` en cada arranque, así que una migración que
te has bajado ya está en tu base de datos cuando el contenedor termina de levantarse. Para crear
una:

```bash
./scripts/dev.sh migration "add attachment type allowlist"
```

Se autogenera contra la base de datos de desarrollo en marcha y escribe la revisión en
`backend/alembic/versions` en el host. La orden se ejecuta con **tu** uid y no con el de la imagen,
que es lo que hace que el fichero nuevo sea tuyo para editarlo: el usuario integrado del contenedor
es el uid 1001, y ese no es el de quien opera en todas las máquinas.

## Herramientas del editor

El backend corre en un contenedor; tu editor no. El autocompletado, ir a la definición y la
comprobación de tipos en línea necesitan un intérprete que pueda resolver `fastapi`, `sqlalchemy`
y el resto, y esta es la única razón por la que unas herramientas de Python podrían seguir tocando
tu máquina:

- **Apunta el editor al contenedor**, con VS Code Dev Containers o un intérprete remoto de
  JetBrains, contra el servicio `api`. No se instala nada en el host.
- **Mantén un virtualenv en el host solo como destino del servidor de lenguaje**,
  `cd backend && uv sync --extra dev`. Nunca se ejecuta nada desde él: `dev.sh` no lo lee, y las
  pruebas tampoco.

Las dos son opcionales. El entorno, la batería y las migraciones funcionan sin ninguna de ellas.

## El frontend directamente

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
