<!-- source: en/admin-guide/payment-providers.md -->
<!-- source-hash: 4af8128ca6e4 -->

# Proveedores de pago: guía de configuración

**Para quién es:** la persona que administra una instalación de memship para su club o asociación
(el **superadministrador**).
**Qué cubre:** todo lo que hay en **Configuración → Pagos → Proveedores de pago**, la conexión con
**Stripe** para pagos con tarjeta y con **Redsys** para la pasarela bancaria española y **Bizum**.

> **En inglés:** [Payment providers: Setup Guide](../../en/admin-guide/payment-providers.md).
> **En català:** [Proveïdors de pagament: guia de configuració](../../ca/admin-guide/payment-providers.md).

No tienes que editar ningún archivo ni reiniciar nada. Todas las credenciales de esta guía se
introducen en la interfaz web y se aplican en la siguiente petición.

---

## Índice

1. [Antes de empezar](#1-antes-de-empezar)
2. [Cómo se protegen los secretos](#2-cómo-se-protegen-los-secretos)
3. [Cómo se completa realmente un pago en línea](#3-cómo-se-completa-realmente-un-pago-en-línea)
4. [Stripe](#4-stripe)
   - [Qué necesitas](#41-qué-necesitas)
   - [Obtener las claves de API](#42-obtener-las-claves-de-api)
   - [Crear el endpoint del webhook](#43-crear-el-endpoint-del-webhook)
   - [Rellenar la pantalla](#44-rellenar-la-pantalla)
   - [Pruebas](#45-pruebas)
   - [Resolución de problemas de Stripe](#46-resolución-de-problemas-de-stripe)
5. [Redsys y Bizum](#5-redsys-y-bizum)
   - [Qué necesitas](#51-qué-necesitas)
   - [Obtener las credenciales de tu banco](#52-obtener-las-credenciales-de-tu-banco)
   - [Por qué no hay webhook que configurar](#53-por-qué-no-hay-webhook-que-configurar)
   - [Rellenar la pantalla](#54-rellenar-la-pantalla)
   - [Pruebas](#55-pruebas)
   - [Resolución de problemas de Redsys](#56-resolución-de-problemas-de-redsys)
6. [Activación, modo de pruebas y lo que ven los socios](#6-activación-modo-de-pruebas-y-lo-que-ven-los-socios)
   - [Cuando falla una notificación de pago](#61-cuando-falla-una-notificación-de-pago)
7. [Referencia de campos](#7-referencia-de-campos)

---

## 1. Antes de empezar

**Acceso.** Pagos solo es visible para los usuarios con el rol de **superadministrador**. Un
administrador normal no ve la pestaña. Ve a **Configuración → Pagos** y luego a la subpestaña
**Proveedores de pago**.

**Una dirección pública.** Los dos proveedores necesitan llegar a tu instalación desde internet para
confirmar un pago. Esa dirección se configura una sola vez al instalar, en `BACKEND_PUBLIC_URL` y
`FRONTEND_URL`. Un proveedor configurado en una instalación a la que internet no llega cobrará el
dinero y nunca marcará el recibo como cobrado.

**La domiciliación es otra cosa.** Si tus socios pagan por domiciliación SEPA, nada de esto se
aplica: consulta [SEPA](sepa.md). Esta guía trata solo del pago en línea con tarjeta o Bizum.

---

## 2. Cómo se protegen los secretos

El cifrado, el almacenamiento y la copia de seguridad funcionan igual que en el resto de
Configuración, y se describen por completo en [Integraciones → Cómo se protegen los
secretos](integrations.md). La edición difiere en una cosa, en el último punto de abajo. En
resumen:

- Los valores secretos se **cifran antes de guardarse** en la base de datos.
- **Nunca se devuelven al navegador.** Un secreto guardado no es un campo de entrada: se muestra
  como texto (`••••` más los cuatro últimos caracteres y la palabra *guardado*) junto a un botón
  **Reemplazar**, y el campo solo aparece cuando lo pulsas. Es lo esperado, no un fallo, y es
  deliberado: un gestor de contraseñas no tiene ningún campo que rellenar, así que no puede
  sobrescribir en silencio una credencial que funciona la próxima vez que guardes.
- **Haz copia de seguridad del archivo de la clave de cifrado junto con tu base de datos.** Si
  restauras un volcado en una máquina con otro archivo de clave, los secretos guardados no se
  pueden descifrar y tendrás que volver a introducirlos.
- **Un secreto guardado no se puede vaciar.** Guardar un valor en blanco encima se rechaza,
  indicando el campo, y el valor guardado se queda como estaba. Aquí no hay *Borrar*, a diferencia
  de las pantallas de Integraciones, que lo tienen porque una integración se puede desactivar
  legítimamente quitando su credencial. El secreto de un proveedor de pago solo se reemplaza: pulsa
  **Reemplazar** y pega el valor nuevo. Si vas a retirar el proveedor, elimina su fila, cosa que la
  pantalla rechaza mientras haya recibos vinculados a él.

> **¿Por qué rechazarlo en lugar de aceptar el blanco?** El valor guardado está cifrado y es la
> única copia: nada puede recuperarlo una vez sobrescrito. Un campo en blanco casi siempre es un
> pegado que ha salido mal, no una instrucción, y antes de la v2.19.0 se aceptaba: el secreto se
> sustituía por nada y, en un proveedor que seguía *desactivado*, el guardado se daba por correcto.

Qué campos se tratan como secretos depende del proveedor, y no es arbitrario: una clave publicable
está pensada para ser pública, así que se guarda en claro y se muestra entera.

| Proveedor | Cifrado | Guardado en claro |
|---|---|---|
| Stripe | `secret_key`, `webhook_secret` | `publishable_key` |
| Redsys | `secret_key` | `merchant_code`, `terminal_id`, `environment`, `currency_code` |

---

## 3. Cómo se completa realmente un pago en línea

Merece la pena entenderlo antes de configurar nada, porque explica *para qué* sirven las
credenciales y por qué un error de configuración es silencioso y no ruidoso.

Cuando un socio paga ocurren tres cosas, y solo una de ellas es la que cuenta:

1. **memship envía al socio al proveedor.** En Stripe es una redirección a una sesión de Checkout;
   en Redsys, un formulario firmado que se envía solo a la página del TPV del banco.
2. **El socio paga y su navegador vuelve** a una página de memship. **Esta vuelta no es la
   confirmación.** El socio puede cerrar la pestaña, perder la cobertura o pulsar atrás, y el
   navegador no es una parte de la que memship pueda fiarse para saber si se movió el dinero.
3. **El proveedor hace una llamada de servidor a servidor a memship** confirmando el resultado.
   **Esta es la fuente de verdad**, y es lo único que marca un recibo como cobrado.

Todo lo que dice esta guía sobre webhooks, URL de notificación y claves de firma existe para que
funcione el paso 3 y para demostrar que la llamada viene de verdad del proveedor.

**Por eso también una configuración rota es silenciosa.** El endpoint que recibe la llamada no
tiene autenticación por diseño: la seguridad viene de verificar la firma del proveedor, no de un
inicio de sesión. Si el secreto de firma es incorrecto, todas las confirmaciones fallan la
verificación y se descartan. Para el socio, el pago ha ido bien; en memship el recibo sencillamente
sigue pendiente, y ninguna pantalla muestra un error. **Haz siempre un pago de prueba real de
principio a fin antes de anunciar un método de pago a los socios.**

---

## 4. Stripe

Stripe gestiona los pagos con tarjeta mediante Stripe Checkout, una página de pago alojada por
Stripe. Los datos de la tarjeta nunca llegan a tu servidor.

### 4.1 Qué necesitas

Una cuenta de Stripe y, de ella, tres valores: una **clave secreta**, una **clave publicable** y un
**secreto de firma del webhook**. Los dos primeros salen de la página de claves de API. El tercero
todavía no existe: lo creas en el paso 4.3.

### 4.2 Obtener las claves de API

1. Inicia sesión en [dashboard.stripe.com](https://dashboard.stripe.com).
2. Ve a **Developers → API keys** ([documentación](https://docs.stripe.com/keys)).
3. Copia la **Publishable key**, que empieza por `pk_`.
4. Muestra y copia la **Secret key**, que empieza por `sk_`.

Stripe tiene claves distintas para el modo de prueba y el modo real, que se eligen con el
interruptor del panel. Las claves de prueba son `pk_test_` / `sk_test_`, y las reales `pk_live_` /
`sk_live_`. Usa las de prueba hasta haber completado un pago de prueba de principio a fin.

> memship comprueba que la clave secreta empiece por `sk_` y la publicable por `pk_`, y se niega a
> guardar un valor en el campo equivocado. **No** comprueba a qué modo pertenece una clave: emparejar
> una clave secreta real con una publicable de prueba se acepta y fallará en el momento del pago.

### 4.3 Crear el endpoint del webhook

**Este es el paso en el que la gente se atasca, así que lee con atención la frase siguiente.** El
webhook es algo que creas *tú* en Stripe, apuntando a memship. memship no crea nada en tu cuenta de
Stripe. El secreto que acabas pegando en memship lo emite Stripe *después* de que exista el
endpoint.

**La URL que necesitas es:**

```
https://<your-memship-address>/api/v1/webhooks/stripe
```

No tienes que construirla a mano: el formulario del proveedor Stripe en **Configuración → Pagos →
Proveedores de pago** la muestra, construida a partir de `BACKEND_PUBLIC_URL`, con un botón para
copiarla. El prefijo `/api/v1/` importa: la configuración del proxy inverso incluida solo envía
`/api/v1/*` a la API y manda todo lo demás a la interfaz web, así que una URL sin él llega al
servicio equivocado y Stripe informará de fallos.

Después, en el panel de Stripe ([documentación de webhooks](https://docs.stripe.com/webhooks)):

1. Ve a **Developers → Webhooks → Add endpoint**.
2. **Endpoint URL**: la URL de arriba.
3. **Events from**: *Your account*.
4. **Payload style**: **Snapshot**. Esto importa: memship lee el objeto completo del evento, y un
   payload *Thin* solo lleva identificadores, así que las confirmaciones llegarían sin nada con lo
   que actuar.
5. **API version**: la predeterminada sirve. memship no fija ninguna versión y solo lee campos de
   Checkout Session que llevan mucho tiempo estables.
6. **Select events**: elige exactamente estos dos:
   - `checkout.session.completed`
   - `checkout.session.expired`
7. Crea el endpoint y luego **muestra el Signing secret**. Empieza por `whsec_`. Es el valor que
   memship llama **Secreto del webhook**.

> **Suscríbete solo a esos dos eventos.** memship ignora cualquier otro tipo de evento, así que
> suscribirse a más no hace daño más allá de generar tráfico y ruido en los registros de Stripe,
> pero un panel lleno de entregas que memship descarta a propósito hace más difícil ver un problema
> real.

### 4.4 Rellenar la pantalla

En **Configuración → Pagos → Proveedores de pago**, añade un proveedor Stripe e introduce:

| Campo | Valor |
|---|---|
| Clave secreta | la clave `sk_…` del 4.2 |
| Clave publicable | la clave `pk_…` del 4.2 |
| Secreto del webhook | el secreto `whsec_…` del 4.3 |

Un proveedor recién creado empieza **desactivado**. Configúralo primero, pruébalo y luego actívalo.

> **El Secreto del webhook se comprueba, pero solo en su forma.** memship se niega a guardar un
> valor que no empiece por `whsec_`, así que el error de pegado habitual (una clave secreta, una
> clave publicable, algo de la casilla equivocada) se detecta en el momento de guardarlo y no al
> activarlo. Lo que ninguna comprobación local puede detectar es un secreto *con la forma correcta*
> de otro endpoint: uno antiguo, o uno de un endpoint que borraste. Parece idéntico, se guarda sin
> problemas y luego falla la verificación en cada evento: el socio ve que ha ido bien y el recibo
> sigue pendiente. memship rechaza cada una de esas notificaciones y la cuenta, así que
> **Notificaciones de pago** (consulta el [6.1](#61-cuando-falla-una-notificación-de-pago)) muestra
> los rechazos y el motivo, pero solo cuando ya se ha intentado un pago real. La prueba de principio
> a fin del 4.5 es lo que te dice que el valor es el correcto.

### 4.5 Pruebas

**El botón Probar conexión hace una llamada real a Stripe.** Recupera tu cuenta y, si va bien,
muestra el nombre visible o el ID de tu cuenta y su país. Eso demuestra que la clave secreta
funciona. **No** prueba el secreto del webhook, que no se puede verificar sin un evento real.

Para probar el webhook, lleva un recibo por un pago real con Stripe en modo de prueba y
[una tarjeta de prueba](https://docs.stripe.com/testing). Después confirma dos cosas:

- el recibo en memship ha pasado a **Cobrado**
- la entrega en **Stripe → Developers → Webhooks** muestra una respuesta `2xx`

Una entrega con `400` y un error de firma significa que el Secreto del webhook es incorrecto;
memship también la cuenta en **Notificaciones de pago**.

### 4.6 Resolución de problemas de Stripe

| Síntoma | Causa |
|---|---|
| Probar conexión informa de un error de autenticación | La clave secreta es incorrecta, está revocada o es del otro modo |
| El pago se completa en Stripe, el recibo sigue pendiente, Stripe muestra `400` | El Secreto del webhook es incorrecto |
| El pago se completa, el recibo sigue pendiente, Stripe no muestra ninguna entrega | La URL del endpoint es incorrecta o no se puede alcanzar desde internet |
| Stripe muestra `404` | A la URL le falta el prefijo `/api/v1/`, así que ha llegado a la interfaz web en lugar de a la API |
| El recibo sigue pendiente y todo lo demás parece correcto | Consulta la nota sobre importes distintos más abajo |

> **Un pago por un importe equivocado se rechaza a propósito.** memship compara el importe que
> comunica Stripe con el total del recibo y, si no coinciden, **deja el recibo pendiente** y
> registra la notificación como **Ignorada** con los dos importes, en **Notificaciones de pago**,
> para que una persona la revise. Una firma válida demuestra que el mensaje lo envió Stripe, no que
> la cantidad sea la que pediste. Esto se parece exactamente a un webhook roto, así que revisa
> Notificaciones de pago antes de concluir que la configuración está mal.

---

## 5. Redsys y Bizum

Redsys es la pasarela que usan la mayoría de los bancos españoles, la que opera el *TPV Virtual*.
La misma entrada de proveedor sirve también para **Bizum**: es un método de pago dentro de Redsys,
no una conexión aparte que configurar. No tiene credenciales propias; hay un interruptor,
**Ofrecer Bizum**, y está apagado hasta que lo enciendas.

### 5.1 Qué necesitas

Tu banco tiene que haberte dado un TPV Virtual. Del contrato o del portal del banco necesitas cuatro
valores: el **código de comercio (FUC)**, un **número de terminal**, una **clave de firma**, y saber
si trabajas contra el entorno de pruebas o el de producción.

**Si quieres Bizum, pide a tu banco que lo habilite en ese terminal.** Bizum lo activa el banco por
comercio y terminal, no nada que introduzcas aquí: las mismas credenciales sirven para tarjeta y
para Bizum en cuanto está activado. Conviene pedirlo a la vez que el TPV, porque un terminal sin
Bizum rechaza los pagos con Bizum en la pasarela. Pide también tus credenciales de **pruebas**: son
las que usas mientras el campo Entorno dice `test`.

Cuando el banco lo confirme, activa **Ofrecer Bizum** en la entrada de Redsys. memship no puede
comprobar el terminal por sí mismo (la pasarela no ofrece forma de preguntarlo), así que ese
interruptor es tu declaración de que el banco lo ha hecho, y el primer pago real con Bizum sigue
siendo la prueba.

### 5.2 Obtener las credenciales de tu banco

No salen de un panel de autoservicio como las de Stripe: las emite el banco que te vendió el TPV, y
el portal cambia de un banco a otro. Redsys publica la documentación técnica en
[pagosonline.redsys.es](https://pagosonline.redsys.es/).

- **Código de comercio (FUC)**: tu identificador de comercio, de 7 a 9 dígitos.
- **ID de terminal**: numérico, normalmente `1` salvo que el banco te haya dado varios.
- **Clave secreta** (la clave de firma): el secreto con el que se firman las peticiones y se
  verifican las notificaciones. En los portales bancarios suele llamarse *clave secreta de
  encriptación* o *clave de firma*. **Los entornos de pruebas y de producción tienen claves distintas.**
- **Código de moneda**: numérico ISO 4217. Para el euro es **978**, que es el valor por defecto.

### 5.3 Por qué no hay webhook que configurar

A diferencia de Stripe, **no registras ninguna URL de notificación en ningún sitio.** memship
incluye la dirección de retorno en cada petición de pago, así que a la pasarela se le dice cada vez
adónde responder. No hay nada que configurar en el portal del banco ni nada que mantener
sincronizado.

Por la misma razón no hay un secreto de webhook aparte. La **Clave secreta** hace los dos
trabajos: memship firma con ella las peticiones que salen y verifica con ella las notificaciones que
llegan. Un solo valor, introducido una vez.

Si alguna vez necesitas saber la dirección que envía memship, es
`https://<your-memship-address>/api/v1/webhooks/redsys`, pero no deberías tener que configurarla en
ningún sitio.

### 5.4 Rellenar la pantalla

| Campo | Valor |
|---|---|
| Código de comercio (FUC) | 7–9 dígitos, de tu banco |
| ID de terminal | numérico, de tu banco |
| Clave secreta | la clave de firma **del entorno que hayas elegido** |
| Entorno | `test` mientras pruebas, `production` en real |
| Código de moneda | `978` para el euro |

> **Confirma que el campo Entorno dice `production` antes de pasar a real.** memship se niega a
> activar un proveedor cuyo entorno no sea ni `test` ni `production`, así que una errata se rechaza
> en lugar de aceptarse en silencio. Lo que no puede detectar es un valor válido que no querías:
> `test` se activa sin protestar y manda a los socios reales al TPV de pruebas, donde sus pagos no
> existen.

### 5.5 Pruebas

**El botón Probar conexión no contacta con Redsys.** Redsys no tiene ningún endpoint al que hacer
ping, así que el botón valida tu configuración en local. Es deliberadamente más estricto que
guardar: rechaza un código de comercio que no tenga de 7 a 9 dígitos, que es la longitud fuera de
la cual un TPV real lo rechaza directamente.

Probar de verdad es hacer un pago contra el entorno de pruebas, con la clave de firma de pruebas y
los números de tarjeta que te dé el banco. Confirma después que el recibo pasa a **Cobrado**: que
el navegador vuelva a una página de éxito no es una confirmación, como se explica en la sección 3.

### 5.6 Resolución de problemas de Redsys

| Síntoma | Causa |
|---|---|
| Probar conexión informa de que el código de comercio debe tener 7–9 dígitos | El FUC es incorrecto o tiene espacios o letras |
| La pasarela rechaza el pago de inmediato | La clave de firma no corresponde al entorno |
| Los pagos salen bien pero no aparecen en ningún sitio | El entorno es `test` (o una errata que acaba en él) cuando creías que era producción |
| El recibo sigue pendiente tras un pago correcto | La notificación no ha podido llegar a tu instalación: comprueba que se puede alcanzar desde internet |
| `SIS0051, Pedido repetido` | Un número de pedido duplicado. memship genera un prefijo aleatorio nuevo en cada intento, así que debería ser raro; al reintentar se emite uno nuevo |
| `SIS0475` en un pago con Bizum, con tarjeta va bien | Bizum no está habilitado en ese comercio y terminal. Pide a tu banco que lo active; nada en la configuración de memship cambia esto |
| `SIS0027`, y la pasarela muestra el importe en otra moneda | El terminal no está preparado para la moneda que envías. Revisa el campo Código de moneda y pregunta al banco qué terminal usar para euros |

---

## 6. Activación, modo de pruebas y lo que ven los socios

Un proveedor tiene tres estados:

| Estado | Significado |
|---|---|
| **Desactivado** | Configurado pero no ofrecido. Los socios no ven ningún botón para él |
| **Pruebas** | Ofrecido, para probar el flujo de principio a fin |
| **Activo** | Ofrecido a los socios como método de pago real |

**Activar Redsys ofrece tarjeta. Bizum es un interruptor aparte.** Los socios ven *Tarjeta* en sus
recibos y en su página de membresía en cuanto la entrada de Redsys está activa; *Bizum* solo aparece
cuando **Ofrecer Bizum** también está encendido. Déjalo apagado hasta que el banco haya confirmado
Bizum en el terminal: un botón de Bizum en un terminal que no lo tiene falla en la pasarela para
cada socio que lo pulse, y nada en su pantalla explica por qué.

Ofrezcas lo que ofrezcas, usa primero el estado **Pruebas** y completa un pago real de cada tipo que
pienses aceptar antes de pasar a activo.

**memship se niega a activar un proveedor que no podría cobrar un pago.** La activación es el último
momento en que una configuración incompleta sigue siendo un problema de ajustes: pasado ese punto,
el campo que falta reaparece como un pago fallido en la pantalla de un socio. Si se rechaza la
activación, el mensaje indica los campos que fallan.

Esta comprobación es local. Confirma que tu configuración es coherente en sí misma; no puede saber
que ayer se revocó una clave en el proveedor. Es un motivo más para completar un pago real antes de
confiar en él.

### 6.1 Cuando falla una notificación de pago

Bajo los proveedores, **Notificaciones de pago** lista lo que las pasarelas enviaron y memship no
aplicó:

- **Fallida**: memship no pudo aplicarla. La pasarela reintenta, así que un fallo que se resuelve
  solo es normal; uno que persiste, no.
- **Ignorada**: memship la recibió y a propósito no hizo nada: un tipo de evento que no trata, un
  importe equivocado o un pago de un recibo **ya pagado**. Esto último es como se manifiesta un
  doble cobro: el socio pagó dos veces y hay que devolver el segundo pago desde la pasarela.
- **Rechazadas por la firma**: se muestran como un recuento por proveedor encima de la lista, con el
  último motivo. Nunca se guardan, porque no se puede confiar en nada de un mensaje sin verificar.
  Un recuento que no para de crecer significa que el secreto configurado es incorrecto y **no** se
  está confirmando ningún pago.

Para que te avisen en lugar de tener que mirar, indica la dirección de notificaciones de
facturación. memship envía entonces un correo al día, solo cuando algo ha ido mal en las 24 horas
anteriores. El correo es **Incidencias en notificaciones de pago**, en Configuración → Socios →
Comunicaciones: activado por defecto en una instalación nueva, y se puede desactivar ahí. Una
instalación anterior a él empieza con él desactivado; actívalo ahí.

Si la pasarela cobró el dinero y el recibo sigue pendiente, márcalo como cobrado a mano eligiendo
Redsys, Bizum o Stripe como método: memship pide la referencia de la pasarela (el código de
autorización o el identificador del pago de la liquidación) para que el pago se pueda seguir
cuadrando con el banco.

---

## 7. Referencia de campos

**Stripe**

| Campo | Obligatorio | Secreto | Formato comprobado | De dónde sale |
|---|---|---|---|---|
| Clave secreta | sí | sí | debe empezar por `sk_` | Stripe → Developers → API keys |
| Clave publicable | sí | no | debe empezar por `pk_` | Stripe → Developers → API keys |
| Secreto del webhook | sí | sí | debe empezar por `whsec_` | Stripe → Developers → Webhooks, después de crear el endpoint |

**Redsys**

| Campo | Obligatorio | Secreto | Formato comprobado | De dónde sale |
|---|---|---|---|---|
| Código de comercio (FUC) | sí | no | solo dígitos; 7–9 en Probar conexión | tu banco |
| ID de terminal | sí | no | solo dígitos | tu banco |
| Clave secreta | sí | sí | no | tu banco, por entorno |
| Entorno | sí | no | `test` o `production` | lo que elijas |
| Código de moneda | sí | no | exactamente 3 dígitos | ISO 4217, `978` para el euro |
| Ofrecer Bizum | no | no | n/a | tu banco, cuando confirme Bizum en el terminal. Apagado por defecto |

---

## Otros métodos de pago, y qué significa aquí el cobro automático

Esta guía configura lo que memship cobra en línea: tarjeta con Stripe, y tarjeta o Bizum con Redsys. La domiciliación es un mecanismo aparte, basado en un archivo para el banco, véase [Domiciliación SEPA](sepa.md).

**La facturación recurrente genera los recibos, no cobra el dinero.** Cobrar una cuota sin que el socio haga nada funciona solo por domiciliación SEPA, donde el socio firma un mandato una vez. Con tarjeta el socio paga cada periodo desde un enlace de pago. memship no guarda deliberadamente ninguna tarjeta para cobrarla después, así que una cuota con tarjeta siempre es algo que el socio completa.

**Cualquier otro proveedor, o cualquier otra forma de cobrar, es una extensión a medida.** Si tu organización necesita un método de pago que memship no incluye, necesita domiciliación cobrada a través de una pasarela en lugar de un archivo bancario, o necesita estos proveedores conectados de otra manera, abre una incidencia con la etiqueta `question` describiendo lo que necesitas: <https://github.com/marcandreuf/memship/issues>. La capa de proveedores está pensada para ampliarse, y quienes contribuyen pueden decirte lo que supondría un proveedor concreto antes de que te comprometas.

---

## Relacionado

- [Pagos](payments.md): el uso diario de los pagos
- [Donaciones](donations.md): un enlace de donación en la web propia de la organización. Ese enlace
  se crea en el panel del proveedor y no tiene nada que ver con el proveedor que se configura aquí
- [SEPA](sepa.md): la domiciliación, un mecanismo aparte
- [Integraciones](integrations.md): SSO y correo, y la descripción completa del almacenamiento de
  secretos
- [Referencia de configuración](../self-hosting/configuration.md): `BACKEND_PUBLIC_URL` y
  `FRONTEND_URL`
