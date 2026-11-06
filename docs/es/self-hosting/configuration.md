<!-- source: en/self-hosting/configuration.md -->
<!-- source-hash: 500c0f9893b8 -->

# Referencia de configuración

Memship se configura con variables de entorno, normalmente definidas en un fichero `.env` junto a
`docker-compose.yml`. Copia `.env.example` a `.env` y ajústalo. Esta página documenta todos los
ajustes que lee el backend.

> **En inglés:** [Configuration reference](../../en/self-hosting/configuration.md).
> **En català:** [Referència de configuració](../../ca/self-hosting/configuration.md).

> **Mínimo para producción:** cambia `SECRET_KEY` y `DB_PASSWORD`, pon en `IMAGE_TAG` una versión
> publicada y configura el [correo](email.md).

## Disposición del despliegue

| Variable            | Por defecto  | Descripción                                                        |
|---------------------|----------|--------------------------------------------------------------------|
| `MEMSHIP_DATA_ROOT` | `./data` | Ruta absoluta que contiene todas las rutas persistentes: base de datos, archivos subidos, estado del planificador, certificados TLS y copias de seguridad. Haz copia de seguridad de ella. Ver la [Instalación](../../en/getting-started/installation.md#the-data-root) _(en inglés)_. |
| `SITE_ADDRESS`      | _(vacío)_ | La dirección que sirve Caddy. Un nombre de máquina sin más (`memship.example.com`) hace que Caddy obtenga automáticamente un certificado de Let's Encrypt; vacío sirve HTTP sin cifrar en el puerto 80. |
| `HOST_UID`          | `1001`   | Uid con el que se ejecutan los contenedores del backend. Ponle tu `id -u` para que los archivos subidos montados con bind mount sean tuyos y se puedan leer sin `sudo`. |
| `HOST_GID`          | `1001`   | Gid, igualmente: tu `id -g`.                                      |

`scripts/install.sh` define las cuatro por ti.

## Seguridad

| Variable      | Por defecto                 | Descripción                                                                 |
|---------------|-------------------------|-----------------------------------------------------------------------------|
| `SECRET_KEY`  | _(se genera en `storage/session.key`)_ | Firma las cookies de sesión y los códigos QR del carné de socio, y de ella se deriva la clave que cifra las credenciales guardadas de las pasarelas de pago. Si la dejas en blanco, se genera una clave propia de la instalación en el primer arranque; **defínela explícitamente** si quieres que sobreviva a la pérdida del directorio de datos. Genérala con `openssl rand -hex 32`. Los valores de ejemplo que vienen en los ficheros de ejemplo se reconocen y se ignoran: cualquier cosa firmada con una clave publicada se puede falsificar. |
| `SESSION_KEY_FILE` | `<STORAGE_LOCAL_PATH>/session.key` | Dónde se guarda la clave de firma generada automáticamente cuando `SECRET_KEY` está en blanco. Tiene que estar en almacenamiento persistente; si no, cada reinicio cierra la sesión de todos los usuarios y las credenciales de pago guardadas dejan de poder descifrarse. |
| `COOKIE_SECURE` | _(se deduce de `FRONTEND_URL`)_ | Fuerza a activado o desactivado el atributo `Secure` de la cookie de sesión. Por defecto se lee el esquema de `FRONTEND_URL`, que es lo correcto salvo que el TLS lo termine un proxy anterior que hable HTTP sin cifrar con Caddy: ahí, pon `true`. |
| `MEMSHIP_SECRET_KEY` | _(se genera en `storage/secret.key`)_ | Cifra las credenciales de SSO y de las pasarelas de pago guardadas en la base de datos. **Defínela explícitamente**: una clave generada automáticamente vive solo en el directorio de datos, así que una máquina reconstruida no puede descifrar sin ella una copia de seguridad restaurada. Cambiarla deja ilegibles las credenciales guardadas. |
| `SECRETS_KEY_FILE` | `<STORAGE_LOCAL_PATH>/secret.key` | Dónde se guarda la clave generada automáticamente cuando `MEMSHIP_SECRET_KEY` no está definida. Tiene que estar en almacenamiento persistente; si no, las credenciales guardadas se vuelven ilegibles tras un reinicio. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30`      | Duración del token de acceso, en minutos.                                  |

## Base de datos

| Variable        | Por defecto                                                    | Descripción                                             |
|-----------------|------------------------------------------------------------|---------------------------------------------------------|
| `DB_PASSWORD`   | `memship`                                                  | **Cámbiala.** Contraseña de PostgreSQL que usa Compose. |
| `DATABASE_URL`  | `postgresql://memship:memship@localhost:5433/memship_db`   | Cadena de conexión completa. En Compose apunta al servicio `db`. |

## Aplicación

| Variable         | Por defecto                 | Descripción                                                        |
|------------------|-------------------------|-------------------------------------------------------------------|
| `APP_ENV`        | `development`            | Ponla a `production` en los despliegues. Afecta al comportamiento de depuración y a si se exponen los documentos de la API. |
| `APP_VERSION`    | _(de la imagen / etiqueta de git)_ | Se incorpora a la imagen al construirla; déjala sin definir cuando uses imágenes publicadas. |
| `DEFAULT_LOCALE` | `es`                     | Idioma por defecto de la interfaz: `es`, `ca` o `en`.             |
| `CORS_ORIGINS`   | `http://localhost:3000`  | Lista separada por comas de los orígenes de navegador permitidos. Pon la URL o URL de tu sitio. |
| `FRONTEND_URL`   | `http://localhost:3000`  | URL pública del frontend; se usa en los enlaces de los correos.   |
| `TRUSTED_PROXY_HOPS` | `1`                  | Cuántos proxies hay delante de la API. Cada uno añade a `X-Forwarded-For` el par del que aceptó la conexión, así que la dirección de quien llama está a ese número de entradas desde la derecha. `1` es el Caddy incluido. El frontend no cuenta como salto: sus rutas de proxy pasan la cabecera sin cambios, así que la API ve la misma cadena tanto si la petición llegó a través de ellas como si fue directa a `/api/v1`. Súbelo si pones cualquier otra cosa delante (una CDN, un balanceador de carga, tu propio proxy inverso); si no, el límite de intentos de inicio de sesión por IP asigna a todos los que llaman la IP de ese proxy y limita todo tu sitio a la vez. Ponlo a `0` solo si la API está publicada sin nada delante, lo que hace que la cabecera la ponga quien llama y que el límite por IP se pueda eludir. |
| `BACKEND_PUBLIC_URL` | `http://localhost:8003` | URL del backend accesible públicamente para las notificaciones de las pasarelas de pago (p. ej. `Ds_Merchant_MerchantURL` de Redsys). En producción **tiene** que ser el nombre de máquina externo al que la pasarela pueda hacer POST. |

## Puertos

Se definen en `.env` para la plataforma de Compose (los valores por defecto están en `.env.example`):

| Variable     | Por defecto | Descripción                    |
|--------------|---------|--------------------------------|
| `HTTP_PORT`  | `80`    | Puerto HTTP de Caddy.          |
| `HTTPS_PORT` | `443`   | Puerto HTTPS de Caddy.         |
| `API_PORT`   | `8003`  | Puerto directo de la API del backend. |
| `DB_PORT`    | `5433`  | Puerto de PostgreSQL en la máquina. |

## Correo

El correo está **desactivado** salvo que haya definida una clave de API de Resend o un servidor
SMTP. Mira [Envío de correo](email.md) para un recorrido completo.

**Resend (preferido, envío gestionado):**

| Variable            | Por defecto | Descripción                     |
|---------------------|---------|---------------------------------|
| `RESEND_API_KEY`    | _(vacío)_ | Activa el envío con Resend.    |
| `RESEND_FROM_EMAIL` | _(vacío)_ | Dirección de remitente verificada. |

**SMTP (alternativa autoalojada):**

| Variable        | Por defecto                 | Descripción                          |
|-----------------|-------------------------|--------------------------------------|
| `SMTP_HOST`     | _(vacío)_               | Activa el envío por SMTP si se define. |
| `SMTP_PORT`     | `587`                   | Puerto SMTP.                         |
| `SMTP_USER`     | _(vacío)_               | Usuario SMTP.                        |
| `SMTP_PASSWORD` | _(vacío)_               | Contraseña SMTP.                     |
| `SMTP_FROM`     | `noreply@memship.local` | Dirección del remitente.             |
| `SMTP_TLS`      | `true`                  | Usar STARTTLS.                       |

Si están configurados los dos, tiene prioridad Resend.

Todas las variables de arriba se pueden definir también desde **Configuración → Integraciones →
Correo**, incluido el servidor SMTP. Una vez guardada esa pantalla, sus valores mandan y el
proveedor activo es el que ella seleccione: ver [Envío de correo](email.md#cuál-está-en-vigor).

## Tareas en segundo plano (Celery / Redis)

| Variable            | Por defecto                    | Descripción                                                |
|---------------------|----------------------------|------------------------------------------------------------|
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Broker de Redis para el correo asíncrono, la facturación recurrente y los recordatorios, y donde se cuentan los límites de intentos de inicio de sesión y de restablecimiento de contraseña, para que todos los procesos de la API los compartan. Redis va incluido en la plataforma de Compose. |
| `CELERY_CONCURRENCY` | `2`                       | Procesos del worker. Cada uno ocupa unos 50 MiB en reposo. El valor por defecto del propio Celery es uno por CPU, que hace crecer la memoria del worker con la máquina y no con la carga de trabajo; las tareas programadas son ligeras, así que dos bastan. Súbelo solo si el correo en cola se acumula. |

El worker y el planificador (Celery beat) se ejecutan como parte de la plataforma y se encargan de
los correos asíncronos, la generación programada de cuotas y los recordatorios de pago.

## Copias de seguridad fuera del servidor

Las lee `scripts/push-backup.sh`, nunca la aplicación. Mira
[Copias de seguridad y restauración](backups-and-restore.md#copias-fuera-del-servidor) para preparar cada destino.

| Variable | Por defecto | Descripción |
|---|---|---|
| `BACKUP_TARGET` | _(vacío)_ | Adónde van las instantáneas: `ssh://user@host[:port]/absolute/path` o `s3://bucket[/prefix]`. Es obligatoria para ejecutar el script. |
| `BACKUP_RETENTION_DAYS` | `30` | Las instantáneas más antiguas que esto se borran del destino tras un envío correcto. |
| `BACKUP_SSH_KEY` | _(por defecto de ssh)_ | Fichero de identidad para un destino `ssh://`. |
| `BACKUP_S3_ACCESS_KEY_ID` | _(vacío)_ | Clave de acceso para un destino `s3://`. |
| `BACKUP_S3_SECRET_ACCESS_KEY` | _(vacío)_ | Su secreto. Se pasa al contenedor por el entorno, nunca en una línea de órdenes. |
| `BACKUP_S3_REGION` | `us-east-1` | Región del bucket. |
| `BACKUP_S3_ENDPOINT` | _(AWS)_ | Endpoint de un almacenamiento que no sea AWS, p. ej. `https://s3.eu-central-003.backblazeb2.com`. |
| `BACKUP_AWS_CLI_IMAGE` | `amazon/aws-cli:2.27.0` | La imagen que ejecuta un envío a `s3://`. |

## Almacenamiento de archivos

| Variable             | Por defecto   | Descripción                                              |
|----------------------|-----------|----------------------------------------------------------|
| `STORAGE_LOCAL_PATH` | `storage` | Ruta dentro del contenedor para los archivos subidos (logotipos, imágenes de actividades, PDF). Se monta con bind mount desde `$MEMSHIP_DATA_ROOT/storage`, que contiene además `secret.key`: inclúyela en las [copias de seguridad](backups-and-restore.md). |
| `MAX_UPLOAD_SIZE_MB` | `10`      | Tamaño máximo de un archivo subido, en megabytes.        |

## Servidor

| Variable | Por defecto   | Descripción                  |
|----------|-----------|------------------------------|
| `HOST`   | `0.0.0.0` | Dirección de escucha del backend. |
| `PORT`   | `8000`    | Puerto del backend dentro del contenedor. |

## Migraciones

| Variable         | Por defecto | Descripción                                                             |
|------------------|---------|-------------------------------------------------------------------------|
| `RUN_MIGRATIONS` | _(puesta a `1` en Compose)_ | Con `1`, el backend ejecuta las migraciones de la base de datos al arrancar. Ver [Actualización](upgrading.md). |
