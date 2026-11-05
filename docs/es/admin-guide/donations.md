# Donaciones

Hay tres formas de recibir una donación. La diferencia no es técnica: es **qué registro
necesitas que quede** y **quién dona**.

## Qué camino te toca

Dos preguntas, en este orden.

> **1. ¿Alguien necesita un registro más allá del panel de la pasarela de pago?** Es decir: un
> recibo con la numeración de la organización, un total anual por donante, o un certificado
> para una deducción fiscal.
>
> - **No** → **camino 1**: publica un enlace de pago en la web de la organización. La pasarela
>   aloja la página, cobra el dinero y guarda el registro. Memship no interviene.
> - **Sí** → sigue a la pregunta 2.
>
> **2. ¿Quién dona?**
>
> - **Una empresa, fundación u organismo** → **camino 2**: dala de alta como
>   [entidad](entities.md) y emite el recibo a su nombre. **No hace falta hacerla socia**: una
>   entidad no tiene cuota, ni acceso al portal, ni inscripciones.
> - **Una persona** → **camino 3**: pasa a ser socia y la donación es un recibo que ella misma
>   descarga desde **Mis recibos**.

El camino 3 no obliga a cobrar una cuota. Un **tipo de membresía con importe base 0** es un
caso previsto: la persona queda registrada, con su recibo y su histórico, sin que la
facturación recurrente le genere nada.

Los caminos 2 y 3 son el mismo mecanismo con distinto titular, y la pestaña **Recibos** es
literalmente la misma pantalla en la ficha de una entidad y en la de un socio.

## Camino 1: un enlace en la web de la organización

Es la respuesta cuando **no quieres registrar al donante en absoluto**. Memship no guarda
donantes anónimos a propósito, así que este camino vive entero fuera de la aplicación. Si el
donante es una empresa y sí quieres su ficha, el camino 2 tampoco la hace socia.

### Cómo se hace

El enlace se crea en el **panel del proveedor de pago**, no en memship. Tanto Stripe como
PayPal ofrecen una URL de donación permanente que no requiere programar nada, y los dos se
pueden configurar para que el donante elija el importe.

- **Stripe**: *Payment Links*. Crea un enlace, marca el importe como personalizable y copia
  la URL.
- **PayPal**: *Botones de donación*. Mismo resultado: una URL que puedes pegar donde quieras.

Publicarlo es un enlace normal:

```html
<a href="https://donate.stripe.com/XXXXXXXX">Hacer una donación</a>
```

No hace falta una clave de API en la web, ni un formulario que procese nada, ni un webhook, ni
despliegue alguno. Esto importa si la web de la organización es un sitio estático, porque no
tiene dónde guardar un secreto.

**PayPal no está integrado en memship**, y Stripe por este camino tampoco: aquí el enlace no
tiene relación con la pasarela que la instancia use para cobrar cuotas. Es la web de la
organización apuntando al proveedor, y nada más.

### Enlaza, no incrustes

Pon un enlace que lleve a la página del proveedor. No metas el formulario de pago dentro de una
página con un `iframe`:

- Memship envía `Content-Security-Policy "frame-ancestors 'none'"` y `X-Frame-Options DENY` en
  todas sus respuestas, así que no se puede incrustar de todos modos.
- Un formulario de tarjeta dentro de una página de terceros es una superficie mucho mayor que
  una redirección a la página del propio proveedor.
- Es también lo que el donante debería ver: primero el sitio de la organización, después el de
  la pasarela, con su candado y su dominio.

### Qué registro queda, y dónde

Esto conviene leerlo despacio, porque lo natural es suponer lo contrario cuando ya estás
acostumbrado a ver el dinero de la organización en un solo sitio:

| Dónde | Queda registro |
|---|---|
| Panel del proveedor de pago | Sí |
| Correo que el proveedor envía al donante | Sí |
| Recibo en memship | **No** |
| Socio en memship | **No** |
| Resumen anual y panel financiero | **No** |

La donación **no aparece en memship**. Ni recibo, ni socio, ni nada en el resumen anual.

### Si quieres cuadrarlo con tus libros

Alguien lo anota a mano. Desde la ficha de un socio, **Recibos → Añadir recibo**, con origen
**Donación** (ver abajo). Es trabajo manual y sin automatizar: si eso pesa, el camino 1 no es
el tuyo.

### Redsys: pregunta a tu banco

Redsys es un TPV bancario, y que exista un enlace de pago permanente depende del banco y del
contrato. La integración de Redsys de memship no puede producir uno: firma un formulario cuyo
identificador de pedido codifica un recibo concreto, así que todo pago que inicia pertenece a
un recibo que ya existe.

Si la organización cobra por Redsys y quiere donaciones públicas, pregunta al banco o usa un
segundo proveedor solo para esto.

## Caminos 2 y 3: la donación como recibo en memship

Cuando sí quieres el registro, la donación es un recibo con **origen Donación**, creado a mano
desde **Recibos → Añadir recibo** en la ficha de la entidad o del socio. La pantalla es la
misma en los dos sitios.

El origen hace tres cosas que `Manual` no hacía:

- **Se puede consultar.** El listado de recibos filtra por origen, y la exportación CSV respeta
  el filtro, así que el total anual de donaciones es una consulta y no una lectura de
  descripciones.
- **No se reclama.** Una donación sin pagar no entra en el ciclo de avisos de impago ni en el
  importe **pendiente** del panel financiero. Una donación que alguien se pensó mejor no es una
  deuda, y nadie debería recibir un recordatorio por ella.
- **Empieza con IVA 0.** Una donación no es una entrega de bienes o servicios. El campo sigue
  siendo editable, porque una donación con contraprestación sí puede estar sujeta; lo que cambia
  es el valor por defecto, que antes era el 21%.

Un socio descarga el PDF desde **Mis recibos** igual que cualquier otro. Una entidad no
tiene portal, así que su recibo lo descarga un administrador desde la ficha y se lo envía.

### El origen Donación cuenta desde esta versión

Los recibos de donación que ya tengas anotados como **Manual** siguen siendo Manual: no hay
forma de reclasificarlos. Nada permite distinguirlos de cualquier otro cargo manual, porque esa
distinción solo estaba en el texto de la descripción.

Si necesitas el total anual de un ejercicio anterior, tendrás que buscarlo por descripción como
hasta ahora. De esta versión en adelante, filtra por origen.

## Relacionado

- [Pagos y recibos](payments.md): el recibo, su ciclo de vida, el IVA y la numeración
- [Entidades](entities.md): empresas, fundaciones y organismos, con recibos a su nombre y sin
  hacerlos socios
- [Guía de proveedores de pago](../../en/admin-guide/payment-providers.md) _(en inglés)_: dar
  de alta Stripe o Redsys en la instancia, para cobrar cuotas
