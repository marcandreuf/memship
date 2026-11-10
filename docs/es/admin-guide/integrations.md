<!-- source: en/admin-guide/integrations.md -->
<!-- source-hash: bf21fddc90e9 -->

# Integraciones: guía de configuración

**Para quién es:** la persona que gestiona una instalación de memship para su club o asociación
(el **superadministrador**).
**Qué cubre:** todo lo que hay en **Configuración → Integraciones**, el inicio de sesión con
Google / Apple (**Inicio de sesión (SSO)**) y el envío de correo (**Correo**), más las opciones de
registro que van con ellos.

> **En inglés:** [Integrations: Setup Guide](../../en/admin-guide/integrations.md).
> **En català:** [Integracions: guia de configuració](../../ca/admin-guide/integrations.md).

No necesitas editar ningún archivo ni reiniciar nada. Todas las credenciales de esta guía se
introducen en la interfaz web y tienen efecto en la siguiente petición.

---

## Índice

1. [Antes de empezar](#1-antes-de-empezar)
2. [Cómo se protegen los secretos](#2-cómo-se-protegen-los-secretos)
3. [Inicio de sesión único (SSO)](#3-inicio-de-sesión-único-sso)
   - [Cómo funciona para un socio](#31-cómo-funciona-para-un-socio)
   - [Paso común: tu URL pública y las URI de redirección](#32-paso-común-tu-url-pública-y-las-uri-de-redirección)
   - [Google: obtener las credenciales](#33-google-obtener-las-credenciales)
   - [Apple: obtener las credenciales](#34-apple-obtener-las-credenciales)
   - [Rellenar la pantalla](#35-rellenar-la-pantalla)
   - [Solución de problemas del SSO](#36-solución-de-problemas-del-sso)
4. [Correo](#4-correo)
   - [Cómo funciona](#41-cómo-funciona)
   - [Resend: obtener las credenciales](#42-resend-obtener-las-credenciales)
   - [SMTP: los datos de tu servidor, o Gmail](#43-smtp-los-datos-de-tu-servidor-o-gmail)
   - [Rellenar la pantalla, probar y activar](#44-rellenar-la-pantalla-probar-y-activar)
   - [Solución de problemas del correo](#45-solución-de-problemas-del-correo)
5. [Opciones de registro que acompañan a estas integraciones](#5-opciones-de-registro-que-acompañan-a-estas-integraciones)
6. [Alternativa con el archivo de configuración (`.env`)](#6-alternativa-con-el-archivo-de-configuración-env)
7. [Referencia de campos](#7-referencia-de-campos)

---

## 1. Antes de empezar

**Acceso.** Integraciones solo es visible para los usuarios con el rol de **superadministrador**.
Un administrador normal no ve la pestaña. Ve a **Configuración → Integraciones**; dentro hay dos
subpestañas: **Inicio de sesión (SSO)** y **Correo**.

**Una dirección pública.** Las dos integraciones dan por hecho que tu instalación es accesible en
una dirección real (por ejemplo `https://socios.myclub.org`), configurada una sola vez al instalar
en `BACKEND_PUBLIC_URL` y `FRONTEND_URL`. La pantalla de Integraciones muestra la URL del backend
en solo lectura, con un botón de copiar.

**HTTPS.** Google funciona sobre `http://localhost` para hacer pruebas, pero **Apple no**: rechaza
`localhost` y el HTTP plano, y exige un dominio real con un certificado válido. Cuenta con
configurar Apple solo en tu instalación en producción.

**Cuentas que quizá tengas que crear:**

| Integración | Necesitas | Coste |
| ----------- | -------- | ---- |
| Inicio de sesión con Google | Una cuenta de Google (Google Cloud Console) | Gratuito |
| Inicio de sesión con Apple | Una suscripción al **Apple Developer Program** | Cuota anual de pago |
| Correo con Resend | Una cuenta de Resend + un dominio que controles | Hay un plan gratuito |
| Correo por SMTP | Los datos SMTP de tu alojamiento de correo actual, o una cuenta de Google con la verificación en 2 pasos activada para Gmail | Normalmente ya pagado / Gratuito |

No tienes que configurarlo todo. Los proveedores de inicio de sesión son opcionales (los socios
siempre pueden usar correo + contraseña). El correo es, en la práctica, obligatorio: sin él no se
entregan los correos de verificación, de aprobación ni de recibos.

---

## 2. Cómo se protegen los secretos

Algunos de los valores que escribes aquí son secretos de verdad: un secreto de cliente de Google,
una clave privada de Apple, una clave de API de Resend, una contraseña SMTP (para Gmail, una
contraseña de aplicación).

- Se **cifran antes de guardarse** en la base de datos.
- **Nunca se devuelven al navegador**. Una vez guardado un secreto, el campo deja de ser una
  casilla de entrada: se muestra como texto (`••••` más los cuatro últimos caracteres, y la
  palabra *guardado*) junto a un botón **Reemplazar**. Es lo esperado; no hay forma de volver a
  leer un secreto guardado desde la interfaz, ni ninguna casilla que pueda rellenar un gestor de
  contraseñas, y esa es la idea. Antes, una casilla rellena ocultaba la única señal de que ya
  había un valor guardado, y al guardar se enviaba lo que el navegador hubiera inyectado encima
  de una credencial que funcionaba.
- La clave de cifrado la **genera automáticamente** el servidor la primera vez que se usa y la
  escribe en un archivo de clave en el volumen de almacenamiento (nunca en la base de datos). No
  tienes que crearla tú.

En la parte superior de cada pantalla de Integraciones verás uno de estos dos avisos:

- 🟢 **"Cifrado activo"**, estado normal. No hay nada que hacer.
- 🟠 **"El servidor no tiene una clave de cifrado válida: o no pudo crear su archivo de clave
  (comprueba que el volumen de almacenamiento tiene permisos de escritura) o MEMSHIP_SECRET_KEY no
  es una clave válida."**, el servidor no ha podido ni leer ni crear su archivo de clave, o
  `MEMSHIP_SECRET_KEY` contiene algo que no es una clave válida. Hasta que se solucione, los campos
  secretos no se pueden guardar (los no secretos, sí). Corrige los permisos del volumen de
  almacenamiento montado en el contenedor del backend, o corrige o quita `MEMSHIP_SECRET_KEY`, y
  después recarga la página.

> **Haz la copia de seguridad del archivo de clave junto con la base de datos.** Si restauras un
> volcado de la base de datos en una máquina que tiene un archivo de clave *distinto*, los
> secretos guardados ya no se pueden descifrar. No falla nada, memship recurre a lo que haya en
> `.env` y los campos afectados simplemente se comportan como si estuvieran vacíos, pero tendrás
> que volver a introducir todos los secretos. El archivo de clave está en el volumen de
> almacenamiento; su ruta es `SECRETS_KEY_FILE`, por defecto `<storage>/secret.key`.

**Reglas de edición para todos los campos secretos** (iguales en las dos subpestañas):

- **No lo toques** → se conserva el valor guardado sin cambios. En un campo que todavía no tiene
  nada guardado, dejarlo en blanco hace lo mismo.
- Haz clic en **Reemplazar** → aparece una casilla, y solo el valor que escribas en ella se envía
  como secreto nuevo. **Cancelar** deja el campo como estaba sin cambiar nada.
- Haz clic en **Borrar** → el valor guardado se elimina al guardar (haz clic en **Deshacer** para
  cancelarlo antes de guardar).

---

## 3. Inicio de sesión único (SSO)

**Configuración → Integraciones → Inicio de sesión (SSO)**

### 3.1 Cómo funciona para un socio

Cuando activas un proveedor, aparece un botón **"Continuar con Google"** / **"Continuar con
Apple"** tanto en la página de inicio de sesión como en la de registro. Los botones solo aparecen
para los proveedores activados y configurados del todo: nadie ve un botón que fallaría.

Qué pasa cuando una persona lo usa:

1. Se la envía a Google / Apple, inicia sesión allí y vuelve a memship.
2. **Si ya tiene una cuenta de memship con la misma dirección de correo, verificada por el
   proveedor**, el proveedor se vincula a esa cuenta existente. A partir de ahí puede iniciar
   sesión de las dos maneras, con contraseña o con el proveedor.
3. **Si es nueva**, se le crea una cuenta y una ficha de socio con el estado **pendiente**, y se
   aplican las reglas de alta habituales: llega a la pantalla *Pendiente de aprobación* hasta que
   un administrador la aprueba desde **Socios → Altas pendientes**. El número de socio se asigna
   al aprobarla.
4. Su correo cuenta como ya verificado (el proveedor ha respondido por él), así que no recibe
   ningún correo de verificación.

Cosas que conviene saber:

- Las cuentas creadas a través de un proveedor **no tienen contraseña**. Si más adelante la
  persona quiere iniciar sesión con contraseña, usa el flujo de "¿Olvidaste tu contraseña?" para
  definir una.
- Una misma persona puede tener contraseña + Google + Apple apuntando a la misma cuenta.
- El registro público tiene que estar activado para que las personas *nuevas* puedan darse de
  alta así, consulta la [sección 5](#5-opciones-de-registro-que-acompañan-a-estas-integraciones).

### 3.2 Paso común: tu URL pública y las URI de redirección

En la parte superior de la pantalla de SSO hay una tarjeta que muestra tu **URL del backend**, y
cada tarjeta de proveedor muestra su **URI de redirección**. Las dos tienen un botón de copiar.
Son los valores que piden las consolas de los proveedores. Tienen este aspecto:

```
Backend URL   https://socios.myclub.org
Google        https://socios.myclub.org/api/v1/auth/oauth/google/callback
Apple         https://socios.myclub.org/api/v1/auth/oauth/apple/callback
```

Cópialas de la pantalla en lugar de escribirlas: tienen que coincidir **carácter por carácter** en
los dos lados, incluido el `https://` y la ausencia de barra final. Una discrepancia es, con
diferencia, la causa más habitual de un inicio de sesión fallido.

Si la URL del backend que se muestra es incorrecta (por ejemplo `http://localhost:8003` en un
servidor en producción), hay que corregirla en la variable `BACKEND_PUBLIC_URL` de la instalación;
a propósito no se puede editar desde la pantalla, porque describe cómo está publicado tu servidor,
no cómo está configurado un proveedor.

### 3.3 Google: obtener las credenciales

Necesitas dos valores: un **ID de cliente** y un **secreto de cliente**.

1. Ve a **[Google Cloud Console](https://console.cloud.google.com/)** e inicia sesión.
2. Crea un proyecto (barra superior → selector de proyectos → **New project**), ponle un nombre
   como `Memship – My Club` y selecciónalo.
3. En el menú de la izquierda abre **APIs & Services → OAuth consent screen**.
   - User type: **External** (salvo que todos los socios tengan una cuenta en tu organización de
     Google Workspace; en ese caso, Internal ya sirve).
   - App name: el nombre de tu club, tal como lo verán los socios en la pantalla de consentimiento
     de Google.
   - User support email y developer contact email: tu dirección.
   - Scopes: los predeterminados `email`, `profile`, `openid` son todo lo que hace falta. No añadas
     ninguno más: los scopes adicionales activan la revisión de verificación de Google.
   - Añade tu logotipo y un enlace a tu web si quieres que la pantalla de consentimiento se parezca
     a vosotros. Opcional.
   - **Publica la aplicación** (botón **Publish app** → *In production*). Mientras está en
     *Testing*, solo pueden iniciar sesión las direcciones de correo que hayas añadido como
     usuarios de prueba.
4. Abre **APIs & Services → Credentials → Create credentials → OAuth client ID**.
   - Application type: **Web application**.
   - Name: lo que quieras, p. ej. `memship web`.
   - **Authorised redirect URIs → Add URI**: pega la URI de redirección de Google copiada de la
     pantalla de memship.
   - (Authorised JavaScript origins se puede dejar vacío: memship hace el intercambio en el
     servidor.)
   - **Create**.
5. Google muestra el **Client ID** (termina en `.apps.googleusercontent.com`) y el **Client
   secret** (empieza por `GOCSPX-`). Cópialos los dos ahora; el secreto se puede volver a copiar
   más tarde desde la misma página.

### 3.4 Apple: obtener las credenciales

Apple necesita **cuatro** valores: un ID de cliente (Services ID), un ID de equipo, un ID de clave
y un archivo de clave privada. Da más trabajo que Google, cuenta con 20 minutos.

Requisitos: una suscripción de pago al **Apple Developer Program** y un dominio HTTPS en
producción (Apple rechaza `localhost` y los certificados autofirmados).

1. Ve a **[developer.apple.com/account](https://developer.apple.com/account)** → **Certificates,
   Identifiers & Profiles**.
2. **Crea un App ID**, *Identifiers* → **+** → **App IDs** → **App**.
   - Description: el nombre de tu club. Bundle ID: p. ej. `org.myclub.memship`.
   - En la lista de capacidades, marca **Sign in with Apple**. Register.
3. **Crea un Services ID**, *Identifiers* → **+** → **Services IDs**.
   - Description: p. ej. `Memship Web`. Identifier: p. ej. `org.myclub.memship.web`.
   - ⚠️ **Este identificador es el valor que memship llama ID de cliente.** *No* es el App ID del
     paso 2, y confundirlos es el error clásico al configurar Apple.
   - Regístralo, después **vuelve a abrir el Services ID** y marca **Sign in with Apple →
     Configure**:
     - Primary App ID: el App ID del paso 2.
     - **Domains and Subdomains**: tu dominio sin el esquema, `socios.myclub.org`.
     - **Return URLs**: pega la URI de redirección de Apple copiada de la pantalla de memship
       (con `https://`).
     - Guarda, y después **Continue / Save** en el propio Services ID.
4. **Crea una clave**, *Keys* → **+**.
   - Key name: p. ej. `Memship Sign in with Apple`.
   - Marca **Sign in with Apple** → **Configure** → selecciona el Primary App ID → Save →
     Continue → Register.
   - **Descarga el archivo `.p8`.** ⚠️ Apple solo te deja descargarlo **una vez**. Si lo pierdes,
     revoca la clave y crea una nueva.
   - Apunta el **Key ID** que se muestra en esa página (10 caracteres, p. ej. `A1B2C3D4E5`).
5. **Encuentra tu Team ID**, arriba a la derecha de la página de la cuenta de Apple Developer,
   bajo tu nombre / en **Membership details**. 10 caracteres, p. ej. `9XYZ8ABCDE`.

Ahora tienes:

| Campo de memship | Valor de Apple | Ejemplo |
| ------------- | ----------- | ------- |
| ID de cliente | el identificador del **Services ID** | `org.myclub.memship.web` |
| ID de equipo | Membership details → Team ID | `9XYZ8ABCDE` |
| ID de clave | la clave que has creado | `A1B2C3D4E5` |
| Clave privada (.p8) | **todo el contenido** del archivo descargado | `-----BEGIN PRIVATE KEY-----…` |

Para la clave privada, abre el archivo `.p8` con un editor de texto plano y cópialo todo, incluidas
las líneas `-----BEGIN PRIVATE KEY-----` y `-----END PRIVATE KEY-----`.

### 3.5 Rellenar la pantalla

En cada tarjeta de proveedor:

1. Pega los campos no secretos (ID de cliente y, para Apple, también ID de equipo e ID de clave).
2. Pega el campo secreto (secreto de cliente de Google / clave privada de Apple). Es una casilla de
   tipo contraseña; se mantiene enmascarada.
3. Pulsa **Guardar**.
4. **Activa el interruptor** del proveedor. El interruptor está desactivado hasta que todos los
   campos de ese proveedor están rellenos: guardar credenciales nunca activa un proveedor por sí
   solo, así que tú decides cuándo entra en funcionamiento.
5. Vuelve a pulsar **Guardar**. La insignia de la tarjeta cambia a **Activo**.

Abre la página de inicio de sesión en una ventana privada y comprueba que el botón está ahí y que
completa un inicio de sesión.

Otras marcas que puedes ver:

- **"del entorno"** junto a una etiqueta, ese valor viene ahora mismo del archivo `.env` de la
  instalación, no de lo que has escrito aquí. Escribir un valor en la pantalla lo sustituye para
  ese campo. Consulta la [sección 6](#6-alternativa-con-el-archivo-de-configuración-env).
- **"guardado"** junto a una etiqueta de secreto, hay un secreto guardado para ese campo.

### 3.6 Solución de problemas del SSO

| Síntoma | Causa y solución |
| ------- | ------------- |
| Google: `Error 400: redirect_uri_mismatch` | La URI de redirección de la consola de Google es distinta de la de la pantalla de memship. Vuelve a copiarla con el botón de copiar; comprueba `https` frente a `http`, `www` y la barra final. |
| Google: "Access blocked: this app has not completed the verification process" | La pantalla de consentimiento sigue en *Testing*. Publícala, o añade a la persona como usuario de prueba. |
| Google: `invalid_client` | El ID de cliente y el secreto de cliente no pertenecen al mismo cliente OAuth, o el secreto se ha recortado al pegarlo. Vuelve a copiar los dos. |
| Apple: `invalid_client` | Casi siempre es una de estas: se ha usado el App ID en lugar del **Services ID**; un Team ID o Key ID incorrecto; un `.p8` pegado solo en parte. Revisa los cuatro valores. |
| Apple: "Invalid redirect_uri" / no se puede guardar el Services ID | La Return URL tiene que ser `https`, exactamente en el dominio indicado en *Domains and Subdomains*, y no puede ser una dirección IP ni `localhost`. |
| El inicio de sesión con Apple vuelve a la página de inicio de sesión con un error | La llamada de vuelta de Apple es un POST entre sitios y requiere que el sitio se sirva por HTTPS. Apple no funciona contra una instalación de desarrollo. |
| El nombre de un socio queda vacío tras iniciar sesión con Apple | Apple envía el nombre **solo la primera vez** que la persona autoriza tu aplicación. Si estabas haciendo pruebas, elimina tu aplicación de *Apple ID → Sign in with Apple* en la cuenta y vuelve a probar; es el comportamiento normal y no hace ningún daño. |
| Un usuario de Apple tiene una dirección como `abc123@privaterelay.appleid.com` | La persona ha elegido "Hide My Email". Apple le reenvía el correo enviado a esa dirección. Guárdala tal cual. |
| El botón del proveedor no aparece en la página de inicio de sesión | El proveedor no está activado, falta un campo obligatorio, o las credenciales se han guardado pero el interruptor no se ha activado nunca. En ese caso, la insignia de la tarjeta muestra **Inactivo**. |
| Una persona inicia sesión con un proveedor y llega a una pantalla *Pendiente de aprobación* | Es lo esperado para los registros nuevos. Apruébala desde la lista de altas pendientes de los socios. |
| Alguien con una cuenta con contraseña existente ha iniciado sesión con Google y ha obtenido una cuenta **nueva** en lugar de la antigua | El proveedor ha informado de que el correo no estaba verificado, así que memship se ha negado a vincularlo (vincular una dirección no verificada permitiría a cualquiera apropiarse de una cuenta). Pídele que verifique la dirección con el proveedor. |

---

## 4. Correo

**Configuración → Integraciones → Correo**

### 4.1 Cómo funciona

memship envía correos para la verificación del registro, los avisos de aprobación/rechazo, el
restablecimiento de contraseñas, los recibos, los recordatorios de pago y las comunicaciones a los
socios. Todo pasa por **un solo** proveedor, que eliges aquí.

Se admiten dos proveedores:

- **Resend**, un servicio de envío gestionado, que se usa a través de su API. Mejor
  entregabilidad, más volumen, necesita un dominio que controles.
- **Servidor SMTP**, cualquier servidor de correo que acepte SMTP: el alojamiento de correo que tu
  entidad ya paga, un servicio de envío o una cuenta de Gmail. No tienes que registrarte en nada
  si ya tienes alojamiento de correo.

**Hay exactamente un proveedor activo a la vez.** La pantalla tiene un solo selector de
*Proveedor activo* con cuatro posiciones, **Ninguno / Resend / Servidor SMTP / SendPulse**. No hay
interruptores por proveedor, así que el estado "varios activados" no puede darse. Puedes tener
guardadas las credenciales de todos y cambiar de uno a otro en cualquier momento.

Con el proveedor activo en **Ninguno**, memship no envía absolutamente nada. Los correos se omiten
sin aviso (quedan registrados en el log, no en cola para más tarde). Los socios no recibirán
enlaces de verificación, avisos de aprobación ni recibos, así que trata *Ninguno* como un estado
temporal.

### 4.2 Resend: obtener las credenciales

Necesitas una **clave de API** y, idealmente, un **correo del remitente** en un dominio que hayas
verificado.

1. Crea una cuenta en **[resend.com](https://resend.com)**.
2. **Domains → Add domain**, introduce el dominio desde el que envías (p. ej. `myclub.org`).
   Resend muestra un conjunto de registros DNS (normalmente DKIM más una entrada SPF/MX para un
   subdominio `send.`).
3. Añade esos registros en tu proveedor de DNS (quien gestione tu dominio) y después pulsa
   **Verify**. La propagación suele tardar minutos, a veces horas.
4. **API Keys → Create API Key**.
   - Name: `memship`.
   - Permission: con **Sending access** basta.
   - Domain: el que acabas de verificar (o *All domains*).
   - Copia la clave: empieza por `re_` y se muestra **solo una vez**.
5. Decide tu **correo del remitente**, p. ej. `no-reply@myclub.org`. Tiene que ser de un dominio
   verificado; Resend rechaza cualquier otro.

> ¿Solo estás haciendo pruebas? Resend te deja enviar desde `onboarding@resend.dev` sin ningún
> dominio, pero solo a la dirección de correo propietaria de la cuenta de Resend. Sirve para un
> envío de prueba, no para el uso real.

### 4.3 SMTP: los datos de tu servidor, o Gmail

**Tu propio servidor de correo.** Quien te proporciona el alojamiento de correo publica estos
valores, normalmente bajo un título como *SMTP*, *correo saliente* o *configuración del cliente de
correo*:

- **Servidor**, p. ej. `mail.myclub.org` o `smtp.yourprovider.com`.
- **Puerto**, `587` en casi todos los casos.
- **Cifrado**, *STARTTLS*. Deja el interruptor activado salvo que el proveedor diga que el
  servidor no está cifrado.
- **Usuario y contraseña**, normalmente la dirección completa de un buzón y su contraseña. Algunos
  proveedores dan una contraseña SMTP aparte; si es así, usa esa. Un relay que acepta correo desde
  la dirección de tu servidor no necesita ninguna de las dos: deja las dos en blanco.
- **Correo del remitente**, la dirección que ven los socios. La mayoría de los servidores solo
  aceptan la dirección de un buzón que sea tuyo; déjalo en blanco para enviar como el usuario.

**Cifrado** elige cómo se protege la conexión: **STARTTLS**, normalmente en el puerto 587, que
mejora una conexión en claro; **SSL/TLS directo**, normalmente en el puerto 465, cifrado desde el
primer byte; o **sin cifrado**, para un servidor de tu propia red. Ponlo como lo documente tu
proveedor para el puerto que uses. Casi todos los proveedores que ofrecen el 465 también ofrecen el
587, y el 587 sigue siendo el valor por defecto.

**Gmail.** Pulsa **Usar la configuración de Gmail** en la tarjeta: rellena `smtp.gmail.com`, el
puerto `587` y STARTTLS. El usuario es la **dirección de Gmail**, y la contraseña es una
**contraseña de aplicación** de Google, una contraseña de 16 caracteres generada para una sola
aplicación. La contraseña normal de la cuenta no funcionará; Google la bloquea.

1. La cuenta tiene que tener la **verificación en 2 pasos activada con un número de teléfono o una
   aplicación de autenticación**: [myaccount.google.com/security](https://myaccount.google.com/security)
   → *2-Step Verification*. Sin ella, las contraseñas de aplicación no existen.
   - **Una passkey o una llave de seguridad solas no bastan.** Google indica que la verificación
     en 2 pasos está activada, pero la página de contraseñas de aplicación sigue sin estar
     disponible. Añade un segundo método, un número de teléfono (SMS/voz) o Google Authenticator,
     junto a la passkey; puedes conservar la passkey.
   - La vía de Gmail **no está disponible en absoluto**, sin ninguna alternativa, cuando la cuenta
     está inscrita en la **Protección Avanzada**, o cuando es una **cuenta de trabajo, de centro
     educativo o de otra organización** cuyo administrador no permite contraseñas de aplicación.
     Usa Resend, tu propio servidor de correo u otra cuenta de Google.
2. Ve a **[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)**.
3. Pon un nombre a la aplicación (p. ej. `memship`) y créala.
4. Google muestra una contraseña de 16 caracteres como `abcd efgh ijkl mnop`. Cópiala: como todos
   los secretos de aquí, solo se muestra una vez. Los espacios son estéticos; funciona con ellos o
   sin ellos.

Cosas que debes saber sobre la vía de Gmail:

- **Límites de envío:** aproximadamente 500 mensajes al día para una cuenta gratuita de Gmail,
  ~2.000 para Google Workspace. Superarlos hace que se bloquee temporalmente el envío de la
  cuenta. Un club con unos cuantos cientos de socios que haga una comunicación masiva puede
  llegar a ellos.
- Gmail **reescribe el correo del remitente** con la dirección de la propia cuenta, salvo que la
  dirección alternativa esté registrada en esa cuenta de Gmail ("Send mail as"). Por eso, el campo
  *Correo del remitente* es mejor dejarlo en blanco, y en ese caso se usa la dirección de Gmail.
- En una cuenta de trabajo, de centro educativo o de Google Workspace, las contraseñas de
  aplicación solo existen si el administrador de esa organización las permite. Si no, esta vía no
  está disponible para esa cuenta, consulta el paso 1.

### 4.4 Rellenar la pantalla, probar y activar

Orden recomendado: configurar, **probar** y después activar:

1. Rellena la tarjeta del proveedor:
   - **Resend**: *Clave de API* (secreto) y *Correo del remitente*.
   - **Servidor SMTP**: *Servidor*, *Puerto*, el interruptor *STARTTLS*, *Usuario SMTP*,
     *Contraseña* (secreto) y *Correo del remitente*, o pulsa primero **Usar la configuración de
     Gmail** y después añade la dirección de Gmail y la contraseña de aplicación. Son obligatorios
     el servidor y un remitente (un usuario o un correo del remitente).
2. Pulsa **Guardar**. La insignia de la tarjeta pasa a **Listo**.
3. Pulsa **Enviar prueba** en esa tarjeta. Se envía un mensaje de prueba **específicamente a
   través de ese proveedor**, aunque no sea el activo: esa es toda la gracia del botón, verificar
   las credenciales antes de pasarles el tráfico real. Va a tu propia dirección (el correo del
   superadministrador que ha iniciado sesión).
   - Éxito → una confirmación "Correo de prueba enviado". Mira tu bandeja de entrada, y la
     carpeta de spam.
   - Error → el error del proveedor se muestra en el mensaje (un fallo de autenticación SMTP, un
     rechazo de Resend, etc.).
   - El botón está desactivado mientras tienes cambios sin guardar ("Guarda los cambios antes de
     enviar la prueba") o mientras faltan campos obligatorios.
4. Cuando llegue la prueba, pon el selector **Proveedor activo** en ese proveedor y pulsa
   **Guardar**. La insignia pasa a **Activo**.

El orden se impone, no es solo una recomendación. El selector de *Proveedor activo* muestra un
proveedor en gris, y explica el motivo al pasar el ratón por encima, en tres casos:

- **Faltan campos obligatorios**, "Rellena las credenciales antes de activarlo".
- **Sus campos tienen cambios sin guardar**, "Guarda y prueba las nuevas credenciales antes de
  activarlo". Una prueba solo demuestra las credenciales guardadas, así que las nuevas hay que
  guardarlas y probarlas primero.
- **Ningún envío ha funcionado con las credenciales actuales**, "Envía una prueba correcta antes
  de activarlo". La prueba tiene que ser el envío más reciente, y también cuenta un correo real
  que haya salido bien. Si el último envío ha fallado, el proveedor sigue en gris hasta que una
  prueba vuelva a funcionar.

El proveedor que ya está activo nunca se muestra en gris por este motivo. Guardar otros cambios no
lo desactiva, aunque no se haya probado nunca. Poner el selector en **Ninguno** siempre es
posible.

Cuando una tarjeta tiene sus credenciales, una línea bajo su cabecera indica si se sabe que
funcionan. Cada correo enviado a través de ese proveedor la actualiza: la prueba, y también cada
mensaje real.

- **Sin verificar** (ámbar), todavía no se ha enviado nada con estas credenciales. Reemplazar una
  clave o una contraseña, o cambiarla en `.env`, devuelve la tarjeta a este estado, porque el
  resultado anterior era para otras credenciales.
- **Funciona** (verde), el proveedor ha aceptado el correo más reciente, con la fecha.
- **Falla** (rojo), el proveedor ha rechazado el correo más reciente, con la fecha y un motivo
  breve (credenciales rechazadas, proveedor inaccesible, límite de envío alcanzado…). **Enviar
  prueba** muestra el mensaje de error completo del proveedor.

*Funciona* significa que el proveedor ha aceptado el mensaje. No significa que el mensaje haya
llegado a la bandeja de entrada: un rebote o la carpeta de spam ocurren después, así que para eso
consulta el registro del propio proveedor.

Cambiar de proveedor más adelante es cuestión de dos clics: selecciona el otro proveedor y guarda.
Las credenciales del que dejas se conservan, así que puedes volver a él, una vez que vuelvan a
superar una prueba, si han cambiado desde entonces.

### 4.5 Solución de problemas del correo

| Síntoma | Causa y solución |
| ------- | ------------- |
| La prueba falla con un error de autenticación SMTP (`535`, "Username and Password not accepted") | El usuario o la contraseña son incorrectos. En Gmail: la contraseña de aplicación es incorrecta, se ha revocado o se ha desactivado la verificación en 2 pasos (lo que invalida todas las contraseñas de aplicación); genera una nueva. En tu propio servidor: comprueba si el proveedor da una contraseña SMTP aparte. |
| La prueba falla: conexión rechazada, tiempo de espera agotado o la conexión se corta enseguida | Servidor o puerto incorrectos, o **Cifrado** no concuerda con el puerto: el 465 necesita SSL/TLS directo y el 587 necesita STARTTLS. Algunas redes de alojamiento también bloquean el SMTP de salida; pregúntaselo al administrador del servidor. |
| [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) dice *"The setting that you are looking for is not available for your account."* | No se puede crear ninguna contraseña de aplicación para esta cuenta. O bien la verificación en 2 pasos solo está configurada con passkeys/llaves de seguridad (añade un número de teléfono o una aplicación de autenticación y recarga la página), o bien la cuenta tiene la Protección Avanzada, o bien es una cuenta de trabajo/centro educativo cuyo administrador bloquea las contraseñas de aplicación (sin alternativa, usa Resend u otra cuenta). Consulta el paso 1 de la 4.3. |
| La prueba falla: Resend "domain is not verified" / 403 | El correo del remitente no es de un dominio verificado en Resend, o los registros DNS no se han propagado. Comprueba *Domains* en Resend. |
| La prueba falla: Resend 401 / "API key is invalid" | Clave mal escrita, revocada o creada sin permiso de envío. Crea una clave nueva. |
| La prueba indica éxito pero no llega nada | Mira el spam. Para Resend, consulta el registro *Emails* de su panel por si hay un rebote. Para Gmail, mira la carpeta *Enviados* de la cuenta que envía. |
| No se envía nada de nada, sin errores en ningún sitio | El proveedor activo es **Ninguno**. Selecciona un proveedor y guarda. |
| Los socios dejan de recibir correo después de un periodo en que funcionaba | Se ha alcanzado el límite diario de Gmail o se ha revocado la contraseña de aplicación; en Resend, un dominio suspendido. La tarjeta del proveedor pasa a **Falla** y da un motivo breve. Usa **Enviar prueba** para ver el error real. |
| La etiqueta dice "del entorno" | Ese valor viene del archivo `.env` de la instalación. Funciona, pero lo que escribas en la pantalla tiene prioridad para ese campo. |
| Los correos llegan desde una dirección que no has configurado | Gmail ha reescrito el remitente con la dirección de la cuenta (es lo esperado), tu servidor solo permite enviar como el buzón con el que has iniciado sesión, o todavía lo proporciona un valor del archivo de entorno. |

---

## 5. Opciones de registro que acompañan a estas integraciones

Dos opciones a nivel de organización rigen el flujo de alta al que alimenta el SSO. **No están en
la pantalla de Integraciones**, todavía no tienen interfaz, y viven en el objeto `features` de la
configuración de la organización. Las dos valen **true** por defecto, que es la configuración
normal:

| Opción | Por defecto | Efecto |
| ------ | ------- | ------ |
| `public_registration` | `true` | Si alguien puede registrarse, ya sea con el formulario o con un proveedor. Ponla a `false` para un club cerrado cuyos socios los crea un administrador. Si está desactivada, la página de registro y los botones de proveedor para personas *nuevas* se rechazan. |
| `registration_requires_approval` | `true` | Si un registro nuevo espera en *pendiente* a que un administrador lo apruebe. Ponla a `false` y un registro nuevo se convierte en socio activo inmediatamente (con el número de socio asignado en el acto), sin pasar por la cola de aprobación. |

Cambiarlas requiere una llamada a la API de configuración (`PUT /api/v1/settings/`,
superadministrador) con el objeto `features`, o una actualización directa de la fila
`organization_settings`. Pídeselo a quien administre tu instalación si necesitas cambiar alguna.

Relacionado, e independiente de lo anterior: los enlaces de **verificación** del correo se envían
siempre, y apuntan a `FRONTEND_URL`. Si los enlaces de verificación de tus correos son incorrectos
(p. ej. `localhost`), esa variable está mal configurada en tu instalación.

---

## 6. Alternativa con el archivo de configuración (`.env`)

Todo lo que hay en la pantalla de Integraciones también se puede proporcionar a través del archivo
`.env` de la instalación. Esto existe por dos motivos: las instalaciones configuradas antes de que
existieran estas pantallas siguen funcionando sin tocar nada, y un operador puede precargar
credenciales en el momento del despliegue.

**La prioridad es por campo: lo que guardes en la pantalla gana; si un campo está vacío ahí, se
usa la variable de entorno.** La insignia **"del entorno"** te indica exactamente qué campos
vienen ahora mismo del archivo. Borrar un campo en la pantalla hace que vuelva a usar el valor del
entorno, si lo hay.

| Campo de la pantalla | Variable de entorno |
| ------------ | -------------------- |
| Google → ID de cliente | `GOOGLE_CLIENT_ID` |
| Google → Secreto de cliente | `GOOGLE_CLIENT_SECRET` |
| Apple → ID de cliente (Services ID) | `APPLE_CLIENT_ID` |
| Apple → ID de equipo | `APPLE_TEAM_ID` |
| Apple → ID de clave | `APPLE_KEY_ID` |
| Apple → Clave privada (.p8) | `APPLE_PRIVATE_KEY` |
| SendPulse → todos los campos | _(ninguna: este proveedor se configura solo desde la pantalla)_ |
| Resend → Clave de API | `RESEND_API_KEY` |
| Resend → Correo del remitente | `RESEND_FROM_EMAIL`, después `SMTP_FROM` |
| Servidor SMTP → Servidor | `SMTP_HOST` |
| Servidor SMTP → Puerto | `SMTP_PORT` |
| Servidor SMTP → Cifrado | `SMTP_SECURITY` y, si no, la obsoleta `SMTP_TLS` |
| Servidor SMTP → Usuario SMTP | `SMTP_USER` |
| Servidor SMTP → Contraseña | `SMTP_PASSWORD` |
| Servidor SMTP → Correo del remitente | `SMTP_FROM` |
| URL del backend (solo lectura) | `BACKEND_PUBLIC_URL` |
| _(ningún campo)_ (clave de cifrado de los secretos) | `MEMSHIP_SECRET_KEY`, `SECRETS_KEY_FILE` |

Notas:

- `BACKEND_PUBLIC_URL` es **solo de entorno** por diseño: describe cómo está publicado tu
  servidor. Tiene que ser correcta, porque las URI de redirección se derivan de ella.
- `MEMSHIP_SECRET_KEY` solo hay que definirla si quieres proporcionar tú mismo la clave de cifrado
  en lugar de dejar que la genere el servidor. `SECRETS_KEY_FILE` elige dónde se escribe la clave
  generada; tiene que estar en un volumen **persistente**.
- En una instalación que nunca ha usado estas pantallas, el correo sigue comportándose exactamente
  como antes: Resend si `RESEND_API_KEY` está definida, y si no, SMTP si `SMTP_HOST` está
  definida. En cuanto guardas cualquier cosa en la pantalla de Correo, pasa a mandar la selección
  explícita de *Proveedor activo*.

---

## 7. Referencia de campos

### Inicio de sesión (SSO)

| Proveedor | Campo | Secreto | De dónde sale | Ejemplo |
| -------- | ----- | ------ | ------------------- | ------- |
| Google | ID de cliente | no | Cloud Console → Credentials → OAuth client | `1234-abc.apps.googleusercontent.com` |
| Google | Secreto de cliente | **sí** | la misma pantalla | `GOCSPX-…` |
| Apple | ID de cliente | no | Developer → Identifiers → **Services ID** | `org.myclub.memship.web` |
| Apple | ID de equipo | no | Developer → Membership details | `9XYZ8ABCDE` |
| Apple | ID de clave | no | Developer → Keys → tu clave | `A1B2C3D4E5` |
| Apple | Clave privada (.p8) | **sí** | el contenido del archivo de clave descargado | `-----BEGIN PRIVATE KEY-----…` |

Todos los campos de un proveedor son obligatorios antes de que se pueda activar.

### Correo

| Proveedor | Campo | Secreto | Obligatorio | Notas |
| -------- | ----- | ------ | -------- | ----- |
| Resend | Clave de API | **sí** | sí | Empieza por `re_`; se muestra una vez, al crearla. |
| Resend | Correo del remitente | no | no | Tiene que ser de un dominio verificado en Resend. |
| Servidor SMTP | Servidor | no | sí | p. ej. `mail.myclub.org`; `smtp.gmail.com` para Gmail. |
| Servidor SMTP | Puerto | no | no | Por defecto, `587`. Usa el `465` con SSL/TLS directo. |
| Servidor SMTP | STARTTLS | no | no | Activado por defecto. |
| Servidor SMTP | Usuario SMTP | no | consulta las notas | Normalmente la dirección de un buzón; para Gmail, la dirección de Gmail. |
| Servidor SMTP | Contraseña | **sí** | no | Para Gmail, una contraseña de aplicación de 16 caracteres, no la contraseña de la cuenta. |
| Servidor SMTP | Correo del remitente | no | consulta las notas | Déjalo en blanco para enviar como el usuario. |

Un servidor SMTP necesita un remitente: un usuario o un correo del remitente. **Usar la
configuración de Gmail** rellena el servidor, el puerto y STARTTLS para una cuenta de Gmail.

---

## Lista de comprobación rápida

**Inicio de sesión con Google**
- [ ] La URL del backend de la pantalla es tu dirección pública real
- [ ] URI de redirección copiada de memship a la consola de Google, exactamente
- [ ] Pantalla de consentimiento publicada
- [ ] ID de cliente + secreto guardados, interruptor activado, la insignia dice **Activo**
- [ ] El botón aparece en la página de inicio de sesión y un inicio de sesión se completa

**Inicio de sesión con Apple**
- [ ] Dominio HTTPS en producción (no localhost)
- [ ] App ID con *Sign in with Apple* activado
- [ ] Services ID creado, dominio + return URL configurados, **el Services ID es el ID de cliente**
- [ ] Clave creada, `.p8` descargado y guardado en un lugar seguro, Key ID apuntado
- [ ] Team ID apuntado; los cuatro campos guardados, interruptor activado, la insignia dice **Activo**

**Correo**
- [ ] Credenciales del proveedor guardadas, la insignia dice **Listo**
- [ ] **Enviar prueba** ha funcionado y el mensaje ha llegado de verdad
- [ ] Selector de proveedor activo puesto en ese proveedor y guardado, la insignia dice **Activo**
- [ ] El aviso de cifrado está en verde
- [ ] El archivo de clave y la base de datos tienen copia de seguridad conjunta
