# Domiciliación SEPA

Cobro de recibos por domiciliación bancaria mediante mandatos SEPA y remesas.

> **Requisito previo.** Configura el **identificador de acreedor** y los datos bancarios de la
> organización en [Ajustes → Domiciliación SEPA](settings.es.md#domiciliación-sepa).

## Mandatos

Un **mandato** es la autorización del socio para domiciliar cobros en su cuenta. Cada mandato
tiene una **referencia**, el **titular** y el **IBAN/BIC** de la cuenta, un **tipo**
(**recurrente** o **puntual**) y una **firma** (**papel** o **digital**).

Flujo habitual:

1. **Nuevo mandato** para el socio.
2. **Descargar PDF** del mandato para su firma.
3. **Subir firmado** el documento (PDF, JPG o PNG).
4. El mandato queda **Activo** y puede usarse en remesas.

Un mandato puede **cancelarse** (acción irreversible); pasa a **Cancelado**. También puede
constar como **Expirado**.

## Remesas

Una **remesa** agrupa recibos domiciliados en un lote para enviarlo al banco.

1. **Nueva remesa** y **selecciona los recibos** — solo recibos **emitidos** o **vencidos** con
   mandatos SEPA activos. Verás el número de recibos seleccionados y el total.
2. **Generar XML** — produce el fichero **ISO 20022 pain.008**, estándar para los bancos de la
   zona SEPA. **Descarga el XML** y preséntalo en tu banca electrónica.
3. **Marcar enviada** cuando lo hayas presentado al banco.
4. **Importar devoluciones** — sube el fichero de devoluciones para actualizar el estado de los
   recibos afectados (se marcan como **Devuelto**). El resultado indica los recibos
   *procesados*, *devueltos* y *no encontrados*.
5. **Cerrar** la remesa para finalizar el lote.

Estados de una remesa: **Borrador → Lista → Enviada → Procesada → Cerrada** (o **Cancelada**;
al cancelar se desvinculan todos los recibos).
