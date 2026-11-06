<!-- source: en/self-hosting/feature-flags.md -->
<!-- source-hash: 70b6870a042d -->

# Feature flags

Memship trae todos los módulos en una sola imagen. Cuáles usa de verdad una organización lo deciden
**veintiuna claves** en una única columna JSONB, `organization_settings.features`, en la única fila
que admite la base de datos (`CHECK (id = 1)`). Se editan desde **Configuración** en el portal de
administración, no desde el `.env` ni desde un fichero del servidor. Nada de esto necesita
reiniciar.

> **En inglés:** [Feature flags](../../en/self-hosting/feature-flags.md).
> **En català:** [Feature flags](../../ca/self-hosting/feature-flags.md).

Esta página existe porque "el flag no está" y "el flag está desactivado" son lo mismo para la
aplicación pero no para una persona que mira una pantalla, y hasta que se puso por escrito no
había forma de distinguir un módulo que nadie había activado de un módulo que estaba roto.

## Con qué empieza una instalación nueva

**Dos de las veintiuna.** Todas las demás están ausentes.

| Definida | Por qué |
|---|---|
| `custom_roles` | La capa de permisos está siempre activa; ocultar la única pantalla que puede ajustarla no ayuda a nadie. |
| `gender_options` | Cinco opciones sembradas, para que el formulario de socio tenga algo que ofrecer desde el primer día. |

Es deliberado, no un descuido. Un club activa cada módulo cuando está preparado para él, e
`install.sh` produce exactamente este estado. Eso sí, hace que un primer arranque se vea escaso:
**siete rutas redirigen al panel** hasta que se activa su módulo.

| Ruta | Necesita |
|---|---|
| `/communications`, `/announcements` | `communications` |
| `/spaces`, `/book`, `/my-bookings` | `bookings` |
| `/scan`, `/my-card` | `member_card` |

Un módulo desactivado además **responde 404 en sus propios endpoints**, y por eso el frontend
redirige en vez de pintar un armazón sobre una API muerta.

**Ausente no siempre significa desactivado.** Dos claves valen *activado* por defecto cuando
faltan, `public_registration` y `registration_requires_approval`, las dos leídas como
`features.get(key, True)` en `domains/auth/service.py`. Así que en una instalación nueva el alta
está abierta *por política*, y cada alta cae en la cola de aprobación pendiente en vez de
convertirse en un socio activo. Si no quieres un formulario de alta abierto, pon
`public_registration` a `false` explícitamente: quitar la clave hace lo contrario de lo que parece.

Abierto por política no es lo mismo que funcionando. `POST /auth/register` se niega con **503,
"the club has not finished setting up email"** hasta que hay un transporte de correo configurado,
porque confirmar una dirección necesita un enlace y el enlace necesita un transporte. Es
deliberado: es mejor que crear una cuenta en la que nadie podrá entrar nunca. En una instalación
autoalojada nueva es la respuesta que recibe cualquier visitante, así que el formulario de alta
está abierto en Configuración y cerrado en la práctica hasta que configures Resend o SMTP. Comprobado en
una instalación limpia, no deducido.

## ¿Quieres una instancia ya configurada?

```bash
python -m app.cli.seed --demo     # or: ./scripts/dev.sh seed demo
```

El camino de demostración activa **las veintiuna** y llena detrás de ellas los datos de un club
entero. Es para evaluar y revisar, nunca para una organización real, porque además crea socios y
recibos de demostración.

