# Pagos y recibos

Gestión de recibos, generación de cuotas, IVA y cobros (incluido el pago en línea).

## El recibo y su ciclo de vida

Cada recibo tiene un **número**, un **socio**, una **descripción**, importes (**base**, **IVA**,
**descuento**, **total**) y un **estado**. El ciclo de vida es:

**Nuevo → Emitido → Cobrado** — y, según el caso, **Devuelto**, **Anulado** o **Vencido**.

Acciones disponibles según el estado: **Emitir**, **Cobrar**, **Devolver**, **Anular** y
**Reemitir** (para un recibo devuelto). Desde el recibo también puedes **Descargar PDF**.

## Corregir un recibo emitido

Un recibo emitido no se edita: se corrige emitiendo una **factura rectificativa** desde el
propio recibo (**Emitir rectificativa**). El recibo original conserva su número, sus importes
y su estado; la rectificativa es un documento nuevo, con importe negativo, que toma el
siguiente número de la misma serie y enlaza con el documento que rectifica. Los dos juntos
suman lo que el socio debe realmente.

Puedes rectificar un recibo **emitido, vencido, devuelto o ya cobrado** — incluida, por tanto,
una cantidad cobrada de más. Indicas el **motivo** y, si no quieres rectificar el total, el
**importe**; se pueden emitir varias rectificativas parciales hasta cubrir el importe del
recibo. Una rectificativa no se cobra por remesa ni se puede anular: la devolución del dinero
se hace por el banco.

Anular sigue estando disponible para un recibo que nunca debió emitirse, pero un recibo ya
cobrado solo se corrige con una rectificativa.

## Origen de los recibos

Un recibo puede tener origen:

- **Cuota** — cuota de socio (ver *Generar cuotas* y la
  [facturación recurrente](settings.es.md#facturación-recurrente)).
- **Actividad** — generado automáticamente al confirmar una [inscripción](activities.es.md);
  se anula si la inscripción se cancela.
- **Manual** — creado a mano desde la ficha del socio.

## Generar cuotas

La acción **Generar cuotas** crea recibos para todos los socios activos según su **tipo de
membresía**. Es la forma de emitir la cuota periódica de forma masiva sin crearlos uno a uno.

## IVA y facturación

- El **tipo de IVA** se calcula sobre la base; el tipo por defecto se configura en
  [Ajustes → Facturación](settings.es.md#facturación).
- La **numeración** usa un prefijo configurable y, opcionalmente, se reinicia cada año
  (p. ej. `FAC-2026-0001`).
- El **PDF** del recibo incluye la cabecera de la organización, los datos del socio y el
  desglose de IVA, en el idioma correspondiente (ES/CA/EN).

## Métodos de pago y cobro en línea

Un recibo puede cobrarse por **efectivo**, **transferencia**, **tarjeta**, **domiciliación**
(ver [SEPA](sepa.es.md)) o mediante una **pasarela de pago en línea**.

Cuando hay un proveedor configurado, el socio ve el botón **Pagar ahora** en sus recibos
pendientes y puede pagar con:

- **Stripe** — pago con tarjeta.
- **Redsys** — pasarela bancaria española con 3D Secure.
- **Bizum** — a través de Redsys.

> La confirmación definitiva de los pagos con pasarela llega por la **notificación asíncrona**
> del proveedor, no por la vuelta del navegador. La configuración de proveedores se hace en
> [Ajustes → Proveedores de pago](settings.es.md#proveedores-de-pago) y en la
> [guía de self-hosting](../self-hosting/configuration.md).

## Panel financiero

El [panel](reports.es.md) muestra el estado de los recibos y los importes **pendiente**,
**cobrado este mes** y **vencido**.
