# Actividades

Las actividades son eventos, cursos, talleres o competiciones en los que los socios pueden
inscribirse. Cada actividad puede tener modalidades, niveles de precio y reglas de
elegibilidad.

> **In English:** [Activities](../../en/admin-guide/activities.md).
> **En català:** [Activitats](../../ca/admin-guide/activities.md).

## Crear una actividad

Al crear una actividad configuras:

- **Información básica**, nombre, descripción y descripción breve.
- **Fechas**, inicio y fin de la actividad, y el **periodo de inscripción** (apertura y
  cierre).
- **Ubicación**, con detalles y URL opcionales.
- **Capacidad**, mínimo y máximo de participantes.
- **Elegibilidad**, rango de edad (edad mínima/máxima).
- **Cancelación**, permitir o no la cancelación por el socio, y el plazo (horas antes del
  inicio).
- **Imagen de portada**, visible para los socios como miniatura.

## Estados y publicación

Una actividad pasa por los estados **Borrador → Publicada → Archivada** (además de *Cancelada*
y *Completada*). Solo las actividades **publicadas** son visibles para los socios. Usa las
acciones **Publicar**, **Archivar** y **Cancelar actividad** según corresponda.

## Modalidades

Las **modalidades** son variantes de una misma actividad, cada una con su propia **capacidad**,
**precio** y **fecha límite de inscripción** (p. ej. distintos grupos de nivel o turnos).

## Precios

Puedes definir varios **precios**, a nivel de actividad o de modalidad, con **validez temporal**
(*válido desde / hasta*) para configurar, por ejemplo, tarifas de inscripción anticipada. Un
precio puede marcarse como **por defecto** u **opcional**, y un importe de 0 se muestra como
**Gratis**.

## Descuentos

Los **códigos de descuento** pueden ser de tipo **porcentaje** o **importe fijo**, con un número
**máximo de usos** (o ilimitado) y fechas de validez. El socio introduce el código al
inscribirse.

## Consentimientos

Cada actividad puede requerir **consentimientos** (obligatorios u opcionales) que el socio debe
aceptar durante la inscripción. Se ordenan y se editan desde la pestaña correspondiente.

## Documentos adjuntos

Puedes definir **tipos de documento** que el socio debe adjuntar al inscribirse, indicando las
**extensiones permitidas**, el **tamaño máximo** y si son obligatorios.

## Inscripciones

Desde la pestaña **Inscripciones** ves a los socios inscritos y su estado: **Confirmado**, **En
espera**, **Pendiente de pago** o **Cancelado**. Si activas la **lista de espera** en la
actividad, cuando se llena las nuevas inscripciones pasan a ella y se promocionan, por orden, al
liberarse plazas. Puedes **cambiar el estado** de una inscripción manualmente.

## Pago y confirmación de la plaza

En una actividad de pago la plaza queda **pendiente de pago** hasta que se cobra su
[recibo](payments.md): ocupa aforo, pero no está confirmada. Se confirma sola al registrarse el
pago, sea por pasarela, por transferencia o en efectivo. Una actividad gratuita, o un precio 0,
confirma al momento.

- **Formas de pago aceptadas.** Tarjeta, Bizum, transferencia o efectivo. Una actividad de pago
  necesita al menos una para publicarse, y solo se ofrecen las que el club puede cobrar hoy: la
  tarjeta necesita Stripe o Redsys activo, Bizum un Redsys con Bizum habilitado y la
  transferencia el IBAN del club. Al socio solo se le ofrecen las que acepta la actividad, en los
  correos y en *Mis recibos*.
- **Confirmar sin pago.** Confirma una plaza pendiente y anula su recibo. Queda registrado quién
  lo hizo.
- **Cancelar una plaza pagada.** Pasa a **Actividades › Devoluciones** salvo que marques
  *Quedarse el pago*. La devolución se hace desde la pasarela o a mano; en memship solo se marca
  como devuelta. Cancelar desde el panel avisa al socio por correo.
- **Pago tardío.** Si la pasarela cobra una plaza ya liberada, la plaza se recupera si queda
  aforo; si no, el importe pasa a devoluciones. En ambos casos se avisa al club por correo y en el
  panel.

Las actividades creadas antes de esta forma de trabajar llevan la marca **legacy**: confirman la
inscripción al momento y el recibo se cobra después, como siempre. No se pueden cambiar.

### Cancelación automática

Si el socio no paga dentro del plazo, la inscripción se cancela, el recibo se anula y la plaza
pasa al siguiente de la lista de espera. El valor del club se configura en **Configuración ›
Pagos › General** (plazo por defecto: 72 horas) y cada actividad puede activarla, desactivarla o
cambiar el plazo.

Solo se puede activar con los correos *Inscripción pendiente de pago*, *Plaza a punto de
caducar* e *Inscripción cancelada por falta de pago* encendidos en **Configuración › Socios ›
Comunicaciones**: sin ellos, el socio perdería la plaza sin aviso.

> **Al activarla en una actividad que ya tiene plazas pendientes**, o en el club con actividades
> que siguen su valor, esas plazas reciben el plazo completo **a partir de ese momento**, su
> recibo vence en esa fecha y cada socio recibe de nuevo el correo de plaza pendiente, ahora con
> el plazo. Las plazas que ya tenían plazo lo conservan.
