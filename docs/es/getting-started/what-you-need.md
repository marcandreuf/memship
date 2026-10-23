<!-- source: en/getting-started/what-you-need.md -->
<!-- source-hash: 9f5a006988a7 -->

# Qué necesitas para ejecutar Memship

Esta página es para decidir **si** vas a ejecutar Memship. Dice qué necesita la plataforma, cuánto
cuesta eso y qué no necesita. Quien siga adelante después lee la
[Instalación](../../en/getting-started/installation.md), escrita para quien se pone delante del terminal.

> **En inglés:** [What you need to run Memship](../../en/getting-started/what-you-need.md).

Todo lo que sigue está **medido** sobre la versión 2.19.0, no estimado. Donde una cifra es un
criterio y no una medición, se dice.

## La respuesta corta

| | |
|---|---|
| **Un servidor** | 2 vCPU, 4 GB de RAM, 40 GB de SSD. Linux con Docker. Un Memship por máquina |
| **Un nombre de dominio** | Con un registro A apuntando al servidor. El HTTPS se resuelve solo |
| **Una forma de enviar correo** | Resend, Gmail o cualquier servidor SMTP. Esto no se puede saltar |
| **Lo que cuesta** | **De 8 a 12 € al mes**, IVA incluido, por todo lo anterior |
| **Quién lo instala** | Tú, el informático que ya tengas, o el mantenedor como servicio de pago |

Sin Kubernetes, sin base de datos gestionada, sin almacenamiento de objetos, sin licencia por
socio.

## El servidor

Memship ejecuta siete contenedores: un proxy inverso Caddy, la API, un worker de Celery, un
planificador Celery beat, el frontend de Next.js, Redis y PostgreSQL.

**Memoria medida.** Versión 2.19.0, tras sembrar un club de 60 socios, 28 actividades, 190
inscripciones, 80 recibos y 25 mandatos SEPA, y recorrer después las pantallas de socios,
actividades, recibos, remesas y mandatos y el resumen anual:

| Contenedor | Memoria residente |
|---|---|
| Frontend (Next.js) | 236 MiB |
| Worker de Celery | 149 MiB |
| API (FastAPI) | 131 MiB |
| Celery beat | 107 MiB |
| PostgreSQL | 42 MiB |
| Caddy | 12 MiB |
| Redis | 5 MiB |
| **Total** | **682 MiB** |

Así que toda la plataforma funciona en unos **0,7 GB**. La cifra del worker es la que produce una
máquina de 2 vCPU: Celery dimensiona su conjunto de procesos según el número de CPU, así que ahí
arranca dos. En una máquina mayor arranca más y consume unos 50 MiB por cada CPU adicional —
conviene saberlo si pones Memship en una máquina que ya tienes.

**Con 2 GB de RAM funciona; la recomendación son 4 GB.** La diferencia no la pide la aplicación.
La piden PostgreSQL, para tener memoria de sobra con la que cachear, y las actualizaciones, que
mantienen un rato las imágenes nuevas junto a las que están en marcha. 4 GB es además lo que
incluye el plan de entrada de todos los proveedores de abajo, así que pedir menos no ahorra nada.

**Disco medido.** Las cinco imágenes ocupan **1,06 GB** en disco y son una descarga de **358 MB**
— cinco y no siete, porque la API, el worker y el planificador usan la misma imagen. Una base de
datos con el club descrito arriba ocupaba 12 MB, dentro de un directorio de datos de PostgreSQL de
50 MB.

Cuenta una base de **1,5 GB**, más el sistema operativo. Lo que crece son solo los archivos que
sube la gente:

- Una foto por socio y una imagen de portada por actividad, que se reemplazan en vez de acumularse
- Los adjuntos de las inscripciones a actividades, que sí se acumulan
- Los ficheros de remesa SEPA generados

Cada archivo subido está limitado a 10 MB (`MAX_UPLOAD_SIZE_MB`). **Los PDF de recibos y mandatos
se generan al pedirlos y no se escriben nunca en disco**, así que no son un factor de crecimiento.
Un club de 500 socios con una foto cada uno no llega al gigabyte. Los 40 GB que traen los planes
de entrada no son una restricción por la que tengas que comparar proveedores; deja margen por
encima si guardas las copias de seguridad de la base de datos en la misma máquina.

**Sistema operativo:** cualquier Linux con Docker Engine y el complemento Compose.
`scripts/vps-bootstrap.sh` prepara un servidor recién creado con **Debian 12** o **Ubuntu 24.04**,
que es lo que ese script espera.

**Un Memship por máquina.** Los contenedores llevan nombre fijo (`memship-db`, `memship-api`, …) y
los nombres de Docker son únicos en todo el demonio, así que una segunda instancia en la misma
máquina falla a medias. Usa otro servidor, o una máquina virtual.

## Lo que cuesta

Planes de entrada de dos proveedores europeos, los dos de 2 vCPU / 4 GB / 40 GB NVMe, comprobados
el 2026-10-20:

