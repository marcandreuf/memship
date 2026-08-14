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
> clave secreta que está en este repositorio. Para gestionar una organización real,
> sigue la [Instalación](docs/getting-started/installation.md) — el mismo producto,
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

## Hoja de ruta

Memship sigue el [versionado semántico](https://semver.org/) y **los números de versión se asignan en el momento del lanzamiento, nunca se reservan en la hoja de ruta por adelantado.** A continuación, la tabla **Publicado** es el historial lanzado; **Planificado** es una lista priorizada de lo siguiente. Un elemento planificado recibe versión solo cuando se lanza — consulta [Elegir una versión](CONTRIBUTING.md#choosing-a-version) para saber cómo se escoge el número.

### Publicado

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
| v1.2.2 | Integración SSO / identidad y configuración de correo — alta pública con verificación por correo, flujo de aprobación por la directiva, inicio de sesión con Google / Apple, configuración de proveedores SSO por el superadministrador y ajuste de Resend / Google SMTP desde una pestaña de Integraciones. También elimina una migración duplicada de configuración de correo cuyo identificador de revisión chocaba con otro existente, lo que hacía fallar `alembic upgrade head` al arrancar | Hecho |
| v1.3.0 | Reservas simples — reservas de socios en espacios compartidos mediante un calendario semanal, aforo por franja, lista de espera FIFO con promoción automática y correos de confirmación/lista de espera | Hecho |
| v1.4.0 | Roles y permisos flexibles — asignación multi-rol y comprobaciones granulares por permiso en lugar de los cuatro roles fijos, con una API `/roles` de gestión y navegación y acceso a páginas guiados por permisos en todo el portal. También repara los stacks de despliegue publicados, que no ejecutaban ningún worker de Celery — por lo que todos los correos que envía el producto se perdían en silencio y las tareas nocturnas de facturación y de recordatorios de pago no se ejecutaban nunca — y no montaban ningún volumen en el servicio de API, de modo que una actualización destruía los archivos subidos y regeneraba la clave secreta que cifra las credenciales almacenadas de SSO y de los proveedores de pago | Hecho |
| v2.0.0 | Revisión del autoalojamiento — los datos persistentes pasan a montajes de tipo bind visibles en el host bajo un único `MEMSHIP_DATA_ROOT`, los contenedores del backend se ejecutan con el uid del propio operador, un `install.sh` de un solo comando y `vps-bootstrap.sh` para preparar el servidor. **Seguridad:** PostgreSQL y la API dejan de publicarse en internet — Docker escribe sus reglas de iptables por delante de las del cortafuegos, así que ambos eran accesibles en cualquier host con IP pública en todas las versiones anteriores. **Cambio incompatible:** `uv run` ya no funciona dentro de los contenedores, y las instalaciones existentes necesitan un `sudo chown -R $(id -u):$(id -g) <data-root>/storage` una sola vez | Hecho |
| v2.1.0 | Configuración inicial sin credenciales publicadas — la puesta en marcha es ahora el mismo proceso interactivo en todos los entornos: eres tú quien elige la dirección y la contraseña del superadministrador, y las cuentas fijas `super@examplee6e3b1.com` / `admin@examplee6e3b1.com` desaparecen de la guía rápida, donde eran un superadministrador cuya contraseña se publica en este mismo repositorio. Añade las opciones `--admin-email` y `--club-name` para instalaciones automatizadas sin preguntas, un borrado de los datos del club que conserva el superadministrador y los proveedores de pago configurados, y un generador de club de demostración que muestra sus credenciales una sola vez. Las publicaciones también son más seguras: ahora se construyen todos los servicios en cada commit de `main`, y una release se detiene si falta la imagen candidata validada en lugar de reconstruirla en silencio desde la etiqueta | Hecho |
| v2.2.0 | Recuperación del superadministrador desde el servidor — el proceso de «he olvidado mi contraseña» del navegador ya no acepta superadministradores: su contraseña se restablece con `python -m app.cli.seed` en la máquina que ejecuta los contenedores. **Seguridad:** esa cuenta posee los permisos de roles y credenciales, así que permitir que un buzón de correo la restableciera equivalía a que el acceso al correo fuera acceso a toda la instancia; además el envío se descartaba en silencio en cualquier instalación sin SMTP, que son todas el primer día. Los restablecimientos hechos desde el servidor quedan registrados en el historial de auditoría, y la opción `--admin-email` para instalaciones automatizadas rechaza una dirección que pertenece a una cuenta que no es superadministradora, en lugar de cambiar la contraseña de otra persona e informar de un restablecimiento de superadministrador. Documenta la vía de recuperación y cómo nombrar a un segundo superadministrador, y corrige las dos primeras órdenes de la guía de instalación, que no podían funcionar tal y como estaban escritas | Hecho |
| v2.3.0 | Archivos subidos tras autenticación, y un inicio de sesión que no se puede adivinar indefinidamente — **Seguridad:** los archivos subidos se servían mediante un montaje de archivos estáticos sobre todo el directorio de almacenamiento, de modo que la clave de cifrado, los ficheros SEPA generados y los mandatos escaneados quedaban al alcance de cualquiera que acertara una ruta; ahora los sirve una ruta autenticada que comprueba la propiedad carpeta por carpeta. Los tokens de restablecimiento y de verificación se devolvían en la respuesta de la API, así que cualquiera podía pedir un restablecimiento para la dirección de otra persona y leer el token directamente; eso ahora solo ocurre en desarrollo. La clave de firma de ejemplo publicada en este repositorio era el valor por defecto del fichero compose, lo que permitía falsificar cookies de sesión y códigos QR del carné; ahora se rechazan los valores de ejemplo conocidos y cada instalación genera y guarda su propia clave. El renderizador de comunicaciones permitía salir de un enlace y añadir un manejador de eventos, convirtiendo el permiso de redactar comunicaciones en código ejecutándose en la sesión de un superadministrador. El inicio de sesión, el registro y los dos endpoints que envían correo a una dirección elegida por quien llama de forma anónima ahora tienen límite de frecuencia, de modo que adivinar contraseñas e inundar buzones queda acotado. Añade cabeceras de seguridad en las respuestas, deriva el atributo `Secure` de la cookie de sesión de la URL del sitio y pasa las credenciales de Resend al backend — el fichero compose nunca lo hacía, así que configurar Resend en `.env` no surtía efecto alguno. Además: un plazo de pago para la facturación recurrente, notas de versión redactadas automáticamente al publicar una etiqueta, cinco defectos de la guía de instalación encontrados recorriéndola en un servidor real, y las direcciones de ejemplo trasladadas fuera de un dominio que pertenece a otra persona. **Cambio incompatible:** una instalación que dependiera de la clave de firma de ejemplo recibirá una nueva al arrancar, lo que cierra todas las sesiones e invalida los códigos QR del carné ya emitidos | Hecho  |

### Planificado

Priorizado, aún sin versión. Cada elemento se convierte en un lanzamiento versionado cuando se publica, y el lanzamiento toma el siguiente número semántico por orden.

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

### Inicio rápido

Arranca los servicios backend (Docker) y el servidor de desarrollo frontend (local):

```bash
./scripts/dev.sh start all
```

Comprobar estado:

```bash
./scripts/dev.sh status
```

Parar todo:

```bash
./scripts/dev.sh stop all
```

### Comandos de desarrollo

| Comando | Descripción |
|---------|-------------|
| `./scripts/dev.sh start all` | Iniciar backend (Docker) + frontend (local) |
| `./scripts/dev.sh start backend` | Iniciar solo backend (API + BD en Docker) |
| `./scripts/dev.sh start frontend` | Iniciar solo frontend (Next.js local) |
| `./scripts/dev.sh stop all` | Parar todos los servicios |
| `./scripts/dev.sh restart all` | Reiniciar todos los servicios |
| `./scripts/dev.sh status` | Ver estado de todos los servicios |
| `./scripts/dev.sh logs backend` | Ver logs de la API |
| `./scripts/dev.sh logs frontend` | Ver logs del frontend (tail -f) |
| `./scripts/dev.sh logs worker` | Ver logs del worker de Celery |
| `./scripts/dev.sh logs beat` | Ver logs de Celery beat (planificador) |
| `./scripts/dev.sh seed` | Ejecutar configuración inicial de la BD (interactivo) |
| `./scripts/dev.sh seed test` | Seed con cuentas de prueba (sin preguntas) |
| `./scripts/dev.sh test` | Ejecutar tests del backend |

`start all` levanta el worker y el beat de Celery junto con la API y la base de datos. `worker` y `beat` también son destinos válidos para `start`, `stop` y `restart` si necesitas controlarlos por separado.

> **¿Añades una dependencia del backend?** Las dependencias de Python están integradas en la imagen de Docker — `pyproject.toml` no se monta como volumen — así que una dependencia nueva no estará en el contenedor en ejecución hasta que lo reconstruyas:
>
> ```bash
> docker compose -f backend/docker/docker-compose.yml build --no-cache api
> docker compose -f backend/docker/docker-compose.yml up -d --force-recreate api
> ```

### URLs de los servicios

- **Frontend**: http://localhost:3000
- **API Backend**: http://localhost:8003
- **Documentación API (Swagger)**: http://localhost:8003/api/docs
- **Base de datos**: localhost:5433
- **Adminer** (UI de BD): http://localhost:8181 (iniciar con `--profile tools`)

### Archivos de log

- Frontend: `frontend/logs/dev-server.log`
- Backend: `docker compose -f backend/docker/docker-compose.yml logs -f api`

### Primera configuración

Tras iniciar los servicios, ejecuta el comando de configuración para crear los datos iniciales:

```bash
./scripts/dev.sh seed          # Interactivo — la misma configuración que usa cualquier entorno
./scripts/dev.sh seed test     # Cuentas de prueba fijas + datos de ejemplo, para la suite e2e
```

`seed test` crea las cuentas con las que inicia sesión la suite de Cypress, además de 4
actividades de ejemplo con modalidades y precios, inscripciones de ejemplo y ~22 socios
adicionales. Las direcciones y contraseñas son un contrato con la suite de pruebas, no una
decisión de configuración, así que viven junto a ella, en
[`e2e/cypress/support/commands.ts`](e2e/cypress/support/commands.ts).

> **`seed test` se niega a ejecutarse fuera de desarrollo.** Crea contraseñas fijas y visibles
> en el repositorio, así que exige `APP_ENV=development` o `CI` y termina en caso contrario.
> Para cualquier uso real, usa la configuración interactiva — consulta
> [Configuración inicial](docs/getting-started/first-setup.md).

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
