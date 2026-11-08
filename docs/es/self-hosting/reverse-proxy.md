<!-- source: en/self-hosting/reverse-proxy.md -->
<!-- source-hash: f28547d2c7c4 -->

# Detrás de tu propio proxy inverso

Memship viene con Caddy delante: termina el HTTPS, obtiene el certificado, pone las cabeceras de
seguridad y envía cada petición al contenedor que le toca. **Úsalo salvo que tengas un motivo para
no hacerlo.** La instalación lo deja configurado, y para él no hace falta nada de esta página.

> **En inglés:** [Behind your own reverse proxy](../../en/self-hosting/reverse-proxy.md).
> **En català:** [Darrere del teu propi proxy invers](../../ca/self-hosting/reverse-proxy.md).

Esta página es para el otro caso: un servidor que ya ejecuta un proxy inverso para otros sitios, o
una organización cuyo tráfico tiene que pasar todo por su propio proxy. Memship funciona entonces
sin su Caddy, y tu proxy ocupa su lugar. Los contenedores de la aplicación son los mismos en los
dos casos; solo cambia lo que tienen delante. El proxy soportado es **Traefik** (v2 o v3),
mediante etiquetas de Docker.

## Lo que tiene que hacer tu proxy

Estas son las reglas del Caddy incluido, y un proxy externo tiene que mantenerlas todas:

| Petición | Va a |
|---|---|
| `/api/v1/*` | la API, `api:8000` |
| todo lo demás | el frontend, `frontend:3000` |

**No hay ruta `/uploads`, a propósito.** Los archivos subidos llegan al navegador por la ruta
`/api/uploads` del frontend, que pasa la sesión del socio al router autenticado de archivos subidos
de la API. Una regla que envíe `/uploads` directamente a la API se salta esa comprobación. Cuando
ese router era un montaje de archivos estáticos, una regla así entregaba la clave de cifrado y los
ficheros SEPA. Si tu proxy suele añadir una ruta `/uploads` para aplicaciones como esta, aquí no
la añadas.

Además, cada respuesta necesita estas cabeceras, las mismas que pone el Caddy incluido:

| Cabecera | Valor |
|---|---|
| `X-Content-Type-Options` | `nosniff` |
| `Content-Security-Policy` | `frame-ancestors 'none'` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Strict-Transport-Security` | `max-age=31536000` |
| `Server` | eliminada |

No las juzgues desde una pestaña del navegador: el frontend pone cuatro de ellas por su cuenta,
así que una página puede parecer completa mientras a todas las respuestas de `/api/v1/*` les
faltan. Compruébalo con `curl -sI https://<your-host>/api/v1/health`.

## Configurarlo con Traefik

`docker-compose.external-proxy.yml`, junto a `docker-compose.yml`, hace todo lo anterior con
etiquetas de Traefik:

- desactiva el Caddy incluido
- une la API y el frontend a la red de Docker de tu proxy
- envía `/api/v1/*` a la API y todo lo demás al frontend, sin ruta `/uploads`
- añade las seis cabeceras como un único middleware, asociado a los dos contenedores
- da a las llamadas de vuelta de los proveedores de pago (`/api/v1/webhooks/*`) un router propio

**1. Tu Traefik.** Tiene que estar ya en marcha con el proveedor de Docker, un entrypoint HTTPS y
un resolutor de certificados (certificate resolver), y conectado a una red de Docker a la que
puedan unirse los contenedores de Memship. Apunta el nombre de la red, el del entrypoint y el del
resolutor.

**2. Instala como siempre,** siguiendo la [Instalación](../getting-started/installation.md), con
`--domain` puesto al nombre de máquina que servirá tu proxy. Eso escribe `FRONTEND_URL`,
`CORS_ORIGINS` y `BACKEND_PUBLIC_URL` como `https://<your-host>`, de lo que dependen los enlaces
de los correos, el inicio de sesión y las llamadas de vuelta de los pagos. `install.sh` comprueba
que el nombre resuelve a este servidor, igual que hace con el Caddy incluido.

**3. Activa el overlay en `.env`:**

```bash
COMPOSE_FILE=docker-compose.yml:docker-compose.external-proxy.yml
MEMSHIP_HOST=memship.example.org
TRAEFIK_NETWORK=traefik
TRAEFIK_ENTRYPOINT=websecure
TRAEFIK_CERTRESOLVER=letsencrypt
```

`MEMSHIP_HOST` es el nombre de máquina sin `https://`. Las otras tres toman los nombres del paso
1; los valores que se ven son los predeterminados. `COMPOSE_FILE` es lo que hace que todas las
órdenes `docker compose` lean los dos archivos, incluidas las de los scripts: no hay ninguna orden
aparte que recordar.

**4. Aplícalo.** `install.sh` arrancó el Caddy incluido, y desactivarlo en el overlay no detiene un
contenedor que ya está en marcha, así que elimínalo primero y luego recrea el resto:

```bash
docker compose stop caddy
docker compose rm -f caddy
docker compose up -d
```

Hasta que Caddy desaparece ocupa los puertos 80 y 443, y tu proxy no puede tomarlos si se ejecuta
en el mismo servidor.

**5. Compruébalo**, desde cualquier máquina:

```bash
curl -sI https://memship.example.org/api/v1/health
```

Debe responder `200` con las cinco cabeceras de la tabla de arriba y sin línea `Server`.

## Llamadas de vuelta de los pagos y control de acceso

Si pones el sitio detrás de la autenticación básica o el inicio de sesión único de tu proxy, para
una demo o una copia de pruebas, añade ese middleware solo a los routers `memship-api` y
`memship-frontend`, **nunca** a `memship-webhooks`. Stripe y Redsys llaman a esa ruta desde sus
propios servidores y se identifican con una firma, no con una contraseña: un inicio de sesión
delante de ella rechaza todas las confirmaciones de pago, y los recibos pagados se quedan sin
pagar.

## Actualizaciones, copias de seguridad y restauraciones

No cambia nada. `upgrade.sh`, `db-backup.sh` y `db-restore.sh` ejecutan `docker compose` desde el
directorio de instalación, así que leen `COMPOSE_FILE` y mantienen el overlay; `push-backup.sh`
saca su volcado mediante `db-backup.sh`.
`install.sh` recarga el Caddy incluido tras una actualización solo cuando Caddy forma parte de la
pila, así que una actualización nunca lo arranca junto a tu proxy.

La API sigue publicada en `127.0.0.1:8003`, solo en loopback, como en la configuración
predeterminada. `verify-deployment.sh` comprueba ahí la salud de la API tras una actualización;
nada de fuera del servidor puede llegar a ella.

## Volver al Caddy incluido

Quita la línea `COMPOSE_FILE` del `.env` (las otras cuatro pueden quedarse, entonces no se usan),
apunta el DNS del dominio al servidor si tu proxy estaba en otra máquina, libera los puertos 80 y
443 si tu proxy se ejecuta en el mismo servidor, y ejecuta `docker compose up -d`. Caddy arranca y
pide su certificado.
