<!-- source: en/getting-started/first-setup.md -->
<!-- source-hash: 8d263d302d8b -->

# Configuración inicial

Después de [instalar](../../en/getting-started/installation.md) _(en inglés)_ Memship y arrancar
los servicios, ejecuta la orden de configuración para crear tu cuenta y configurar tu organización.
Es la misma orden en todos los entornos, y es interactiva.

> **En inglés:** [First-time setup](../../en/getting-started/first-setup.md).
> **En català:** [Configuració inicial](../../ca/getting-started/first-setup.md).

```bash
docker compose exec -it api python -m app.cli.seed
```

Fíjate en el `-it`: la orden hace preguntas, así que necesita un terminal conectado.

## Las tres preguntas

La configuración hace tres preguntas independientes, así que una sola orden cubre todas las
situaciones.

### 1. Superadministrador

La cuenta propietaria de la instancia. Tú eliges la dirección y la contraseña: no hay nada
predefinido, y en este repositorio no existen credenciales para ella en ningún sitio.

Si ya existe un superadministrador, la configuración ofrece en su lugar restablecer su contraseña.
Así es como vuelve a entrar quien administra el servidor si se ha quedado fuera, ver
[Recuperar la contraseña del superadministrador](#recuperar-la-contraseña-del-superadministrador).

### 2. Datos del club

Solo se ofrece cuando la instancia ya tiene datos del club, cosa que en una instalación nueva no
ocurre. Responder *yes* borra todos los socios, actividades, recibos, mandatos y la propia
organización, después de mostrarte el número de filas y pedirte que escribas el nombre de la
organización para confirmar.

**Conserva** las cuentas de superadministrador, los roles del sistema y las pasarelas de pago que
hayas configurado. Esto último es el motivo para usar esto y no borrar el volumen de la base de
datos: las credenciales de las pasarelas viven en la base de datos, cifradas, no en `.env`, así
que borrar el volumen obliga a volver a introducir todos los secretos.

Así es como conviertes una instancia que has evaluado con datos de demostración en la de verdad.

### 3. Configuración del club

O introduces los datos reales de tu organización, o generas un club de demostración.

Para un despliegue real, elige **1) real details**. Solo el nombre es obligatorio; lo que dejes en
blanco se queda en blanco y se puede rellenar más tarde desde **Configuración**. No se inventa
nada: una instancia configurada así empieza sin CIF/NIF y sin IBAN, en vez de con valores de
relleno con aspecto creíble que tendrías que detectar y corregir.

Elige **2) demo club** solo para evaluar o para una demostración que estés preparando. Genera un
año de datos de ejemplo, además de accesos para un administrador del club y dos socios, cuyas
contraseñas generadas se muestran una sola vez al final de la ejecución.

## Los tres roles

| Rol             | Qué puede hacer                                                           |
|-----------------|---------------------------------------------------------------------------|
| **Superadministrador** | Es propietario de la instancia: roles, credenciales, campos personalizados, pasarelas de pago. |
| **Administrador del club** | Lleva el día a día de la organización: socios, actividades, facturación, comunicaciones. |
| **Socio**       | Usa el portal del socio: perfil, actividades, pagos, carné, reservas.     |

El superadministrador crea roles más restringidos (por ejemplo, un tesorero que solo ve la
facturación) desde **Configuración → Roles**. Ver
[Roles y permisos](../reference/roles-and-permissions.md).

### Un segundo superadministrador

Un único superadministrador es un punto único de fallo: si esa persona se va, la única forma de
volver a entrar es con acceso a la shell del servidor. Asciende a un segundo cuanto antes.

Lo hace un superadministrador desde **Configuración → Cuentas**: elige la cuenta y marca
**Super Admin**. Solo un superadministrador ve esa casilla activada; para cualquier otra persona
está desactivada y marcada como exclusiva del superadministrador, porque una cuenta no puede
otorgar un rol que no tiene. Memship se niega además a retirar el último superadministrador, así
que no puedes dejar la instancia sin acceso degradándote a ti mismo.

La cuenta tiene que existir antes. Hoy eso significa que la persona se registró por su cuenta
(cuando el registro público está activado) o que la creó la orden de configuración: todavía no hay
un flujo de "invitar a un usuario" desde la administración.

## Recuperar la contraseña del superadministrador

**Solo desde la máquina, con `python -m app.cli.seed`.** El flujo de contraseña olvidada del
navegador rechaza a propósito a los superadministradores: esa cuenta tiene los permisos de roles y
credenciales, así que permitir que la restablezca un buzón de correo haría que acceder al buzón
equivaliera a ser dueño de la instancia. Además, en la mayoría de instalaciones no funcionaría:
una instalación nueva no tiene SMTP configurado, que es justo cuando necesitas recuperar el acceso.