| Proveedor | Plan | Sin IVA | Con el 21 % de IVA |
|---|---|---|---|
| [Hetzner](https://www.hetzner.com/cloud/) | CX23 | 5,49 €/mes | ≈ 6,64 €/mes |
| [OVHcloud](https://www.ovhcloud.com/es-es/vps/) | VPS-1 | 3,81 €/mes | 4,61 €/mes |

La cifra de OVHcloud es su tarifa pagando doce meses por adelantado; mes a mes cuesta más. Hetzner
subió los precios de su nube el 15 de junio de 2026, así que la cifra de arriba es la vigente y
las comparaciones más antiguas se quedan cortas.

Además del servidor:

- **Un dominio**, normalmente de 10 a 15 € al año, o sea alrededor de 1 € al mes.
- **El correo**, gratis para una entidad pequeña. El plan gratuito de Resend cubre 3.000 mensajes
  al mes, y Gmail funciona con una cuenta normal. Mira los límites de más abajo antes de dar por
  hecho que el plan gratuito te vale.

Sumando: el plan de Hetzner a 6,64 € con IVA, más 1 € al mes de dominio, más nada de correo en un
plan gratuito, sale por **menos de 8 € al mes**. Cuenta con **8 a 12 € al mes con IVA** y eso te
cubre un servidor mayor o un plan de correo de pago a medida que crezca la entidad. No hay coste
por socio, ni por administrador, ni por recibo.

## Un nombre de dominio

Un nombre de máquina, con un registro **A** del DNS apuntando a la IP del servidor. En cuanto eso
resuelve, el Caddy que viene incluido obtiene y renueva un certificado de Let's Encrypt por su
cuenta — no hay certificado que comprar, ni instalar, ni acordarse de renovar.

Si el dominio es de la entidad y no de quien instala — de forma que el nombre de máquina, la zona
DNS y el dominio del correo son asunto de tres personas distintas — lee
[El dominio de tu organización](../../en/self-hosting/domain-and-dns.md) antes de empezar.

## Una forma de enviar correo

Memship necesita enviar correo transaccional, y esto **no es opcional**: el restablecimiento de
contraseña, la verificación de la dirección y los avisos de pago van todos por ahí, y un socio no
puede entrar por primera vez hasta que funcione.

Tres opciones, configurables desde la pantalla de Ajustes o desde el `.env`:

- **Resend** — una API de correo. Plan gratuito: 3.000 mensajes al mes y 3 dominios, pero **100 al
  día**. Ese límite diario es el que molesta: mandar avisos a más de 100 socios de una tirada lo
  supera. El plan de pago son 20 USD al mes.
- **Gmail** — una cuenta de Google normal con una contraseña de aplicación. Google aplica sus
  propios límites diarios de envío.
- **Cualquier servidor SMTP** — incluido el del alojamiento de correo que ya tenga la entidad,
  siempre que acepte STARTTLS, normalmente en el puerto 587. Un servidor accesible solo por el
  puerto 465 no está soportado.

[Envío de correo](../../en/self-hosting/email.md) cubre las tres, incluidos los registros DNS que
necesita Resend.

## Cuánto tarda

Con las imágenes ya en el servidor, la plataforma arranca y responde como saludable en **16
segundos**.

El tiempo de principio a fin de una primera instalación en un servidor recién creado —
`scripts/vps-bootstrap.sh`, luego `scripts/install.sh`, y luego crear el primer administrador — no
está medido, y esta página no se lo va a inventar. Lo que domina ese tiempo es la descarga de las
imágenes (358 MB) y la propagación del registro DNS que crees para el dominio.

## Lo que no necesita

- **Kubernetes, no**, ni ninguna orquestación más allá de Docker Compose.
- **Base de datos gestionada, no.** PostgreSQL es uno de los siete contenedores.
- **Almacenamiento de objetos, no.** Lo que se sube va a un directorio del disco del servidor.
- **Un servicio de colas aparte, no.** Redis y Celery van dentro.
- **Sin cuota de licencia y sin coste por socio.** Memship es de código fuente abierto, con
  licencia [Elastic License 2.0](https://github.com/marcandreuf/memship/blob/main/LICENSE). Puedes
  usarlo, modificarlo y autoalojarlo libremente; la licencia restringe ofrecerlo como servicio
  gestionado a terceros, que no es lo que hace una entidad que lo ejecuta para sus propios socios.

## Quién lo instala

- **Tú mismo**, o cualquiera que se maneje con un servidor Linux y un panel de DNS.
- **El informático que ya use la entidad**, que no necesita nada de este proyecto más allá de la
  [Instalación](../../en/getting-started/installation.md).
- **El mantenedor, como servicio de pago**, si nadie en la entidad quiere hacerse cargo de un
  servidor.

## Y ahora

- Si ya está decidido, lo siguiente es instalar: [Instalación](../../en/getting-started/installation.md).
- Si prefieres tocarlo antes, sin servidor ninguno: la [Prueba rápida](../../en/getting-started/quickstart.md) levanta toda
  la plataforma en tu propia máquina con una sola orden. Es solo para evaluar.
