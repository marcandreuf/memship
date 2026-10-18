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

**Un socio solo puede tener un mandato activo.** Si intentas registrar un segundo, Memship lo
rechaza e indica la referencia y la cuenta del mandato vigente. Cuando un socio cambia de banco,
**anula primero** el mandato actual y registra después el nuevo — el mismo orden que sigue el
papeleo. Si tu instancia viene de una versión anterior a la **2.18.0** y tenía mandatos activos
duplicados, la actualización los canceló y conservó el más reciente.

El **IBAN** se valida al guardarlo, **dígitos de control incluidos**, así que un IBAN con una
cifra mal se rechaza en el formulario en vez de acabar en el fichero del banco — que devolvería
la remesa entera. Puedes pegarlo tal como viene del extracto: mayúsculas y espacios se
normalizan.

Un mandato puede **cancelarse** (acción irreversible); pasa a **Cancelado**. También puede
constar como **Expirado**.

## Remesas

Una **remesa** agrupa recibos domiciliados en un lote para enviarlo al banco.

1. **Nueva remesa** y **selecciona los recibos** — solo recibos **emitidos** o **vencidos** con
   mandatos SEPA activos. Verás el número de recibos seleccionados y el total.

   La **fecha de cobro** no puede ser anterior a hoy — se comprueba contra el día de la
   organización, no el del servidor — porque el banco rechaza el fichero completo si lo es. Si
   cae en fin de semana, el formulario te avisa pero no te lo impide: el plazo mínimo y el
   calendario de liquidación los fija cada banco.
2. **Generar XML** — produce el fichero **ISO 20022 pain.008**, estándar para los bancos de la
   zona SEPA. **Descarga el XML** y preséntalo en tu banca electrónica.

   **El fichero se genera una sola vez y no se sobrescribe**: es el registro de lo que se envió
   al banco. Si necesitas uno distinto — porque un mandato ha cambiado, por ejemplo — **cancela
   la remesa y vuelve a crearla**; al cancelarla sus recibos quedan libres para otra.
3. **Marcar enviada** cuando lo hayas presentado al banco.

   Desde ese momento y hasta que cierres la remesa, sus recibos **no se pueden cobrar ni anular
   a mano**: hay una orden en curso en el banco y Memship no puede afirmar lo contrario. Las dos
   salidas son las de los pasos siguientes — importar la devolución, o cerrar la remesa. Un pago
   con tarjeta o Bizum confirmado por el proveedor sí marca el recibo como cobrado, porque ahí
   el dinero se ha movido de verdad; esa es justamente la situación que describe el aviso del
   paso 4.
4. **Importar devoluciones** — SEPA solo informa de los cobros que **fallan**. Pega las líneas
   de devolución en **JSON** (el cuadro del diálogo muestra el formato), con el número de recibo
   y, si lo tienes, el motivo; no se sube el fichero del banco tal cual. Un texto vacío se
   rechaza: no equivale a "el banco no ha devuelto nada". Si no hay devoluciones, **sáltate este
   paso** en lugar de importar una lista vacía.

   El resultado agrupa los recibos por lo que ha pasado con cada uno — **Devueltos**, **Ya
   constaban devueltos**, **Sin cambios: su estado no admite una devolución**, **Líneas
   repetidas en el fichero**, **No están en esta remesa** (indicando en cuál están) y **No
   encontrados** — y nombra los recibos de cada grupo. Solo pueden marcarse como devueltos los
   recibos **emitidos** o **vencidos**.

   **Si alguna línea corresponde a un recibo que en Memship consta como cobrado, no se importa
   nada.** El banco dice que ha devuelto el dinero y Memship dice que lo cobró: alguien lo cobró
   por otra vía mientras el adeudo estaba en curso. Revisa esos recibos, decide qué cobro es el
   real y vuelve a importar el fichero sin esas líneas.
5. **Cerrar** la remesa cuando haya pasado el plazo de devoluciones. SEPA solo informa de los
   cobros que fallan, así que al cerrar se marcan como **Cobrados** todos los recibos del lote
   que sigan pendientes, con la fecha de cobro de la remesa. Antes de confirmar verás cuántos
   recibos se van a marcar: **una vez cerrada la remesa ya no se pueden importar devoluciones**,
   así que no la cierres antes de que venza el plazo de tu banco.

Estados de una remesa: **Borrador → Lista → Enviada → Procesada → Cerrada** (o **Cancelada**;
al cancelar se desvinculan todos los recibos). Una remesa **Enviada** se puede cerrar
directamente, sin pasar por **Procesada**: el lote en el que ha pagado todo el mundo no tiene
devoluciones que importar.
