<!-- source: en/self-hosting/email.md -->
<!-- source-hash: a7f08bd46411 -->

# Envío de correo

Memship envía correo transaccional para confirmar direcciones, restablecer contraseñas, confirmar
inscripciones a actividades, avisar de ascensos desde la lista de espera, enviar recibos de pago y
avisar de recibos vencidos. **El correo está desactivado hasta que configuras un transporte.**

> **En inglés:** [Email delivery](../../en/self-hosting/email.md).
> **En català:** [Enviament de correu](../../ca/self-hosting/email.md).

Hay dos formas de configurarlo, y **no son equivalentes**: la pantalla de ajustes manda sobre el
`.env`. Lee [Cuál está en vigor](#cuál-está-en-vigor) antes de tocar nada, sobre todo en una
instalación que ya está en marcha.

| Dónde | Proveedores | Lo mejor para |
|-------|-----------|----------|
| **Configuración → Integraciones → Correo** | Resend, cualquier servidor SMTP (Gmail es una configuración predefinida) | Casi todo el mundo. Se aplica en la siguiente petición, sin reiniciar. |
| **`.env`** | Resend, cualquier servidor SMTP | Dejar las credenciales puestas al desplegar, y las instalaciones anteriores a la pantalla de ajustes. |

SMTP quiere decir un servidor que acepte **STARTTLS**, normalmente en el puerto 587, o uno que
cifre desde el primer byte, normalmente en el puerto 465, o uno sin cifrado ninguno. Elige cuál con
el ajuste **Cifrado** de la pantalla, o con `SMTP_SECURITY` en el `.env`.

## Opción A: la pantalla de ajustes

Entra como superadministrador y ve a **Configuración → Integraciones → Correo**.

El recorrido completo (cómo obtener las credenciales, los registros DNS que necesita Resend, los
datos de tu servidor SMTP o una contraseña de aplicación de Gmail, el botón **Enviar prueba** y una
tabla de resolución de problemas) está en la
[guía de configuración de integraciones, sección 4](../admin-guide/integrations.md#4-correo)
_(en inglés)_. Dos puntos de esa guía merecen repetirse aquí, porque son los que fallan sin avisar:

- **Guardar las credenciales no las activa.** La insignia de la tarjeta pasa a *Listo*, no a
  *Activo*. Después tienes que elegir el selector **Proveedor activo** y volver a guardar.
  Configurar → probar → activar, en ese orden. El orden es obligatorio: no se puede activar un
  proveedor hasta que haya salido bien un envío con sus credenciales guardadas actuales.
- **Sin proveedor activo, el correo se omite sin avisar**: se registra en el log, no se pone en
  cola y no da error. Nada en la interfaz informa de un envío que nunca se hizo.

Cada tarjeta de proveedor muestra además si se sabe que sus credenciales funcionan: *Sin
verificar*, *Funciona*, o *Falla* con un motivo. Se actualiza con cada correo enviado por ese
proveedor, la prueba incluida, y vale también para las credenciales que vienen del `.env`.

Los correos de aprobación y rechazo se envían en el momento en que el administrador decide, para
poder decirle si han salido. Si no se pudo contactar con el proveedor o se alcanzó su límite de
envío, se reintentan automáticamente al cabo de 1, 5 y 25 minutos, y el mensaje de aprobación lo
dice. Cualquier otro fallo, como unas credenciales rechazadas, se notifica en el acto y no se
reintenta, porque volvería a fallar igual. Los reintentos se ejecutan en el servicio `worker`, que
tiene que estar levantado.

## Opción B: `.env`

Define las variables y recrea el backend para que las lea:

```bash
docker compose up -d --force-recreate api
```

**Resend:**

```bash
RESEND_API_KEY=re_your_key_here
RESEND_FROM_EMAIL=noreply@yourdomain.org
```

**SMTP** (cualquier servidor, Gmail incluido; para Gmail usa `smtp.gmail.com` y una contraseña de
aplicación):

```bash
SMTP_HOST=smtp.yourprovider.com
SMTP_PORT=587
SMTP_USER=your-username
SMTP_PASSWORD=your-password
SMTP_FROM=noreply@yourdomain.org
SMTP_SECURITY=starttls   # starttls | ssl | off
```

`SMTP_SECURITY` sustituye a `SMTP_TLS`. La variable antigua sigue funcionando, así que un archivo
que ya existe no necesita cambios: `SMTP_TLS=true` significa `starttls` y `SMTP_TLS=false` significa
`off`. Define `SMTP_SECURITY` cuando necesites `ssl`, que `SMTP_TLS` no podía expresar. Si están las
dos, manda `SMTP_SECURITY`.

La correspondencia completa entre campo de pantalla y variable de entorno está en la
[guía de configuración de integraciones, sección 6](../admin-guide/integrations.md#6-alternativa-con-el-archivo-de-configuración-env)
_(en inglés)_.

## Cuál está en vigor

Tres casos, y la diferencia importa:

| Situación | Qué envía |
|-----------|------------|
| **La pantalla de Correo no se ha guardado nunca** | Los valores del `.env`, tal como se describe arriba: Resend si está definida `RESEND_API_KEY`, si no SMTP si está definida `SMTP_HOST`, y si no, nada. |
| **La pantalla se ha guardado y se ha elegido un proveedor activo** | Ese proveedor. Campo a campo, un valor guardado en la pantalla manda; un campo que se deja vacío ahí recurre a la variable de entorno correspondiente. |
| **La pantalla se ha guardado pero no se ha elegido proveedor activo** | **Nada.** El correo se omite sin avisar, diga lo que diga el `.env`. |

El [entorno de prueba rápida](../getting-started/quickstart.md#5-prueba-el-alta-de-un-socio)
_(en inglés)_ depende de la primera fila: su fichero compose apunta `SMTP_HOST` a un buzón de
pruebas local, así que guardar la pantalla sustituye ese buzón de pruebas por el proveedor que se
elija ahí, o por nada si no se elige ninguno.

La consecuencia a vigilar: en cuanto alguien ha guardado la pantalla de Correo, **editar el `.env`
puede no tener ningún efecto visible**: el valor guardado manda y no salta ningún error. Si
configuraste Resend en la pantalla y luego cambias `RESEND_API_KEY` en el `.env`, se sigue enviando
con la clave antigua. Vacía el campo en la pantalla para recurrir al valor del entorno.

La pantalla marca los campos que está leyendo del entorno con la insignia **"del entorno"**, que es
la forma más rápida de ver qué origen está vigente. El puerto y el TLS siempre tienen valor, 587 y
activado, así que solo llevan la insignia cuando `SMTP_PORT` o `SMTP_SECURITY` están realmente
definidas.

**Si actualizas desde una versión que ofrecía "Gmail" como proveedor:** siempre fue el transporte
SMTP, y ahora se llama así. El correo sigue yendo adonde iba:

- Una instalación que configuró Gmail en la pantalla pasa a ser el proveedor SMTP con el servidor
  de Google (`smtp.gmail.com`, puerto 587, STARTTLS) guardado explícitamente. No empieza a seguir
  `SMTP_HOST`.
- Una instalación configurada solo mediante el `.env` sigue usando su `SMTP_HOST`, y ahora aparece
  como SMTP en vez de Gmail.

En los dos casos la tarjeta muestra *Sin verificar* hasta que pase el siguiente correo, porque su
registro de estado pertenecía al proveedor antiguo. Mientras tanto sigue activa.

## Comprobar

Provoca un envío real para confirmar la entrega; por ejemplo, pide un **restablecimiento de
contraseña** desde la página de acceso, o aprueba un alta pendiente y comprueba que llega el
correo de aprobación. Los correos se localizan (ES/CA/EN) según el idioma del destinatario.

Si configuraste desde la pantalla de ajustes, mejor usa su botón **Enviar prueba**: envía a través
de un proveedor concreto aunque no sea el activo, así que puedes verificar las credenciales antes
de pasarles el tráfico real.

Para la prueba de restablecimiento usa una cuenta de socio o de administrador del club. Los
superadministradores quedan fuera de ese flujo a propósito (su contraseña se restablece desde el
servidor con `python -m app.cli.seed`, ver la
[primera puesta en marcha](../getting-started/first-setup.md#recuperar-la-contraseña-del-superadministrador)), así que probar con uno parece un
correo que nunca llega.

## Lo que un socio puede desactivar

Cada socio tiene en su perfil el interruptor **Recibir correos del club**. Cubre las plantillas
`optional`, las confirmaciones de reservas y actividades y los comunicados del club, y nada más:

| Nivel | Ejemplos | Baja voluntaria del socio |
|---|---|---|
| Obligatorio | confirmación de la dirección, restablecimiento de contraseña | no se aplica nunca |
| Operativo | recibos, recordatorios de pago, una reserva cancelada | no se aplica nunca |
| Opcional | confirmaciones de reservas e inscripciones, anuncios | se aplica |

Un socio que se da de baja sigue recibiendo sus facturas y los avisos que preceden a una deuda,
que un club puede estar obligado a enviar. El personal puede cambiar el interruptor en nombre de un
socio desde su ficha, para quien lo pide en el mostrador o no tiene acceso al portal.

Qué plantillas van en qué nivel se ve en **Configuración → Socios → Comunicaciones**, y primero se comprueba el
interruptor de la propia organización: una plantilla desactivada ahí no se envía a nadie, elija lo
que elija el socio.

Salvo los correos obligatorios, las plantillas empiezan **desactivadas**, con una excepción: una
instalación nueva empieza con el correo de **aprobación del alta** activado, porque un solicitante
aprobado no tiene otra forma de enterarse de que lo han admitido. Se puede desactivar como
cualquier otro. Una instalación creada antes de que existiera este valor por defecto conserva lo
que tuviera; si los correos de aprobación no llegan nunca, revisa primero ese interruptor. Al
aprobar un alta, además, se le dice al administrador si el correo se envió, estaba desactivado o
falló, y por qué.

## Los socios no pueden entrar hasta que funcione el correo

Para entrar hace falta una dirección confirmada, y la única forma de confirmarla por uno mismo es
el enlace que se envía al registrarse. Así que, mientras no haya un proveedor configurado:

- **El autorregistro se rechaza**, con un mensaje que pide al visitante que contacte con el club,
  en vez de crear una cuenta que su dueño nunca podría usar.
- **Un socio que se registró antes y nunca confirmó** aparece como *activo* y no puede entrar.
  Abre su ficha: indica que la dirección está sin confirmar y ofrece **Confirmar dirección**. Eso
  requiere `users.write`, y queda registrado en el log de auditoría como confirmada por un
  administrador y no por el socio; confirma solo una dirección que hayas comprobado por otra vía
  que es suya.
- Desde el servidor, lo mismo sin la interfaz:
  `python -m app.cli.verify_email --email someone@example.org`, o `--list` para ver quién está
  esperando.

Un proveedor *configurado pero roto*, con una clave de API incorrecta por ejemplo, no lo detecta la
protección del registro: parece utilizable y falla en el transporte. Esos socios se quedan
atascados igual, y **Confirmar dirección** es la salida.

## Resolución de problemas

- **No sale ningún correo**: comprueba en este orden: (1) **Configuración → Integraciones → Correo**,
  ¿está *Proveedor activo* en algo distinto de *Ninguno*? Un proveedor guardado pero no activado no
  envía nada. (2) Si la pantalla no se ha usado nunca, confirma que `RESEND_API_KEY` o `SMTP_HOST`
  está definida en el `.env`; si no lo está ninguna, el correo está desactivado a propósito.
- **Cambiar el `.env` no hizo nada**: la pantalla de Correo tiene un valor guardado para ese campo,
  y manda. Ver [Cuál está en vigor](#cuál-está-en-vigor).
- **Resend rechaza el envío (403, "domain is not verified")**: la dirección del remitente no está
  en un dominio verificado en Resend, o sus registros DNS no se han propagado. Resend rechaza
  cualquier remitente fuera de un dominio verificado. La única excepción es
  `onboarding@resend.dev`, que no necesita dominio pero entrega **solo a la dirección dueña de la
  cuenta de Resend**: sirve para una prueba, no para tráfico real.
- **Los correos llegan con retraso**: el envío es asíncrono, mediante Celery. Revisa los logs del
  worker: `docker compose logs -f worker`.
- **Los enlaces apuntan al servidor equivocado**: define `FRONTEND_URL` con la URL pública de tu
  sitio (ver la [referencia de configuración](configuration.md)).
