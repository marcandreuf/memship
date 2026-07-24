# Configuración de la organización

Ajustes generales, facturación, SEPA, proveedores de pago y automatizaciones. Requiere permisos
de administración.

## Datos de la organización

- **Datos de la organización** — nombre, razón social, CIF/NIF, correo, teléfono y sitio web.
- **Imagen de marca** — **color de marca** y **logotipo** (JPG, PNG, WebP o SVG).
- **Dirección** — usada en recibos y documentos legales.
- **Localización** — **idioma por defecto** (se usa en recibos, correos y formato de números),
  zona horaria, moneda y formato de fecha.

## Banca y facturación

- **Banca** — nombre del banco, **IBAN** y **BIC/SWIFT** de la organización.
- **Facturación** — **prefijo de factura**, **siguiente número** y **numeración anual**
  (reinicia la numeración al comienzo de cada año).
- **IVA por defecto** — tipo aplicado por defecto al calcular recibos.

## Domiciliación SEPA

- **Identificador del acreedor** — identificador de acreedor SEPA (p. ej.
  `ES12000B12345678`), obligatorio para generar remesas.
- **Formato SEPA** — ISO 20022 **pain.008**, estándar para los bancos de la zona SEPA.

Ver [Domiciliación SEPA](sepa.es.md) para el flujo de mandatos y remesas.

## Proveedores de pago

Configura las credenciales de las pasarelas de **pago en línea** que verán los socios en
*Pagar ahora*: **Stripe**, **Redsys**, **Bizum** (vía Redsys) y **domiciliación SEPA**. Cada
proveedor tiene un **nombre visible**, un **estado** (Activo / Pruebas / Desactivado) y la
opción **Probar conexión** para validar la configuración.

> Los detalles de credenciales y URLs de retorno de cada proveedor se tratan en la
> [guía de self-hosting](../self-hosting/configuration.md).

## Facturación recurrente

Genera automáticamente los recibos de cuota según un calendario:

- **Activar facturación recurrente**.
- **Día del mes** (1–28) en que se ejecuta. Las cuotas trimestrales y anuales solo se facturan
  en el primer mes de su periodo.
- **Correo de notificación** opcional que recibe un resumen tras cada ejecución.

## Recordatorios de pago

Envía correos automáticos a los socios con recibos vencidos:

- **Días tras el vencimiento** antes del primer recordatorio.
- **Repetir cada (días)** entre recordatorios sucesivos.
- **Recordatorios máximos** por recibo (1–10).

## Otras opciones

- **Comunicaciones** — activa el envío de [anuncios](communications.es.md).
- **Tarjeta de socio** — activa el [carné digital](member-cards.es.md) y su numeración.
- **Campos de perfil** — activa los [campos personalizados](custom-fields.es.md).
- **Opciones de género** — configura las opciones disponibles en los formularios de socios.
