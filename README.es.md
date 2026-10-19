# Memship

🌐 [English](README.md) | **Español** | [Català](README.ca.md)

> **Memship ya se puede desplegar en producción.** Funciona en producción en la instancia del propio mantenedor, se instala y se actualiza con scripts que comprueban antes de actuar, y sus vías de cobro (domiciliación SEPA, y tarjeta con Stripe y Redsys) se han llevado a mano hasta un pago real. El desarrollo está activo y se agradecen [incidencias y solicitudes de funcionalidades](https://github.com/marcandreuf/memship/issues); las primeras entidades que lo desplieguen tienen soporte directo del mantenedor.

**Gestión de socios para todo tipo de entidades.**

Memship es un **software de gestión de socios** autohospedable y de **código fuente abierto**, con licencia [Elastic License 2.0](LICENSE), diseñado para **asociaciones culturales**, **clubs deportivos**, **colegios profesionales** y cualquier entidad basada en membresías. Controla las **cuotas**, las **inscripciones**, la **facturación de socios** y los **recibos** desde tu propia infraestructura. Con soporte para **domiciliación SEPA**, gestión de actividades y un portal completo para socios, Memship ofrece una solución moderna de **control de socios** y **gestión de clubs** sin depender de terceros. Despliega en tu servidor, mantén tus datos bajo tu control y gestiona tu comunidad con herramientas actuales.

---

## Qué estamos construyendo

La mayoría de herramientas de gestión de socios son plataformas SaaS caras o software obsoleto. Memship quiere cambiar eso: una solución moderna y completa que tú controlas. Sin dependencia del proveedor, sin coste por socio, sin que tus datos salgan de tus servidores.

- **Autohospedable** — funciona en cualquier servidor con Docker
- **Monotenant** — una base de datos por organización, aislamiento total de datos
- **Multiidioma** — castellano, catalán e inglés desde el primer día. Ampliable a cualquier idioma mediante contribuciones de la comunidad
- **Preparado para RGPD** — plantillas de términos legales y gestión de consentimientos integradas

## Inicio rápido (Docker)

> **Para probar Memship, no para usarlo.** Es la vía más rápida a una instancia
> funcionando en tu propia máquina: imágenes publicadas, volúmenes desechables y una
> contraseña de base de datos fija. Para gestionar una organización real, sigue
> la [Instalación](docs/getting-started/installation.md) — el mismo producto,
> configurado para poder respaldarlo, actualizarlo y conservarlo.

Prueba Memship con un solo comando, sin necesidad de clonar el repositorio:

```bash
mkdir -p "$HOME/memship-quickstart" && cd "$HOME/memship-quickstart"
curl -fsSL https://raw.githubusercontent.com/marcandreuf/memship/main/docker-compose.quickstart.yml -o docker-compose.yml
docker compose pull        # descarga las últimas imágenes publicadas
PORT=8081 docker compose up -d
```

A continuación, ejecuta la configuración, que te hace tres preguntas:

```bash
docker compose exec -it demo-memship-api python -m app.cli.seed
```

1. **Super admin** — eliges la dirección y la contraseña. No hay nada predefinido.
2. **Datos del club** — solo se ofrece si los hay, así que en una instalación nueva no hace nada.
3. **Configuración del club** — introduce los datos reales de tu organización, o genera un club de demostración.

Elige el club de demostración para explorar: crea un año completo de datos de ejemplo
realistas — ~60 socios en todos los estados, actividades, recibos en todos los estados
repartidos por los meses, mandatos SEPA y recordatorios del panel. También genera accesos
para un administrador de club y dos socios, y **muestra esas contraseñas una sola vez**,
así que guarda la salida. Se puede volver a ejecutar sin duplicar (idempotente).

Abre http://localhost:8081 e inicia sesión como super admin. Cambia `PORT=8081` por el
puerto que prefieras (por defecto es el 80).

Cuando termines de evaluarlo, vuelve a ejecutar el mismo comando y responde *sí* a la
pregunta sobre los datos del club: borra el club de demostración conservando tu super
admin y las pasarelas de pago que hayas configurado. Consulta
[Configuración inicial](docs/getting-started/first-setup.md).

## Lanzamientos

Memship sigue el [versionado semántico](https://semver.org/) y **los números de versión se asignan en el momento del lanzamiento, nunca se reservan por adelantado.** Una línea por versión; las notas completas de cada una están en la [página de lanzamientos](https://github.com/marcandreuf/memship/releases). Lo que viene a continuación está en la [Hoja de ruta](#hoja-de-ruta), y [Elegir una versión](CONTRIBUTING.md#choosing-a-version) explica cómo se escoge el número.

| Versión | Hito | Estado |
|---------|------|--------|
| v0.1.0 | Gestión de socios MVP — autenticación, RBAC, CRUD de socios, tipos de membresía, i18n, Docker, CI | Hecho |
| v0.1.1 | Envío de emails (SMTP) — correos de bienvenida, recuperación de contraseña | Hecho |
| v0.1.2 | Grupos, soporte tutores/menores, rol restringido (schema) | Hecho |
| v0.1.3 | Proxy inverso Caddy, scripts de copia de seguridad/restauración, mejoras para autoalojamiento | Hecho |
| v0.1.4 | Gestión de configuración de la organización (API + frontend) | Hecho |
| v0.1.5 | CRUD de actividades — modelos, modalidades, precios, frontend admin | Hecho |
| v0.1.6 | Patrón de entidad unificado — listado/detalle/pestañas consistente en todas las entidades | Hecho |
| v0.2.0 | Gestión de actividades — inscripciones, elegibilidad, lista de espera, descuentos, consentimientos, adjuntos | Hecho |
| v0.2.1 | Rediseño UX — sidebar Shadcn, modo oscuro, colores de marca, tablas compactas, inicio rápido | Hecho |
| v0.2.2 | Base de tests E2E (Cypress) — auth, socios, actividades, inscripciones | Hecho |
| v0.2.3 | Endurecimiento de errores y validación — notificaciones toast, handler global de errores, validación backend, StrEnum, 76 tests de validación, 16 tests E2E | Hecho |
| v0.2.4 | Corrección de errores — sidebar en modo oscuro, visualización de errores en formularios, protección de rutas, visibilidad de socios cancelados, eliminación de socio eliminada | Hecho |
| v0.2.5 | UX de actividades — rediseño de tarjeta de actividad, subida de imagen de portada, badges de estado de inscripción, miniaturas en listado, cuadrícula "Mis actividades", volumen Docker para almacenamiento | Hecho |
| v0.2.6 | Correcciones y testing — diálogos de confirmación Shadcn (reemplazan 13 alertas del navegador), corrección de código de descuento en seed, comprobación de plazo de autocancelación, reinscripción tras cancelación, 21 nuevos tests API, 9 nuevos tests E2E de elegibilidad | Hecho |
| v0.2.7 | Mejoras de actividades — skeletons de carga, estado de URL con nuqs | Hecho |
| v0.2.9 | Prerrequisitos de pagos — dirección y datos bancarios de la org, subida de logotipo, pestaña de contactos, IBAN del socio, Celery/Redis, notificaciones por email (Jinja2 + SMTP/Resend) | Hecho |
| v0.3.0 | Pagos y facturación básica — recibos, generación de PDF, IVA, generación de cuotas, historial de pagos del socio | Hecho |
| v0.3.1 | Correcciones — tests fallidos y README traducidos | Hecho |
| v0.3.2 | Correcciones — arreglo del pipeline de build del frontend | Hecho |
| v0.3.3 | Mejoras de CI — ejecución de tests más rápida | Hecho |
| v0.3.4 | Correcciones — limpieza de warnings y optimización de tests de integración | Hecho |
| v0.3.5 | Correcciones — tests de integración fallidos | Hecho |
| v0.3.6 | Optimización de CI — setup-uv v7, cache de hash de contraseñas, workers de test paralelos, hooks de versionado automático | Hecho |
| v0.4.0 | Domiciliación SEPA — gestión de mandatos, remesas, XML pain.008, forma de pago del socio | Hecho |
| v0.4.1 | Configuración de pasarelas de pago — gestión configurable desde el panel de super admin | Hecho |
| v0.4.2 | Infraestructura de webhooks + Stripe Checkout — webhooks de pasarela, estado de pago en tiempo real, flujo "Pagar ahora" del socio | Hecho |
| v0.4.3 | Integración Redsys — pasarela bancaria española con 3D Secure + Bizum | Hecho |
| v0.4.4 | Facturación recurrente — generación automática de cuotas | Hecho |
| v0.4.5 | Recordatorios de pago — notificaciones por email de recibos vencidos | Hecho |
| v0.5.0 | Comunicaciones simples — anuncios del admin a todos los socios / grupo / tipo de cuota | Hecho |
| v0.5.1 | Vista de envíos de comunicaciones — seguimiento de destinatarios + "Visto" en la app | Hecho |
| v0.7.0 | Carnet digital de socio + registro QR — carnet en PDF, numeración automática de socios | Hecho |
| v0.7.1 | Mejoras del carnet — vista de carnet para el admin, foto de perfil del socio, rediseño del perfil | Hecho |
| v1.0.0 | Estabilización y lanzamiento — exportaciones CSV, panel financiero, notas y recordatorios, resumen anual, datos demo, pulido de docs | Hecho |
| v1.0.1 | Parche — corrige el registro de tareas programadas de facturación/recordatorios en Celery; protección de CI contra la sobrescritura de etiquetas de imagen | Hecho |
| v1.1.0 | Campos de perfil personalizados — datos de socio configurables por la organización (texto, número, fecha, selección, …) con validación por campo y visibilidad/edición por campo | Hecho |
| v1.1.1 | Parche — reorganización de la navegación de configuración: ajustes de pagos y de socios agrupados en las pestañas Pagos y Socios | Hecho |
| v1.2.2 | SSO y configuración de correo — alta pública con verificación por correo y aprobación por la directiva, inicio de sesión con Google / Apple, y ajuste de Resend / Google SMTP desde una pestaña de Integraciones | Hecho |
| v1.3.0 | Reservas simples — reservas de socios en espacios compartidos mediante un calendario semanal, con aforo por franja y lista de espera FIFO | Hecho |
| v1.4.0 | Roles y permisos flexibles — asignación multi-rol y comprobaciones granulares por permiso en lugar de los cuatro roles fijos. También repara los stacks de despliegue que no ejecutaban ningún worker de Celery ni montaban volumen en el servicio de API | Hecho |
| v2.0.0 | Revisión del autoalojamiento — montajes bind visibles en el host bajo un único `MEMSHIP_DATA_ROOT`, contenedores del backend con el uid del operador y un `install.sh` de un solo comando. **Seguridad:** PostgreSQL y la API dejan de publicarse en internet. **Cambio incompatible:** `uv run` ya no funciona en los contenedores. | Hecho |
| v2.1.0 | Configuración inicial sin credenciales publicadas — el mismo proceso interactivo en todos los entornos, sin cuentas cuyas contraseñas se publiquen en este repositorio, más opciones desatendidas para instalaciones automatizadas | Hecho |
| v2.2.0 | Recuperación del superadministrador desde el servidor — su contraseña se restablece con `python -m app.cli.seed` en la máquina, no por correo. **Seguridad:** el acceso al buzón equivalía a controlar toda la instancia | Hecho |
| v2.3.0 | Archivos subidos tras autenticación, y un inicio de sesión que no se puede adivinar indefinidamente — el almacenamiento se servía como archivos estáticos, los tokens de restablecimiento volvían en la respuesta de la API y la clave de firma publicada era el valor por defecto. **Cambio incompatible:** quien la usaba recibe una nueva y se cierran todas las sesiones. | Hecho |
| v2.3.1 | Rutas de dinero que fallaban en silencio — un fichero SEPA ya no descarta recibos cuyo mandato se canceló, un webhook de pago ya no registra un importe distinto como pago completo, y una actividad ya no supera su aforo si dos personas se inscriben a la vez. | Hecho |
| v2.4.0 | El inicio de sesión exige una dirección de correo confirmada, y la numeración de recibos es correlativa y sin huecos. **Cambio incompatible:** una cuenta que nunca confirmó su dirección ya no puede entrar. **Migración:** la numeración pasa a un contador por año, inicializado con los números ya emitidos. | Hecho |
| v2.5.0 | Todo el correo saliente en una única plantilla con la identidad de la organización — nombre, logotipo y color se leen de la configuración, cada mensaje lleva una alternativa en texto plano junto al HTML, y el envío de recibos y el resumen de facturación pasan a ser plantillas. | Hecho |
| v2.6.0 | Un super administrador decide qué correos envía el sistema — una pantalla de Configuración con un interruptor por plantilla y los 17 puntos de envío pasando por una única puerta. **Cambio incompatible:** el correo opcional queda desactivado, así que una instalación existente se queda en silencio al actualizar. | Hecho |
| v2.7.0 | Sesiones que se deslizan en vez de caducar a mitad de tarea — una sesión activa se renueva a la mitad de su ventana y, al agotarse, lo dice y te devuelve al inicio de sesión. **Autoalojamiento:** una versión se despliega en un VPS sin git ni copia del código, desde un tarball de la publicación. | Hecho |
| v2.7.1 | Una primera instalación deja un `POST-INSTALL.md` en el servidor con lo que el instalador no puede hacer por ti — copiar `.env` fuera del host, crear la organización y el super administrador, programar copias y configurar el correo — con todas las rutas rellenadas. El aviso de la v2.7.0 era correcto y nadie lo leyó. | Hecho |
| v2.8.0 | Una cuota que el socio compra, y puede perder — el plan se compra desde el portal del socio a un precio prorrateado con impuestos incluidos, se concede cuando llega el dinero por cualquier vía, y se retira 21 días después de que venza una cuota impagada, guardando el nivel perdido para restituirlo al pagar. | Hecho |
| v2.9.0 | La pantalla en la que el socio compra su plan — la v2.8.0 sabía cobrar pero no dejaba pedirlo. **Mi plan** muestra el plan contratado y los disponibles, con el primer cargo prorrateado antes de confirmar nada. Comprar emite un recibo; el plan se activa al cobrarlo. | Hecho |
| v2.9.1 | Una primera instalación capaz de seguir sus propias instrucciones — cada arreglo salió de ejecutar la guía de principio a fin en un servidor nuevo. `vps-bootstrap.sh` se interrumpía por el bloqueo de apt al arrancar Ubuntu y dejaba el host sin cortafuegos ni fail2ban tras una salida que parecía correcta. | Hecho |
| v2.10.0 | Trece arreglos en las rutas que manejan dinero, datos personales y carga; ninguna pantalla nueva. Los tokens de restablecimiento se guardan como resumen, el IBAN completo deja de devolverse junto al enmascarado y las exportaciones CSV neutralizan las celdas con fórmula. **Cambio incompatible:** los enlaces de restablecimiento pendientes dejan de funcionar al actualizar. | Hecho |
| v2.11.0 | El personal no es socio del club — un super administrador o un administrador gestiona la instancia sin pertenecer a ella, en vez de llevar número de socio y contar en cada listado, exportación y facturación. **Migración irreversible:** las cuentas de personal pierden su ficha de socio. | Hecho |
| v2.12.0 | Acceso, correo, pagos y la propia actualización — las rutas con las que tropieza un club en sus primeras semanas. Las direcciones se guardan y comparan en minúsculas, y `upgrade.sh` pregunta a la API nueva por los datos antes de sustituir la pila. **Migración:** las direcciones existentes pasan a minúsculas. | Hecho |
| v2.13.0 | La versión de auditoría — diecisiete defectos encontrados leyendo el código contra su propia documentación, ninguna función nueva. Restablecer la contraseña cierra todas las sesiones que abrió, el límite de intentos se aplica a quien llama en vez de bloquear a todos los socios, y la facturación fecha en la zona horaria del club. | Hecho |
| v2.14.0 | La versión de caza de errores — dieciséis defectos reportados y una compilación que podía publicar una imagen incapaz de arrancar, sin funciones nuevas. Las compilaciones instalan `uv.lock` con `--locked` y cada imagen candidata se arranca antes de publicarse; los precios de actividad dejan de devolver el IVA a cero. | Hecho |
| v2.15.0 | Funciones alcanzables y la ruta de actualización — tres funciones publicadas que no se podían usar, y las comprobaciones que lo habrían detectado. | Hecho |
| v2.16.0 | La versión de las rutas del dinero — el circuito de cobro SEPA que un club ejecuta cada mes, repasado a mano en lugar de leído. | Hecho |
| v2.17.0 | La versión de revisión — once defectos encontrados leyendo el árbol y trabajando las pantallas, ninguno reportado por nadie, y la tubería de compilación que publicaba imágenes descuadradas. | Hecho |
| v2.18.0 | La versión de validación SEPA — dieciséis defectos encontrados conduciendo el cobro en una instancia desplegada. Una devolución contra un recibo ya cobrado deja de constar como atendida, y un fichero bancario generado no se sobrescribe. **Cambio incompatible:** `import-returns` informa por grupos. **Migración:** los mandatos activos duplicados se cancelan, se conserva el más reciente. | Hecho |
| v2.19.0 | La versión de los proveedores de pago — Bizum puede ofrecerse por separado de la tarjeta, un secreto guardado ya no se borra con un guardado en blanco, y una remesa enviada nombra el recibo que el banco devolvió. **Cambio incompatible:** Bizum viene desactivado. **Migración:** `remittance_receipts` registra qué recibos llevó cada remesa. | Hecho |

## Hoja de ruta

Priorizado, aún sin versión. Cada elemento se convierte en un lanzamiento versionado cuando se publica, y el lanzamiento toma el siguiente número semántico por orden. Cada elemento tiene una incidencia con su resumen y las ideas actuales — consulta las [incidencias con la etiqueta `roadmap`](https://github.com/marcandreuf/memship/labels/roadmap).

- **Invitaciones de usuarios** — invitar a un nuevo superadministrador, administrador del club o socio indicando su dirección de correo y su rol; la persona elige su propio nombre y contraseña. Se envían por correo cuando el correo está configurado, y como enlace copiable cuando no lo está, de modo que una instalación recién creada pueda añadir un segundo administrador sin acceso por consola
- **Copias de seguridad** — descargar una copia completa desde el área de administración, con la base de datos y los archivos subidos, y una restauración documentada y probada
- **Convocatorias** — convocatorias formales de Asamblea General con confirmación del socio mediante token
- **Biblioteca de documentos** — estatutos, actas, formularios con visibilidad por grupo
- **Calendario de eventos + confirmación de asistencia** — vista de calendario y seguimiento de participación
- **Integraciones** — conectar memship con las herramientas que el club ya utiliza, en lugar de pedirle que las abandone. Primero mensajería instantánea (WhatsApp, Telegram, Signal, Instagram), que es donde la mayoría de los clubes se comunican realmente; después suscripciones de calendario, exportaciones a contabilidad y facturación electrónica, envío de licencias a federaciones deportivas y webhooks salientes como vía genérica para todo lo demás. Cada conector tiene su propio coste y sus propias limitaciones, y se publica por separado

Las variaciones complejas se construyen bajo demanda, cuando una implementación real las necesita: GoCardless e-mandatos, PayPal, flujo de Stripe Invoice, acciones masivas en recibos, generador de informes personalizados, encuestas, facturación familiar, pagos y reservas recurrentes, alquiler de equipamiento, votación y adjuntos en convocatorias, y variantes más profundas de las funciones anteriores.

**Aplazado — las extensiones como sistema de módulos/plugins.** Los complementos opcionales como álbumes de fotos, foro, libro de visitas, directorio de enlaces, inventario/préstamos y widgets del portal necesitan un sistema de módulos diseñado dentro de la arquitectura, no añadido sobre ella. Esto espera a una futura revisión de esa arquitectura en lugar de publicarse como una función.

---

## Funcionalidades

**Gestión de socios** (disponible)
- Ciclo de vida completo del socio: alta, acogida, cambios de estado, baja
- Tipos de membresía con grupos, precios y restricciones por edad
- Soporte de tutores y menores de edad
- Control de acceso por roles: super admin, admin de organización, socio
- Configuración de la organización con imagen de marca (color corporativo, subida de logotipo), dirección, datos bancarios (IBAN/BIC) y series de facturación
- Gestión de datos de contacto del socio (teléfono, email, con tipos de contacto)
- Datos bancarios del socio (IBAN/BIC) para domiciliación bancaria SEPA
- Interfaz multiidioma (ES, CA, EN) con selector de idioma en el perfil
- Panel de administración con gráficos de estado (recharts)
- Patrón de entidad unificado: listado → detalle → pestañas para todas las entidades
- Notificaciones por email (confirmación de inscripción, cancelación, promoción desde lista de espera) mediante Celery/Redis
- Doble transporte de email: SMTP (autoalojado) o API Resend (gestionado)
- Plantillas de email Jinja2 con soporte de idioma (ES/CA/EN)

**Actividades e inscripciones** (disponible)
- Creación de actividades con gestión del ciclo de vida (borrador → publicada → archivada)
- Subida de imagen de portada por actividad (admin sube, visible como miniatura para socios)
- Modalidades (variantes con aforo, precio y plazos independientes)
- Tramos de precio con validez temporal (precio de preinscripción o "early bird")
- Inscripción online con comprobación de elegibilidad (tipo de membresía, edad, estado)
- Gestión de aforo con lista de espera automática y promoción
- Autocancelación con plazos configurables
- Códigos de descuento (porcentaje/fijo, máximo de usos, fechas de validez)
- Consentimientos legales por actividad (obligatorios/opcionales)
- Adjuntos obligatorios por actividad con subida de archivos
- Portal del socio: catálogo de actividades con miniaturas, badges de estado de inscripción, cuadrícula "Mis actividades"
- Portal de administración: gestión de inscripciones con cambios de estado

**Pagos y facturación** (disponible)
- Gestión de recibos con ciclo de vida de 7 estados (nuevo → emitido → pagado / devuelto / cancelado / vencido)
- Generación de recibos en PDF (WeasyPrint) con cabecera de la organización, datos del socio, desglose de IVA — en 3 idiomas (ES/CA/EN)
- Generación masiva de cuotas de membresía a partir de los tipos de membresía
- Recibo automático al inscribirse en una actividad (emitido al confirmar, cancelado al cancelar)
- Creación manual de recibos desde la ficha del socio
- Cálculo de IVA con tipo impositivo por defecto configurable por organización
- Numeración de facturas con prefijo configurable y reinicio anual opcional (ej: FAC-2026-0001)
- Formato de moneda europeo (1.234,56 €) según el idioma de la organización
- Autoservicio del socio: página "Mis recibos" con descarga de PDF
- Panel de administración: gráfico de estados de recibos + tarjetas de importes pendientes/cobrados/vencidos
- Notificación por email del recibo con PDF adjunto (mediante Celery + Resend o SMTP)
- Configuración → pestaña Pagos para facturación y datos bancarios

**Domiciliación SEPA** (disponible — v0.4.0)
- Gestión de mandatos SEPA (crear, PDF, subir firmado, cancelar)
- Procesamiento de remesas con XML SEPA (pain.008.001.02)
- Importación de devoluciones bancarias y seguimiento de estado
- Página de forma de pago para socios

**Pasarelas de pago** (previsto — v0.4.x)
- Gestión configurable de pasarelas de pago (configuración del super admin)
- Integración Stripe — pagos con tarjeta basados en factura con webhooks
- GoCardless — e-mandatos SEPA gestionados con flujo alojado
- Patrón de adaptador extensible para proveedores regionales (MercadoPago, Razorpay, etc.)

**Comunicaciones** (previsto)
- Campañas de email con plantillas y segmentación de audiencia
- Mensajería directa entre la directiva y los socios
- Plantillas de email multiidioma

**Reservas y espacios** (disponible)
- Espacios reservables con horario de apertura diario y franjas con fecha definidas por la directiva
- Reglas de repetición que materializan una serie de fechas (días de la semana elegidos, cada N semanas) y franjas de día completo
- Aforo por franja con lista de espera FIFO y promoción automática al cancelar
- Calendario semanal del socio con ocupación en vivo y autocancelación hasta un plazo configurable
- Correos de confirmación, lista de espera, promoción y cancelación por la directiva

**Informes y cuadros de mando** (previsto)
- Estadísticas y tendencias de membresía
- Resúmenes financieros
- Exportación de datos (CSV, PDF)

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.12+ / FastAPI / SQLAlchemy / Alembic |
| Frontend | Next.js / React / Tailwind CSS / Shadcn/ui |
| Base de datos | PostgreSQL 15 |
| Tareas en segundo plano | Celery worker + beat, con Redis como broker |
| Proxy inverso | Caddy — obtiene y renueva los certificados TLS por su cuenta |
| Contenedores | Docker + Docker Compose |
| CI | GitHub Actions |
| Registro | GitHub Container Registry (ghcr.io) |

## Desarrollo

El backend en Docker y el frontend en local con recarga en caliente de pnpm, gobernados por
`scripts/dev.sh`:

```bash
./scripts/dev.sh start all      # backend (Docker) + frontend (local)
./scripts/dev.sh status
./scripts/dev.sh test           # tests del backend
```

La instalación completa, todos los comandos, las URL de los servicios, la carga de datos inicial y
las suites de tests están en
**[Entorno de desarrollo local](docs/development/local-environment.md)** _(en inglés)_.

Consulta [CONTRIBUTING](CONTRIBUTING.md) para ramas, versionado y cómo se publica una versión.

## Instalación (Docker)

El autoalojamiento en producción vive en la documentación, para que haya una sola copia que mantener correcta:

- **[Instalación](docs/getting-started/installation.md)** — `vps-bootstrap.sh` en un servidor
  recién creado y después `install.sh`, que genera secretos reales, fija una versión y coloca tus
  datos en un único directorio respaldado
- **[Configuración inicial](docs/getting-started/first-setup.md)** — crear el super administrador y
  la organización
- **[Referencia de configuración](docs/self-hosting/configuration.md)** — todas las variables de
  entorno
- **[Copias de seguridad y restauración](docs/self-hosting/backups-and-restore.md)** — configúralo
  antes de entrar en producción
- **[Actualizaciones](docs/self-hosting/upgrading.md)** — pasar a una nueva versión
- **[Resolución de problemas](docs/self-hosting/troubleshooting.md)** — cuando algo no arranca

El [Inicio rápido](#inicio-rápido-docker) de arriba es solo para evaluación: incluye una clave de
firma publicada en este repositorio y guarda los datos en volúmenes desechables.

## Contribuir

Las contribuciones de código son bienvenidas. La base del proyecto — infraestructura, CI/CD y la arquitectura central — ya está asentada, y [CONTRIBUTING](CONTRIBUTING.md) explica el modelo de ramas, las convenciones de commits y pull requests, el versionado y cómo se publica una release _(en inglés)_. En resumen: crea una rama `feature/*` de vida corta a partir de `main` y abre un pull request de vuelta a `main`. Para preparar el entorno, empieza por [Local development environment](docs/development/local-environment.md) _(en inglés)_.

¿No escribes código? [Abre un issue](https://github.com/marcandreuf/memship/issues) — los informes de errores, las propuestas de funcionalidades, las preguntas y contar cómo usarías Memship son igual de bienvenidos, y para los dos primeros hay plantillas.

Las vulnerabilidades de seguridad se comunican por un canal privado, no en un issue público — consulta [SECURITY](SECURITY.md). Quien participa en el proyecto queda cubierto por el [Código de conducta](CODE_OF_CONDUCT.md).

[Accesibilidad](ACCESSIBILITY.md) explica a qué aspira el proyecto, qué se espera que compruebe quien contribuye y cómo informar de una barrera — incluido qué se ha probado de verdad y qué no _(en inglés)_. Si te topas con una, ahí está la vía para informar, con una dirección de correo para cuando GitHub sea precisamente el obstáculo.

## Licencia

Memship se distribuye bajo la [Elastic License 2.0 (ELv2)](LICENSE). Puedes usar, modificar y autoalojar Memship libremente. La licencia restringe ofrecerlo como servicio gestionado a terceros.
