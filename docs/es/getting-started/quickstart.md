<!-- source: en/getting-started/quickstart.md -->
<!-- source-hash: d496fab5e3d2 -->

# Prueba rápida

Prueba Memship en tu máquina en más o menos un minuto, sin clonar nada. Usa imágenes ya
construidas y está pensado para **evaluar**, no para producción. Para un despliegue real, ve a la
[Instalación](installation.md).

> **En inglés:** [Quick start](../../en/getting-started/quickstart.md).
> **En català:** [Inici ràpid](../../ca/getting-started/quickstart.md).

## Requisitos previos

- Docker y Docker Compose

## 1. Crea una carpeta para ella

Todo lo que sigue se ejecuta desde un único directorio, que acaba conteniendo el único fichero que
esto necesita. Compose toma el **nombre del proyecto** del nombre de ese directorio, y la pila de
prueba rápida guarda sus datos en volúmenes de Docker con el nombre de ese proyecto, así que
ejecuta todas las órdenes `docker compose` de esta guía desde dentro de esta carpeta. Desde
cualquier otro sitio, Compose busca un proyecto distinto y no encontrará ni tus contenedores ni
tus datos.

```bash
mkdir -p "$HOME/memship-quickstart"
cd "$HOME/memship-quickstart"
echo "STACK_PREFIX=$(date +%Y%m%d-%H%M%S)" > .env
```

Esa última línea da a los contenedores de esta pila el nombre del momento en que la pusiste en
marcha, así que `docker ps` te dice qué evaluación es cuál y cuándo la empezaste:
`20261105-043107-memship-api`. Compose lee el `.env` de esta carpeta en cada orden, así que lo
defines una sola vez. También significa que una segunda evaluación en una segunda carpeta tiene
sus propios nombres y puede funcionar junto a esta, con su propio `PORT` y `MAILPIT_PORT`. Si te
saltas la línea, los contenedores se llaman `demo-memship-*`, lo que funciona hasta que quieras
dos.

## 2. Descarga el fichero compose de la prueba rápida y arranca

```bash
curl -fsSL https://raw.githubusercontent.com/marcandreuf/memship/main/docker-compose.quickstart.yml -o docker-compose.yml
docker compose pull          # fetch the latest published images
PORT=8081 docker compose up -d
```

Cambia `PORT=8081` por el puerto que prefieras (por defecto es `80`).

Esto ejecuta las últimas imágenes publicadas, y `/api/v1/health` informa `"version":"latest"`.
Para evaluar una versión concreta, define `IMAGE_TAG` en las dos órdenes. Health informa entonces
de esa versión:

```bash
IMAGE_TAG=3.0.1 docker compose pull
IMAGE_TAG=3.0.1 PORT=8081 docker compose up -d
```

## 3. Ejecuta la configuración

La misma orden configura Memship en todos los entornos. Es interactiva, y hace tres preguntas
independientes:

```bash
docker compose exec -it demo-memship-api python -m app.cli.seed
```

1. **Superadministrador**: tú eliges la dirección y la contraseña. No hay nada predefinido, y no
   se publican credenciales en ningún sitio.
2. **Datos del club**: solo se ofrece cuando los hay, así que en una instalación nueva no hace
   nada.
3. **Configuración del club**: introduce los datos reales de tu organización, o genera un club de
   demostración.

Las tres preguntas tienen también opciones, para automatizar una evaluación o ejecutarla donde no
hay terminal en el que responder:

```bash
# same three steps, unattended
docker compose exec -T -e MEMSHIP_ADMIN_PASSWORD='...' demo-memship-api \
  python -m app.cli.seed --admin-email you@example.org
docker compose exec -T demo-memship-api python -m app.cli.seed --demo

# ... or --club-name instead of --demo, for the real-details path
docker compose exec -T demo-memship-api \
  python -m app.cli.seed --club-name 'Your Organization'
```

