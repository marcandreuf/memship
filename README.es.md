# Memship

🌐 [English](README.md) | **Español** | [Català](README.ca.md)

> **Este proyecto está en desarrollo activo, aún no está preparado para producción, y acepta [solicitudes de funcionalidades](https://github.com/marcandreuf/memship/issues).**

**Gestión de socios para todo tipo de entidades.**

Memship es un **software de gestión de socios** open source y autohospedable, diseñado para **asociaciones culturales**, **clubs deportivos**, **colegios profesionales** y cualquier entidad basada en membresías. Controla las **cuotas**, las **inscripciones**, la **facturación de socios** y los **recibos** desde tu propia infraestructura. Con soporte para **domiciliación SEPA**, gestión de actividades y un portal completo para socios, Memship ofrece una solución moderna de **control de socios** y **gestión de clubs** sin depender de terceros. Despliega en tu servidor, mantén tus datos bajo tu control y gestiona tu comunidad con herramientas actuales.

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
| v2.0.0 | Revisión del autoalojamiento — montajes bind visibles en el host bajo un único `MEMSHIP_DATA_ROOT`, contenedores del backend con el uid del operador y un `install.sh` de un solo comando. **Seguridad:** PostgreSQL y la API dejan de publicarse en internet. **Cambio incompatible:** `uv run` ya no funciona en los contenedores y las instalaciones existentes necesitan un `chown` una sola vez | Hecho |
| v2.1.0 | Configuración inicial sin credenciales publicadas — el mismo proceso interactivo en todos los entornos, sin cuentas cuyas contraseñas se publiquen en este repositorio, más opciones desatendidas para instalaciones automatizadas | Hecho |
| v2.2.0 | Recuperación del superadministrador desde el servidor — su contraseña se restablece con `python -m app.cli.seed` en la máquina, no por correo. **Seguridad:** el acceso al buzón equivalía a controlar toda la instancia | Hecho |
| v2.3.0 | Archivos subidos tras autenticación, y un inicio de sesión que no se puede adivinar indefinidamente — **Seguridad:** el directorio de almacenamiento se servía como archivos estáticos, los tokens de restablecimiento volvían en la respuesta de la API y la clave de firma de ejemplo publicada era el valor por defecto de compose. **Cambio incompatible:** las instalaciones que usaban esa clave reciben una nueva y cierran todas las sesiones | Hecho |
| v2.3.1 | Rutas de dinero que fallaban en silencio — un fichero SEPA ya no descarta recibos cuyo mandato se canceló, un webhook de pago ya no registra un importe distinto como pago completo, y una actividad ya no puede sobrepasar su aforo si dos personas se inscriben a la vez. **Comportamiento:** una remesa cuyo mandato ha desaparecido ahora falla con un error en lugar de generar un fichero incompleto, y un pago por un importe distinto deja el recibo pendiente de revisión | Hecho |
| v2.4.0 | El inicio de sesión exige una dirección de correo confirmada, y la numeración de recibos es correlativa y sin huecos. **Cambio incompatible:** una cuenta que nunca confirmó su dirección ya no puede entrar — `python -m app.cli.verify_email` la confirma desde el servidor cuando el correo de confirmación es lo que falla. **Migración:** la numeración pasa a un contador por año, inicializado con los números ya emitidos | Hecho |
| v2.5.0 | Todo el correo saliente usa una única plantilla con la identidad de la organización — nombre, logotipo y color se leen de la configuración, cada mensaje incluye ya una alternativa en texto plano junto al HTML, y el envío de recibos y el resumen de facturación recurrente pasan a ser plantillas en lugar de HTML incrustado. Además: una inscripción cuyo recibo falla al generarse ya no se deshace con él, y `SEED_EMAIL_DOMAIN` permite que una instalación que envía correo real siembre un club de demostración en un dominio capaz de recibirlo | Hecho |
| v2.6.0 | Un super administrador decide qué correos envía el sistema — una pantalla de Configuración con un interruptor por plantilla, y los 17 puntos de envío pasando por una única puerta en lugar de enviar sin condiciones. El indicador de la función de comunicados ahora cierra sus endpoints en vez de limitarse a ocultar la navegación, y una política de plantillas ilegible falla cerrada, porque no equivale a un consentimiento. **Cambio incompatible:** el correo opcional queda desactivado por defecto, así que una instalación existente se queda en silencio al actualizar hasta que un super administrador active las plantillas que quiera — solo la verificación de dirección y el restablecimiento de contraseña siguen enviándose | Hecho |

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

### Requisitos previos

- Docker y Docker Compose instalados
- Git (para clonar el repositorio)

### Opción A: Imágenes preconstruidas (recomendado)

Utiliza las imágenes publicadas en [GitHub Container Registry](https://github.com/marcandreuf/memship/pkgs/container/memship-backend).

```bash
git clone https://github.com/marcandreuf/memship.git
cd memship

# Configurar
cp .env.example .env
# Edita .env — como mínimo cambia SECRET_KEY y DB_PASSWORD
# Establece la versión de la imagen:
#   IMAGE_TAG=0.1.3

# Descargar e iniciar todos los servicios (Caddy + API + Frontend + PostgreSQL)
docker compose pull
docker compose up -d

# Ejecutar la configuración inicial (crea las cuentas de admin)
docker compose exec -it api python -m app.cli.seed

# Abre http://localhost
```

### Opción B: Compilar desde el código fuente

Compila las imágenes Docker localmente a partir del código fuente del repositorio.

```bash
git clone https://github.com/marcandreuf/memship.git
cd memship
cp .env.example .env
docker compose up -d --build
docker compose exec -it api python -m app.cli.seed
```

### Servicios

| Servicio | URL | Descripción |
|----------|-----|-------------|
| Frontend | http://localhost | Portal del socio (mediante Caddy) |
| API | http://localhost/api/v1/health | API backend (mediante Caddy) |
| API directa | http://localhost:8003 | API backend (acceso directo) |
| Documentación API | http://localhost:8003/api/docs | Swagger UI (solo en modo desarrollo) |

### Copias de seguridad

```bash
# Crear una copia de seguridad
./scripts/db-backup.sh

# Listar y restaurar desde una copia (simulación por defecto)
./scripts/db-restore.sh

# Restaurar con confirmación
./scripts/db-restore.sh --confirm
```

Las copias de seguridad se almacenan en el directorio `backups/`. Las copias antiguas se eliminan automáticamente tras 10 días.

## Contribuir

Memship está en sus primeras fases. Las contribuciones de código serán bienvenidas una vez que la base del proyecto esté asentada — permanece atento.

Mientras tanto, no dudes en [abrir un issue](https://github.com/marcandreuf/memship/issues) para compartir ideas, sugerir funcionalidades o hacer preguntas. Todo feedback es bienvenido.

## Licencia

Memship se distribuye bajo la [Elastic License 2.0 (ELv2)](LICENSE). Puedes usar, modificar y autoalojar Memship libremente. La licencia restringe ofrecerlo como servicio gestionado a terceros.