La petición devuelve la misma respuesta "si el correo existe…" que da ante una dirección
desconocida, así que la página de inicio de sesión nunca revela qué cuentas son de
superadministrador. No llega nada por correo.

En su lugar, en la máquina donde se ejecutan los contenedores:

```bash
docker compose exec -it api python -m app.cli.seed
```

Responde **yes** a "Reset the password for one of them?", indica la dirección y escribe dos veces
la contraseña nueva. Responde *no* a la pregunta de los datos del club y elige **3) Skip for now**
en la configuración del club: un restablecimiento no cambia nada más.

Sin intervención, para una recuperación con script:

```bash
MEMSHIP_ADMIN_PASSWORD='...' docker compose exec -T -e MEMSHIP_ADMIN_PASSWORD api \
  python -m app.cli.seed --admin-email you@example.org
```

Cada restablecimiento se escribe en el registro de auditoría como una actualización de la cuenta,
sin usuario que la haga: quien lo ejecutó tenía acceso a la shell de la máquina, y eso el registro
no puede nombrarlo. Si encuentras uno que no hiciste tú, trátalo como cualquier otro acceso de
nivel root sin explicación.

Los socios normales y los administradores del club no se ven afectados: usan el flujo normal de
contraseña olvidada, que necesita que el [envío de correo](../self-hosting/email.md) funcione.

## Configuración desatendida

Para despliegues automatizados, los mismos tres pasos aceptan opciones en vez de preguntas. La
contraseña se lee del entorno, nunca de la línea de órdenes, donde acabaría en el historial de la
shell y en `ps`:

```bash
MEMSHIP_ADMIN_PASSWORD='...' docker compose exec -T -e MEMSHIP_ADMIN_PASSWORD api \
  python -m app.cli.seed --admin-email you@example.org --club-name "Your Club"
```

**El `-e MEMSHIP_ADMIN_PASSWORD` no es opcional.** `docker compose exec` no pasa al contenedor el
entorno de la shell desde la que se llama, así que sin él la variable está definida en tu máquina
y sin definir donde se ejecuta la orden, y la configuración se detiene con
`--admin-email needs the password in MEMSHIP_ADMIN_PASSWORD`. Nombrar la variable después de
`-e`, sin `=valor`, es lo que la reenvía sin poner la contraseña en la salida de `ps`.

| Opción | Efecto |
|------|--------|
| `--admin-email EMAIL` | Crea el superadministrador, o restablece su contraseña si ya existe. Requiere `MEMSHIP_ADMIN_PASSWORD`. Rechaza una dirección que ya pertenezca a una cuenta que *no* es de superadministrador, en vez de restablecer la contraseña de un desconocido. |
| `--reset-club-data` | Borra todos los datos del club. Sin pregunta de confirmación: es la petición explícita. |
| `--club-name NAME` | Crea la organización con este nombre. |
| `--demo` | Genera en su lugar el club de demostración y sus datos de ejemplo. |

## Iniciar sesión

Abre la URL de tu Memship e inicia sesión como el superadministrador que acabas de crear. La
autenticación es por **correo electrónico + contraseña**.

## 3. Configura tu organización

Desde el panel de administración, ve a **Configuración** y completa:

- **Imagen de marca**: nombre de la organización, color de marca y logotipo.
- **Dirección**: se usa en los recibos y documentos legales.
- **Banca y facturación**: IBAN/BIC, necesarios para la domiciliación SEPA.
- **Facturación**: prefijo del número de factura, tipo de IVA por defecto y reinicio anual opcional
  (p. ej. `FAC-2026-0001`).
- **Idioma por defecto**: español, catalán o inglés.

## 4. Comprueba el envío de correo

Las confirmaciones de dirección, los restablecimientos de contraseña y los avisos de pago dependen
de que el correo esté configurado. Configura el [envío de correo](../self-hosting/email.md) y haz
una prueba antes de dar de alta a socios reales: lanza un restablecimiento de contraseña desde una
cuenta de **socio o de administrador del club**, ya que el flujo rechaza a los superadministradores
y parecería un fallo de envío.

Hazlo antes de abrir el autorregistro: hasta que haya un proveedor configurado, los registros se
rechazan, porque el enlace de confirmación del que dependen no se puede enviar. Ver
[Los socios no pueden iniciar sesión hasta que el correo funciona](../self-hosting/email.md#los-socios-no-pueden-entrar-hasta-que-funcione-el-correo).

## Siguientes pasos

- [Guía de administración → Introducción](../admin-guide/overview.md): cómo está organizado el
  panel de administración.
- [Copias de seguridad y restauración](../self-hosting/backups-and-restore.md): configúralas antes
  de poner la instancia en marcha.
