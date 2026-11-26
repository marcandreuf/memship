<!-- source: en/admin-guide/spaces.md -->
<!-- source-hash: 724f69b7d567 -->

# Espacios y reservas

Los espacios son los recursos que el club pone a reservar: una pista, una sala, una calle de
piscina. Cada espacio tiene un horario y **franjas** con fecha, y los socios reservan una franja
desde **Reservar**, en el portal del socio. Los espacios aparecen cuando el módulo de **reservas**
está activado.

> **In English:** [Spaces and bookings](../../en/admin-guide/spaces.md).
> **En català:** [Espais i reserves](../../ca/admin-guide/spaces.md).

## Espacios y franjas

Un espacio tiene nombre, tipo, horario de apertura, un **precio** opcional por reserva (antes de
impuestos) y, si se quiere, los tipos de socio que pueden reservarlo. Una franja es una fecha y
una hora dentro de ese horario, con una **capacidad** (cuántos socios pueden tenerla a la vez) y,
si es distinto del del espacio, su propio precio; un precio de 0 es una franja gratuita en un
espacio de pago. Una regla de repetición crea toda una serie de franjas de una vez.

**Desactivar** un espacio lo oculta a los socios y lo conserva todo. **Borrar** una franja o un
espacio elimina sus reservas para siempre, así que se rechaza mientras alguna tenga dinero de por
medio: una reserva pagada cuya franja aún no ha llegado, o una cancelada con una devolución
pendiente. Cancélalas antes, con lo que queda registrado lo que se debe, o desactiva en lugar de
borrar.

## Pago y confirmación de la reserva

En un espacio de pago, la reserva queda **pendiente de pago** hasta que se paga su
[recibo](payments.md): ocupa plaza, pero no está confirmada. Se confirma sola cuando se registra
el pago, sea por pasarela, por transferencia o en efectivo. Un espacio gratuito o una franja
gratuita se reservan al momento.

- **Formas de pago aceptadas.** Tarjeta, Bizum, transferencia o efectivo. Un espacio con precio
  necesita al menos una, y solo se ofrecen las que el club puede cobrar hoy: la tarjeta necesita
  Stripe o Redsys activos, Bizum un Redsys con Bizum activado y la transferencia el IBAN del club.
  Al socio solo se le ofrecen las que acepta el espacio, en los correos y en *Mis recibos*.
- **Confirmar sin pago.** Desde la pestaña **Reservas** del espacio, confirma una reserva
  pendiente y anula su recibo. Queda registrado quién lo hizo.
- **Marcar un pago recibido.** La columna de pago enlaza con el recibo, donde se marca pagada una
  transferencia o un pago en efectivo; la reserva se confirma sola.
- **Cancelar una reserva pagada.** Pasa a **Devoluciones** salvo que marques *Quedarse el pago*.
  La devolución se hace desde la pasarela o a mano; memship solo la registra como devuelta. El
  socio recibe un correo que le dice que se le devolverá el importe.
- **Pago tardío.** Si la pasarela cobra una reserva ya liberada, la reserva vuelve si la franja
  no ha empezado y hay sitio; si no, el importe pasa a devoluciones. En los dos casos se avisa al
  club por correo y en el panel.

Los espacios creados antes de esta forma de trabajar llevan la marca **legacy**: confirman la
reserva al momento y el recibo se cobra después. A diferencia de una actividad, un espacio legacy
se puede pasar al flujo nuevo desde su formulario de edición. El cambio no se puede deshacer, y
solo siguen el flujo nuevo las reservas que se hagan después.

### El plazo de pago

Toda reserva pendiente tiene un plazo, porque una franja es para una fecha concreta y a menudo
para mañana. En **Configuración › Pagos › General**, en *Reservas de pago*, el club fija:

- **Margen antes de la franja** (60 minutos por defecto): una reserva pendiente debe pagarse como
  tarde este tiempo antes de que empiece la franja. Ninguna reserva llega a su franja sin pagar.
  Ponlo a 0 si cobras en efectivo en la puerta y lo marcas pagado antes de empezar.
- **Tiempo mínimo para pagar** (15 minutos por defecto): una reserva que tendría menos tiempo se
  rechaza, y se le dice al socio por qué. Las franjas demasiado cerca de su inicio se muestran como
  que ya no se pueden reservar.
- **Liberar antes las reservas no pagadas** (desactivado por defecto, 24 horas): si se activa, una
  reserva pendiente también se libera si no se paga en ese tiempo, lo que llegue antes. Cada
  espacio puede seguir al club, activarlo o desactivarlo, o cambiar el tiempo. Al activarlo, las
  reservas ya pendientes adelantan su plazo y se avisa a sus socios.

Al socio se le muestra el plazo antes de reservar, lo recibe en el correo y se le avisa una vez
antes de que venza. Una reserva que no se paga a tiempo se cancela, su recibo se anula y se avisa
al socio.

### Lista de espera

Cuando se libera una plaza en una franja de pago, lo que ocurre depende del tiempo que tendría
para pagarse una reserva hecha en ese momento:

| Tiempo para pagar | Qué ocurre |
|---|---|
| Al menos el *tiempo mínimo para dar la plaza sola* (120 minutos por defecto) | La plaza pasa al primero de la lista de espera, pendiente de pago, y se le dice cómo y hasta cuándo pagar |
| Entre el *tiempo mínimo para pagar* y ese | No se promociona a nadie. Toda la lista de espera recibe un correo de que hay una plaza libre; se la queda quien la reserve y pague primero |
| Menos que el *tiempo mínimo para pagar* | La plaza se queda libre |

En una franja gratuita o legacy, la plaza libre pasa al primero de la lista, como antes.

### Correos

Un espacio de pago libera las reservas no pagadas, así que solo puede cobrar mientras estén
activados los correos *Reserva pendiente de pago*, *Aviso de plazo de una reserva* y *Reserva
cancelada por falta de pago* en **Configuración › Socios › Comunicaciones**. Por lo mismo,
mientras exista un espacio de pago esos correos no se pueden desactivar. Una instalación nueva los
trae activados, junto con *Plaza liberada a última hora*, que lleva el aviso a la lista de espera.

## Política de cancelación

Cada espacio tiene su propia política de cancelación, distinta de la de las actividades. El plazo
de devolución se fija en minutos, horas o días antes del inicio de una franja; si se deja vacío, el
espacio sigue el valor por defecto del club (**Ajustes › Reservas**, 24 horas salvo que se cambie).

- **Antes del plazo** el socio que cancela libera la plaza, y un pago ya hecho se marca como
  *devolución pendiente*.
- **Pasado el plazo** eliges **Rechazar la cancelación** (por defecto) o **Permitirla; el club se
  queda el pago**. En el segundo caso la plaza queda libre, el recibo sigue pagado y no se debe nada.
  *Mis reservas* avisa al socio antes de confirmar.
- **Cuando cancelas tú** una reserva, eliges si el pago se devuelve. Cuando eliminas una franja o un
  espacio, las reservas con dinero se cancelan antes y siempre deben devolverse, porque la causa es
  del club.
- Una reserva que nunca se pagó no tiene nada que devolver. Una reserva pendiente siempre puede ser
  liberada por su socio hasta su plazo de pago.

## Devoluciones y pagos tardíos

**Devoluciones**, a la que se llega desde Actividades o desde Espacios, lista todas las
inscripciones y reservas canceladas cuyo pago hay que devolver, con la forma de pago y la
referencia de la pasarela. Marca cada una como devuelta cuando el dinero se haya devuelto. Los
pagos que llegan después de liberarse su plaza aparecen además como aviso en el panel hasta que
alguien los revisa.
