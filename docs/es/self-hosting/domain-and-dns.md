<!-- source: en/self-hosting/domain-and-dns.md -->
<!-- source-hash: 2d38b31431ce -->

# El dominio de tu organización

La [Instalación](../../en/getting-started/installation.md) _(en inglés)_ da por hecho un nombre de
máquina que ya resuelve a tu servidor. Esta página trata de cómo llegar ahí cuando el dominio es
de una organización y no tuyo: qué nombre elegir, qué registros crear, y las dos o tres formas en
que sale mal que te cuestan una hora cada una.

> **En inglés:** [Your organisation's domain](../../en/self-hosting/domain-and-dns.md).
> **En català:** [El domini de la teva entitat](../../ca/self-hosting/domain-and-dns.md).

Nada de esto es específico de las tripas de memship. Si tu DNS ya está configurado y solo quieres
instalar, ve directamente a la [Instalación](../../en/getting-started/installation.md)
_(en inglés)_.

## Quién tiene que hacer qué

El dominio de una asociación no suele tenerlo quien hace la instalación. Averigua quién tiene
estas cosas antes de reservarte una tarde para ello: esperar el acceso al registrador es el motivo
más habitual de que se retrase una puesta en marcha.

| Qué | Quién lo suele tener | Para qué hace falta |
|---|---|---|
| La cuenta del registrador (donde se compró el dominio) | alguien de la junta, o quien montó la web | para nada, normalmente, salvo que el DNS también se sirva ahí |
| La zona DNS (donde se editan los registros) | quien lleve la web de la organización | el registro `A` de memship |
| El correo de la organización | a veces, otro proveedor distinto más | el dominio de envío, más adelante |
| El servidor | tú | todo lo demás |

El registrador y el proveedor de DNS suelen ser la misma empresa, pero no siempre. Lo que
necesitas es a quien pueda añadir un registro a la zona.

## Elige el nombre de máquina

**Usa un subdominio, no el dominio raíz.** `socios.myclub.org`, `members.myclub.org`,
`app.myclub.org`, el que la organización vaya a reconocer. El dominio raíz (`myclub.org` sin
prefijo) casi siempre apunta ya a la web de la organización, y apuntarlo a memship tumba esa web.

Un subdominio significa además que nunca tocas un registro existente: añades uno, y la web sigue
funcionando todo el tiempo. Si algo sale mal, borrar el registro que añadiste lo deja todo como
estaba.

> **memship responde exactamente en un nombre de máquina.** El `Caddyfile` sirve un único sitio,
> el que se indica en `SITE_ADDRESS`. No hay alias `www` ni segundo nombre:
> `www.socios.myclub.org` no resolverá, y si hubieras puesto memship en el dominio raíz,
> `www.myclub.org` tampoco llegaría a él. Elige el nombre que se le va a dar a la gente, y usa ese
> en todas partes.

Elige el nombre antes de instalar, no después. Se escribe en cuatro ajustes, la dirección del
sitio de Caddy más las tres URL públicas que construyen los enlaces de los correos, el origen CORS
y la URL de retorno del proveedor de pagos, y después se registra a mano en algunos sitios más; ver
[Cambiarlo más adelante](#cambiarlo-más-adelante) para saber lo que cuesta.

## Los registros que hay que crear

Un registro. En tu proveedor de DNS, en la zona de `myclub.org`:

| Campo | Valor |
|---|---|
| Tipo | `A` |
| Nombre / Host | `socios` (solo la etiqueta, la mayoría de proveedores añaden el dominio por ti) |
| Valor | la **dirección IPv4 pública** de tu servidor |
| TTL | 300 segundos mientras lo estás configurando |

Un TTL corto no cuesta nada y significa que un error se corrige en cinco minutos en vez de en un
día. Súbelo después si quieres.

### Si el servidor tiene IPv6

O añades un registro `AAAA` con la dirección IPv6 del servidor, o te aseguras de que el nombre no
tenga **ningún** registro `AAAA`. Las dos cosas valen. Lo que no vale es un registro `AAAA` que
apunte a otro sitio, y en el dominio de una organización es una posibilidad real, porque un
comodín o un registro heredado del alojamiento de la web pueden aportar uno que tú nunca creaste.

> **Esta es la trampa que conviene conocer.** `install.sh` comprueba solo el registro `A`, así que
> informa de éxito. Let's Encrypt, al validar el certificado, se conecta por IPv6 cuando existe un
> registro `AAAA`, y solo recurre a IPv4 cuando la conexión *falla*, no cuando sale bien y devuelve
> otra cosa. Un `AAAA` obsoleto que apunta a un servidor web en marcha responde, sirve un 404, y la
> validación falla. Tienes entonces cinco intentos fallidos por hora antes de que Let's Encrypt te
> haga esperar.
>
> Compruébalo expresamente: `dig +short AAAA socios.myclub.org` debería imprimir la dirección de
> tu servidor o nada en absoluto.

### Lo que no hay que hacer

- **No actives el proxy de tu proveedor de DNS**: la nube naranja de Cloudflare, o cualquier
  interruptor de "CDN"/"proxy web" en el registro. La validación del certificado tiene que llegar
  directamente a tu máquina, y el proxy terminaría el TLS él mismo. `install.sh` avisa cuando lo
  detecta, y lo nombra.
- **Un `CNAME` solo funciona si al final resuelve a este servidor.** Un registro `A` es más simple
  y es una cosa menos en la que pensar. Muchos proveedores, además, no admiten un `CNAME` en el
  dominio raíz.
- **No uses el nombre de máquina del servidor que sale en el panel de tu proveedor**
  (`vps-12345.example-host.net`). Resuelve, así que la instalación funciona, pero es suyo: puede
  cambiar, y los socios lo tendrán en sus navegadores y en cada enlace de los correos.

## Compruébalo y luego instala

Desde el servidor:

```bash
dig +short A    socios.myclub.org    # your server's IPv4
dig +short AAAA socios.myclub.org    # your server's IPv6, or nothing
curl -fsS https://api.ipify.org      # what this host's public IPv4 actually is
```

La primera y la tercera tienen que coincidir. La propagación suele ser cuestión de minutos; un
nombre que antes resolvía a otra cosa puede tardar tanto como su TTL anterior.

Luego instala con el nombre, siguiendo la [Instalación](../../en/getting-started/installation.md)
_(en inglés)_:

```bash
./scripts/install.sh --data-root /srv/openmemship/data \
                     --domain socios.myclub.org --tag 2.19.0
```

> **Deja el puerto 80 abierto después.** Los certificados se renuevan con la misma validación HTTP
> con la que se emitieron, más o menos cada 60 días, y un cortafuegos que más tarde se cierre a
> "solo 443" rompe la renovación sin avisar: te enteras cuando caduca el certificado.
> `vps-bootstrap.sh` abre el 80 y el 443, y los dos deben seguir abiertos.

Si el DNS todavía no está listo y quieres poner la plataforma en marcha igualmente, instala sin
`--domain` y añádelo en una ejecución posterior. Ese es el camino de ensayo documentado, y la
[Instalación](../../en/getting-started/installation.md#without-a-domain) _(en inglés)_ explica por
qué además te ahorra gastar certificados.

## El correo es una decisión de dominio aparte

La dirección desde la que envía memship **no** tiene por qué estar, y normalmente no debería, en el
subdominio que acabas de crear. Los socios reconocen `no-reply@myclub.org`; nadie reconoce
`no-reply@socios.myclub.org`.

Eso supone un segundo juego de registros DNS, sin relación con el de arriba:

- El registro `A` del sitio hace que la aplicación sea accesible. Para el correo no hace nada.
- Un dominio de envío necesita los registros que pida tu proveedor de correo; con Resend, un
  registro DKIM más un par SPF/MX en un subdominio `send.`. El recorrido está en
  [Integraciones → Correo](../../en/admin-guide/integrations.md#4-mailing) _(en inglés)_, y
  [Envío de correo](email.md) cubre cómo elegir entre Resend y SMTP.

Dos cosas que hay que acordar con quien lleve el correo de la organización, porque son suyas y no
tuyas:

- **Desde qué dirección envía memship**, y que esté en un dominio al que puedan añadir registros.
- **Si el dominio publica una política DMARC.** Si la publica, un servicio de envío nuevo tiene
  que alinearse con ella o se resiente la reputación del correo de la propia organización. Añadir
  memship como remitente es un cambio en su configuración de correo, no solo en la tuya.

El correo que no funciona es invisible por diseño: [Envío de correo](email.md) explica que, sin un
proveedor activo, los envíos se omiten y se registran en el log en vez de ponerse en cola o
notificarse. Envía un mensaje de prueba desde la pantalla de ajustes antes de decirle a nadie que
la instancia está en marcha, y recuerda que los socios no pueden entrar hasta que funcione el
correo, porque primero confirman su dirección.

## Cambiarlo más adelante

Volver a ejecutar `install.sh --domain <new-name>` actualiza `SITE_ADDRESS` y las tres URL
públicas a la vez, así que nada se queda apuntando al nombre antiguo. Lo que no puede actualizar es
todo lo que hay fuera de memship y al que se le dio el nombre antiguo:

| Dónde | Qué se rompe |
|---|---|
| SSO de Google / Apple | la URI de redirección se registra por nombre de máquina y tiene que coincidir exactamente, o el inicio de sesión falla. [Integraciones → SSO](../../en/admin-guide/integrations.md#3-single-sign-on-sso) _(en inglés)_ |
| Webhooks de Stripe | la URL del endpoint se registra en el panel de Stripe. **Edita el endpoint existente** en vez de crear otro: un destino nuevo emite un secreto de firma nuevo, memship guarda uno, y entonces todos los eventos fallarían la verificación, lo que se ve exactamente igual que un pago que, sin avisar, nunca llega |
| Correos ya enviados | sus enlaces siguen apuntando al nombre antiguo mientras resuelva |
| Marcadores de los socios | el nombre antiguo tiene que seguir resolviendo, o redirigiendo, mientras te importe |

Redsys no necesita ningún cambio: memship envía la URL de retorno con cada transacción en vez de
tenerla registrada.

Nada de eso es difícil, pero es el motivo de que elegir el nombre de máquina una sola vez, antes de
la puesta en marcha, merezca diez minutos de reflexión.

## Ver también

- [Instalación](../../en/getting-started/installation.md) _(en inglés)_, la instalación en sí, y
  los avisos sobre el límite de certificados que conviene leer antes del primer intento
- [Primera puesta en marcha](../getting-started/first-setup.md), lo que la organización tiene que
  decidir una vez la instancia está levantada
- [Referencia de configuración](configuration.md), `SITE_ADDRESS`, `FRONTEND_URL`, `CORS_ORIGINS`,
  `BACKEND_PUBLIC_URL` y el resto
- [Resolución de problemas](troubleshooting.md), cuando la plataforma está levantada pero el sitio
  no es accesible