Fíjate en `-T` en lugar de `-it`, y en que la contraseña pasa por `docker compose exec -e`: el
contenedor no hereda el entorno de tu shell, y pasarla como argumento la dejaría en el historial
de tu shell y en `ps`. `--reset-club-data` responde a la tercera pregunta. Consulta
`python -m app.cli.seed --help`.

### Qué camino elegir en la pregunta 3

**Si evalúas Memship por primera vez, responde `2) demo club`.** No es solo por tener datos que
mirar. El club de demostración **activa** los módulos opcionales, y una instalación con datos
reales empieza a propósito con casi todos **desactivados**: dos de las veintiuna claves de
funcionalidad, con siete rutas que redirigen al panel. Elige datos reales para ver qué es Memship,
y el carné de socio, el calendario de reservas y los anuncios simplemente no están, sin nada en
pantalla que diga que el módulo existe. [Feature flags](../self-hosting/feature-flags.md) los
enumera todos y explica cómo se activa cada uno.

El club de demostración te da unos 60 socios en todos los estados, actividades, recibos en todos
los estados, mandatos SEPA y avisos en el panel, lo bastante para evaluar el panel de finanzas y
el resumen anual. Se puede volver a ejecutar sin riesgo (es idempotente).

El club de demostración crea además accesos para un **administrador del club** y **dos socios**,
con contraseñas generadas. Se muestran una sola vez, al final de la ejecución:

```
  Accounts:

    super admin  you@example.org             (the password you chose)
    club admin   admin@mediterrani.example   4hVqTmXeb9PkscYRt2Nu
    member       demo0@mediterrani.example   pQ7yKdRfw3TgLmXaB6ns
    member       demo1@mediterrani.example   Zj5rWnEcx8VbHtPqM4dy
```

Eso es una ejecución interactiva que responde a las tres preguntas. Con las opciones de arriba son
dos órdenes, y cada una muestra solo lo que ha creado: el superadministrador con la primera, y el
administrador del club y los dos socios con la ejecución de `--demo`. La ejecución con
`--club-name` no crea accesos, así que no muestra ningún bloque de cuentas.

Guarda esa salida: las contraseñas solo se almacenan como hash y no se pueden volver a mostrar. Los
dos accesos de socio sirven para ver el portal del socio sin repartir una cuenta de administrador,
y es la mitad del producto que una sesión de administrador nunca te enseña.

**Responde `1) real details` solo si quieres evaluar con tus propios datos**, y lee esto antes:

> **Una instancia de prueba rápida no es para quedársela.** Lo que introduzcas, real o no, vive en
> volúmenes de Docker desechables tras una contraseña de base de datos fija, y por defecto todo
> correo que envía la instancia lo recoge el buzón de prueba local en lugar de llegar a la persona
> a la que va dirigido. Eso es lo que la hace segura de tirar, y lo que la hace inadecuada para un
> club. Cuando quieras una instancia que conservar, empieza de nuevo con la
> [Instalación](installation.md), que genera secretos de verdad y pone tus datos en algún sitio
> del que puedas hacer copia de seguridad.

## 4. Abre la aplicación

Ve a **http://localhost:8081** e inicia sesión con el superadministrador que has creado.

