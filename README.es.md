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

Prueba Memship con un solo comando, sin necesidad de clonar el repositorio:

```bash
curl -fsSL https://raw.githubusercontent.com/marcandreuf/memship/main/docker-compose.quickstart.yml -o docker-compose.yml && PORT=8081 docker compose up -d
```

A continuación, ejecuta la configuración inicial:

**Opción A: Demo rápida con cuentas de prueba (sin preguntas)**

```bash
docker compose exec demo-memship-api uv run python -m app.cli.seed --test
```

Esto crea cuentas de prueba preconfiguradas, socios de ejemplo, actividades e inscripciones:

| Rol | Email | Contraseña |
|-----|-------|------------|
| Super Admin | super@test.com | TestSuper1! |
| Admin de Org | admin@test.com | TestAdmin1! |
| Socio | member@test.com | TestMember1! |

**Opción B: Configuración personalizada (interactiva)**

```bash
docker compose exec demo-memship-api uv run python -m app.cli.seed
```

Te pedirá que crees tus propias cuentas de super admin y admin de organización. No se generan datos de ejemplo.

Abre http://localhost:8081 e inicia sesión con tus credenciales. Cambia `PORT=8081` por el puerto que prefieras (por defecto es el 80).

## Hoja de ruta

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
| v0.4.1 | Configuración de pasarelas de pago — gestión configurable desde el panel de super admin | — |
| v0.4.2 | Integración Stripe — pagos con tarjeta, webhooks, sincronización de clientes | — |
| v0.4.3 | GoCardless e-mandatos — SEPA gestionado con flujo alojado | — |
| v0.5.0 | Sistema de comunicaciones | — |
| v0.6.0 | Reservas y documentos | — |
| v0.7.0 | Informes y analítica | — |
| v0.8.0 | Carnet digital de socio y registro QR | — |
| v1.0.0 | Estabilización y lanzamiento | — |

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

**Reservas y espacios** (previsto)
- Sistema de reserva de espacios e instalaciones
- Vistas de calendario con disponibilidad
- Reglas de reserva y prevención de conflictos

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
| `./scripts/dev.sh seed` | Ejecutar configuración inicial de la BD (interactivo) |
| `./scripts/dev.sh seed test` | Seed con cuentas de prueba (sin preguntas) |
| `./scripts/dev.sh test` | Ejecutar tests del backend |

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

Tras iniciar los servicios, ejecuta el comando seed para crear los datos iniciales:

```bash
./scripts/dev.sh seed          # Interactivo — te pide las credenciales de admin
./scripts/dev.sh seed test     # Rápido — crea cuentas de prueba (sin preguntas)
```

La opción `seed test` crea cuentas de prueba y datos de ejemplo para desarrollo:

| Rol | Email | Contraseña |
|-----|-------|------------|
| Super Admin | super@test.com | TestSuper1! |
| Admin de Org | admin@test.com | TestAdmin1! |
| Socio | member@test.com | TestMember1! |

Además, 5 cuentas de socio adicionales (maria@test.com, joan@test.com, etc. / TestMember1!), 4 actividades de ejemplo con modalidades y precios, e inscripciones de ejemplo.

> **Aviso:** No utilices las cuentas de prueba en producción. Usa `./scripts/dev.sh seed` (interactivo) para despliegues reales.

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
docker compose exec -it api uv run python -m app.cli.seed

# Abre http://localhost
```

### Opción B: Compilar desde el código fuente

Compila las imágenes Docker localmente a partir del código fuente del repositorio.

```bash
git clone https://github.com/marcandreuf/memship.git
cd memship
cp .env.example .env
docker compose up -d --build
docker compose exec -it api uv run python -m app.cli.seed
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