> **También arma las tareas programadas.** `recurring_billing_enabled`,
> `payment_reminders_enabled` y `membership_lapse_enabled` son interruptores que lee una tarea de
> Celery beat a las 02:00, 03:00 y 04:00 UTC. Mientras están activados, una instancia en marcha
> genera recibos, marca como vencidos los impagados y pasa al plan gratuito a los socios cuya
> cuota ha caducado. Se está comportando correctamente, pero sus datos no estarán exactamente
> como los dejaste.
>
> **La caducidad no suspende a nadie.** Un socio caducado es un socio de pleno derecho en el plan
> gratuito: `Member.status` no se toca a propósito, y el plan anterior se guarda en
> `Member.membership_reverted_from_id` para que pagar la cuota lo restituya (ver
> `lapse_service.py` y memship#145). Por eso los recuentos de estado de los socios en el panel no
> se mueven cuando se ejecuta una pasada de caducidad.
>
> **Son horas UTC, y UTC no es tu jornada laboral.** En UTC+9 se disparan a las 11:00, 12:00 y
> 13:00, en plena mañana de trabajo, no de madrugada. Si estás revisando o haciendo una demostración
> de una instancia y quieres que sus datos se queden quietos, desactiva estos tres mientras tanto.
> Controlan trabajo programado y no tienen pantalla propia, así que no pierdes nada que puedas ver
> por hacerlo.

## Las veintiuna

En esta columna conviven tres tipos de cosa distintos, y no se comportan igual.

- **Compuertas**: desactivada significa que se rechaza una petición. Son las que redirigen.
- **Valores**: parametrizan el comportamiento en vez de bloquearlo. Si falta uno, se recurre a un
  valor por defecto escrito en el código, así que la instancia *ya está funcionando con ese
  número* exista o no la clave.
- **Datos**: una lista, validada entrada a entrada al guardarla.

| Clave | Tipo | Si falta | Controla |
|---|---|---|---|
| `custom_roles` | compuerta | desactivada | la pestaña Cuentas/Roles de Configuración |
| `communications` | compuerta | desactivada | `/communications`, `/announcements` |
| `member_card` | compuerta | desactivada | `/scan`, `/my-card` |
| `bookings` | compuerta | desactivada | `/spaces`, `/book`, `/my-bookings` |
| `custom_profile_fields` | compuerta | desactivada | los campos de socio personalizados |
| `public_registration` | compuerta | **activada** | el autorregistro, aunque responde 503 hasta que se configura el correo |
| `registration_requires_approval` | compuerta | **activada** | la cola de aprobación pendiente |
| `payment_reminders_enabled` | compuerta | desactivada | la pasada de recordatorios de impago y los recordatorios manuales |
| `recurring_billing_enabled` | compuerta | desactivada | la pasada programada de cuotas de socio |
| `membership_lapse_enabled` | compuerta | desactivada | la pasada programada que devuelve a los socios caducados al plan gratuito |
| `reminder_days_after_due` | valor | **3** | días tras el vencimiento antes del primer recordatorio |
| `reminder_repeat_days` | valor | **7** | días entre repeticiones |
| `reminder_max_count` | valor | **3** | recordatorios por recibo |
| `recurring_billing_day` | valor | **1** | día del mes en que emite la pasada de facturación |
| `membership_fee_due_days` | valor | **7** | días desde la emisión hasta el vencimiento |
| `membership_lapse_grace_days` | valor | **21** | días tras el vencimiento antes de que caduque un socio |
| `booking_window_days` | valor | **14** | con cuánta antelación puede reservar un socio (1–365) |
| `booking_cancellation_deadline_hours` | valor | **24** | plazo límite de cancelación (0–8760) |
| `booking_waitlist_enabled` | valor | **activado** | si una franja llena ofrece lista de espera |
| `billing_notification_email` | valor | *sin definir* | adónde van los resúmenes de las pasadas de facturación y el resumen diario de notificaciones de pago; sin efecto si no está definido, se valida como dirección al guardar |
| `gender_options` | datos | no se ofrece ninguna opción | el campo de género del formulario de socio |

Los valores por defecto de arriba son los valores de reserva literales de `reminder_service.py`,
`recurring_billing_service.py`, `lapse_service.py` y `bookings/rules.py`. Dos tests de
`backend/tests/integration/test_demo_data.py` los protegen: uno fija los seis valores numéricos
por defecto frente a lo que escribe la siembra de demostración, y el otro fija los tres flags que
están **activados mientras faltan**.

Conviene ser preciso con lo que eso cubre y lo que no: los dos comparan *código* con *código*.
Ninguno lee esta página, así que una fila de aquí puede seguir desviándose del valor de reserva que
describe, que es lo que le pasó a `booking_waitlist_enabled`, que figuraba como desactivado
durante todo el tiempo que el código lo tuvo activado por defecto.

## Desactivar uno no es lo mismo que no haberlo activado nunca

Un **valor** no tiene estado desactivado ni redirección. Poner `reminder_max_count` fuera de rango
es una situación distinta de dejarlo ausente: cada valor se comprueba contra su rango al guardar y
se rechaza con un 422, y los que se leen a través de un registro además recurren a su valor por
defecto en vez de lanzar un error si una instancia antigua ya tiene uno incorrecto guardado. Si
estás revisando esta zona, a un valor hay que mirarle *qué hace la pantalla con un número sin
sentido*, algo que las compuertas no necesitan en absoluto.

## Se rechaza cualquier clave que esta página no liste

Las veintiuna de arriba son el conjunto completo, y `PUT /api/v1/settings/` responde **422** a
cualquier otra, nombrando la clave que no ha reconocido.

Esto importa si configuras una instancia a través de la API en vez de las pantallas de
administración. Antes de que se aplicara, un nombre de flag mal escrito se aceptaba, se guardaba y
no hacía nada sin avisar: la actualización fusiona de forma parcial, así que cualquier clave que
llevara la petición se escribía y se conservaba para siempre, sin nada en ningún sitio que dijera
que el ajuste no tenía efecto. `booking_window_day` en vez de `booking_window_days` costó
exactamente eso.

Dos consecuencias que conviene conocer:

- **La ausencia sigue estando bien.** La regla es que se rechaza una clave desconocida, nunca que
  sea obligatoria cada clave conocida. Una instalación nueva guarda un subconjunto y el resto se
  resuelve con los valores por defecto de la tabla de arriba.
- **Envía solo las claves que cambias.** Una clave que ya estaba en la columna desde antes de que
  esto se aplicara se deja en paz, así que una instancia que tenga una sigue funcionando, pero un
  cliente que lee el diccionario `features` entero y lo vuelve a enviar reenvía esa clave y será
  rechazado. Reenviar una instantánea nunca fue necesario, porque el endpoint fusiona.

Si necesitas un sitio donde guardar valores propios, `custom_settings` es una columna aparte en la
misma fila y acepta cualquier cosa.

## Una coincidencia de nombres que conviene conocer

`activities.features` es una **columna distinta** en otra tabla, y contiene una clave
`waiting_list`. Un grep de `features` encuentra las dos. Nada en `organization_settings.features`
se llama `waiting_list`, y la clave a nivel de actividad no tiene nada que ver con
`booking_waitlist_enabled`.

## Relacionado

- [Referencia de configuración](configuration.md), las variables de entorno, que son un mecanismo
  completamente aparte
- [Primera puesta en marcha](../getting-started/first-setup.md)