> **Sigue siendo una pila de evaluación.** Antes de poner Memship en una red, sigue la
> [Instalación](installation.md) y la
> [Referencia de configuración](../self-hosting/configuration.md). Consulta la
> [pregunta 3 de arriba](#qué-camino-elegir-en-la-pregunta-3) para saber por qué los datos reales
> de los socios no tienen cabida aquí.

## 5. Prueba el alta de un socio

La pila incluye un **buzón de prueba** en **http://localhost:8025**. Todo correo que envía la
instancia (verificación de la dirección, aprobación del registro, recibos, avisos de pago) acaba
allí en lugar de entregarse, sea cual sea la dirección a la que se envió. Este es el flujo que
conviene probar primero:

1. En una ventana privada, abre **http://localhost:8081/register** y regístrate con cualquier
   dirección, real o no.
2. Abre el buzón de prueba, busca el correo de verificación y sigue su enlace.
3. De vuelta en tu sesión de administrador, abre **Altas pendientes** en la barra lateral. El
   nuevo registro aparece allí, junto a unos cuantos que siembra el club de demostración, así que
   pulsa **Aprobar** en su fila y confirma.
4. El correo de aprobación llega al buzón de prueba, y el socio ya puede iniciar sesión.

El buzón es local a tu máquina: se publica solo en `127.0.0.1` y no contiene nada real. Define
`MAILPIT_PORT` junto a `PORT` si el 8025 está ocupado.

Solo está en vigor **mientras Configuración → Correo no se haya guardado nunca**. Configura allí
un proveedor real y a partir de entonces envía ese proveedor, que es la precedencia prevista y no
un fallo: ver [Cuál está en vigor](../self-hosting/email.md#cuál-está-en-vigor).

## Pasar de la evaluación al uso real

No lleves la pila de prueba rápida a producción: instálalo como es debido con la
[Instalación](installation.md), que genera secretos de verdad y pone tus datos en algún sitio del
que puedas hacer copia de seguridad.

Un club de demostración tiene nueve módulos opcionales activados porque quien evalúa debe verlos,
no porque un club deba usarlos. Una instalación real empieza a propósito con casi todos
desactivados, y activas cada uno cuando estés preparado para él. No tomes la configuración del
club de demostración como una recomendación.

Si solo quieres quitar el club de demostración de una instancia que vas a conservar, vuelve a
ejecutar la configuración y responde *yes* a la pregunta de los datos del club. Borra el club de
demostración y conserva tu superadministrador, los roles del sistema y los proveedores de pago que
hayas configurado: ver [Configuración inicial](first-setup.md).

## Pararlo todo

Ejecuta estas órdenes desde la carpeta que creaste en el paso 1: Compose identifica la pila por el
directorio desde el que se ejecuta.

```bash
docker compose stop          # pause it; containers and data stay put
docker compose start         # ... and pick up where you left off
```

```bash
docker compose down          # stop and remove the containers and the network; data kept
docker compose down -v       # ... and delete the data volumes with them
```

`down` conserva la base de datos y los archivos subidos, así que un `docker compose up -d`
posterior trae de vuelta el mismo club. **`down -v` es la que no deja nada**: el club de
demostración, el superadministrador que creaste y todos los recibos se van con ella, y no se
puede deshacer.

Para recuperar también el espacio en disco, elimina las imágenes cuando la pila esté parada:

```bash
docker image rm ghcr.io/marcandreuf/memship-backend:latest \
                ghcr.io/marcandreuf/memship-frontend:latest \
                axllent/mailpit:v1.29
```

Deja `caddy`, `postgres` y `redis` en paz a menos que estés seguro de que nada más en la máquina
las usa: son imágenes públicas corrientes y es muy posible que algo más las use.

### Si ya no estás en esa carpeta

Todo contenedor de la prueba rápida lleva `-memship-` en el nombre, con el prefijo que fuera con
el que se arrancó, así que puedes encontrarlo y pararlo desde cualquier sitio, algo útil si
borraste el directorio o no recuerdas dónde lo pusiste:

```bash
docker ps -a --format '{{.Names}}' --filter name=-memship-   # which stacks exist
docker rm -f $(docker ps -aq --filter name=-memship-)        # remove all of them
```

El prefijo con la fecha y hora es lo que distingue las ejecuciones en ese listado. La segunda
orden elimina todos los contenedores de prueba rápida de la máquina, así que mira la primera si
tienes más de uno en marcha.

Eso elimina los contenedores pero no los datos. Los volúmenes llevan el nombre del proyecto de
Compose, que es el nombre de la carpeta; `docker volume ls | grep demo-memship` los encuentra, y
`docker volume rm <name>` borra uno.
