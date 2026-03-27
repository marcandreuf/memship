# Memship

🌐 [English](README.md) | [Español](README.es.md) | **Català**

> **Aquest projecte està en desenvolupament actiu, encara no està preparat per a producció, i està obert a [sol·licituds de funcionalitats](https://github.com/marcandreuf/memship/issues).**

**Gestió de socis per a tothom.**

Memship és un programari de codi obert i autohospedable per a la gestió de socis, dissenyat per a associacions culturals, clubs esportius, entitats esportives, col·legis professionals i qualsevol organització basada en membres. Desplegeu-lo a la vostra pròpia infraestructura, manteniu el control de les vostres dades i gestioneu la vostra comunitat amb eines modernes. Amb Memship podeu portar el control de socis, la gestió de quotes, la facturació de socis, les inscripcions a activitats i molt més — tot des d'una única plataforma autohospedable.

---

## Què estem construint

La majoria d'eines de gestió de socis són plataformes SaaS cares o programari obsolet. Memship vol canviar això — una solució moderna i completa que vosaltres controleu. Sense dependència de proveïdors, sense preus per soci, sense que les vostres dades surtin dels vostres servidors.

- **Autohospedable** — funciona a qualsevol servidor amb Docker
- **Monoentitat** — una base de dades per organització, aïllament complet de dades
- **Multiidioma** — castellà, català i anglès des del primer dia. Extensible a qualsevol idioma mitjançant contribucions de la comunitat
- **Preparat per al RGPD** — plantilles de termes legals i gestió del consentiment integrades

## Inici ràpid (Docker)

Proveu Memship amb una sola comanda — sense necessitat de clonar el repositori:

```bash
curl -fsSL https://raw.githubusercontent.com/marcandreuf/memship/main/docker-compose.quickstart.yml -o docker-compose.yml && PORT=8081 docker compose up -d
```

A continuació, executeu la configuració inicial:

**Opció A: Demostració ràpida amb comptes de prova (sense preguntes)**

```bash
docker compose exec demo-memship-api uv run python -m app.cli.seed --test
```

Això crea comptes de prova preconfigurats, socis d'exemple, activitats i inscripcions:

| Rol | Correu electrònic | Contrasenya |
|-----|-------------------|-------------|
| Superadministrador | super@test.com | TestSuper1! |
| Administrador | admin@test.com | TestAdmin1! |
| Soci | member@test.com | TestMember1! |

**Opció B: Configuració personalitzada (interactiva)**

```bash
docker compose exec demo-memship-api uv run python -m app.cli.seed
```

Us demanarà que creeu els vostres propis comptes de superadministrador i administrador. No es generen dades d'exemple.

Obriu http://localhost:8081 i inicieu sessió amb les vostres credencials. Canvieu `PORT=8081` per qualsevol port que preferiu (per defecte és el 80).

## Full de ruta

| Versió | Fita | Estat |
|--------|------|-------|
| v0.1.0 | Gestió de socis MVP — autenticació, RBAC, CRUD de socis, tipus de membresies, i18n, Docker, CI | Fet |
| v0.1.1 | Enviament de correus (SMTP) — correus de benvinguda, correus de restabliment de contrasenya | Fet |
| v0.1.2 | Grups, suport tutor/menor, rol restringit (esquema) | Fet |
| v0.1.3 | Proxy invers Caddy, scripts de còpia de seguretat/restauració, millores d'autohospedatge | Fet |
| v0.1.4 | Gestió de la configuració de l'organització (API + frontend) | Fet |
| v0.1.5 | CRUD d'activitats — models, modalitats, preus, frontend d'administració | Fet |
| v0.1.6 | Patró d'entitat fort — llista/detall/pestanyes unificats per a totes les entitats | Fet |
| v0.2.0 | Gestió d'activitats — inscripcions, elegibilitat, llista d'espera, descomptes, consentiments, adjunts | Fet |
| v0.2.1 | Millora d'UX — barra lateral Shadcn, mode fosc, colors de marca, taules compactes, inici ràpid | Fet |
| v0.2.2 | Base de proves E2E (Cypress) — autenticació, socis, activitats, inscripcions | Fet |
| v0.2.3 | Gestió d'errors i validació — notificacions toast, gestor global d'errors, validació d'esquemes, StrEnum, 76 proves de validació, 16 proves E2E | Fet |
| v0.2.4 | Correccions — mode fosc a la barra lateral, visualització d'errors de formulari, guards de ruta, visibilitat de socis cancel·lats, eliminació de soci suprimida | Fet |
| v0.2.5 | UX d'activitats — redisseny de targeta d'activitat, imatge de portada, insígnies d'estat d'inscripció, miniatures a la llista, graella "Les meves activitats", volum Docker | Fet |
| v0.2.6 | Correccions i proves — diàlegs de confirmació Shadcn (substitueixen 13 alertes del navegador), correcció de codis de descompte, comprovació de termini d'autocancelació, reinscripció després de cancel·lació, 21 noves proves d'API, 9 noves proves E2E d'elegibilitat | Fet |
| v0.2.7 | Millores d'activitats — esquelets de càrrega, estat d'URL amb nuqs | Fet |
| v0.2.9 | Prerequisits de pagament — adreça i dades bancàries de l'organització, pujada de logotip, pestanya d'informació de contacte, IBAN del soci, Celery/Redis, notificacions per correu (Jinja2 + SMTP/Resend) | Fet |
| v0.3.0 | Pagaments i facturació bàsics — rebuts, generació de PDF, IVA, generació de quotes, historial de pagaments del soci | Fet |
| v0.3.1 | Correccions — proves fallides i README traduïts | Fet |
| v0.3.2 | Correccions — arranjament del pipeline de build del frontend | Fet |
| v0.3.3 | Millores de CI — execució de proves més ràpida | Fet |
| v0.3.4 | Correccions — neteja de warnings i optimització de proves d'integració | Fet |
| v0.3.5 | Correccions — proves d'integració fallides | Fet |
| v0.3.6 | Optimització de CI — setup-uv v7, cache de hash de contrasenyes, workers de proves paral·lels, hooks de versionat automàtic | Fet |
| v0.4.0 | Processament de pagaments (SEPA + Stripe) | — |
| v0.5.0 | Sistema de comunicació | — |
| v0.6.0 | Reserves i documents | — |
| v0.7.0 | Informes i analítiques | — |
| v0.8.0 | Carnet de soci digital i registre QR | — |
| v1.0.0 | Estabilització i llançament | — |

---

## Funcionalitats

**Gestió de socis** (disponible ara)
- Cicle de vida complet del soci: inscripció, alta, canvis d'estat, baixa
- Tipus de membresia amb grups, quotes i restriccions d'edat
- Suport per a tutors i menors d'edat
- Control d'accés per rols: superadministrador, administrador de l'organització, soci
- Configuració de l'organització amb marca (color, pujada de logotip), adreça, dades bancàries (IBAN/BIC), sèries de facturació
- Gestió d'informació de contacte del soci (telèfon, correu electrònic, amb tipus de contacte)
- Dades bancàries del soci (IBAN/BIC) per a domiciliació bancària SEPA
- Interfície multiidioma (ES, CA, EN) amb selector d'idioma al perfil
- Tauler d'administració amb gràfics d'estat (recharts)
- Patró d'entitat unificat: llista → detall → pestanyes per a totes les entitats
- Notificacions per correu electrònic (confirmació d'inscripció, cancel·lació, promoció de llista d'espera) via Celery/Redis
- Doble transport de correu: SMTP (autohospedable) o API de Resend (gestionat)
- Plantilles de correu Jinja2 amb suport d'idioma (ES/CA/EN)

**Activitats i esdeveniments** (disponible ara)
- Creació d'activitats amb gestió del cicle de vida (esborrany → publicada → arxivada)
- Imatge de portada per activitat (pujada per l'administrador, miniatures visibles pels socis)
- Modalitats (variants amb capacitat, preus i terminis independents)
- Tarifes amb validesa temporal (preus d'inscripció anticipada)
- Inscripció en línia amb comprovacions d'elegibilitat (tipus de membresia, edat, estat)
- Gestió de capacitat amb llista d'espera automàtica i promoció
- Autocancelació amb terminis configurables
- Codis de descompte (percentatge/import fix, usos màxims, dates de validesa)
- Consentiments legals per activitat (obligatoris/opcionals)
- Adjunts requerits per activitat amb pujada de fitxers
- Portal del soci: exploració d'activitats amb miniatures, insígnies d'estat d'inscripció, graella "Les meves activitats"
- Portal d'administració: gestió d'inscripcions amb canvis d'estat

**Pagaments i facturació** (disponible ara)
- Gestió de rebuts amb cicle de vida de 7 estats (nou → emès → pagat / retornat / cancel·lat / vençut)
- Generació de rebuts en PDF (WeasyPrint) amb capçalera de l'organització, dades del soci, desglossament d'IVA — 3 idiomes (ES/CA/EN)
- Generació massiva de quotes de membresia a partir dels tipus de membresia
- Rebut automàtic en inscriure's a una activitat (emès en confirmar, cancel·lat en cancel·lar)
- Creació manual de rebuts des de la pàgina de detall del soci
- Càlcul d'IVA amb tipus configurable per defecte per organització
- Numeració de factures amb prefix configurable i reinici anual opcional (p. ex., FAC-2026-0001)
- Format de moneda europeu (1.234,56 €) segons l'idioma de l'organització
- Autoservei del soci: pàgina "Els meus rebuts" amb descàrrega de PDF
- Tauler d'administració: gràfic d'estat de rebuts + targetes d'imports pendents/pagats/vençuts
- Notificació per correu amb el rebut en PDF adjunt (via Celery + Resend o SMTP)
- Configuració → pestanya Pagaments per a facturació i dades bancàries

**Processament de pagaments** (previst — v0.4.0)
- Processament per lots de domiciliació bancària SEPA
- Pagaments en línia amb Stripe
- Flux de devolucions
- Recordatoris de pagament

**Comunicacions** (previst)
- Campanyes de correu electrònic amb plantilles i segmentació d'audiència
- Missatgeria directa entre administradors i socis
- Plantilles de correu multiidioma

**Reserves i espais** (previst)
- Sistema de reserva d'espais i recursos
- Vistes de calendari amb disponibilitat
- Regles de reserva i prevenció de conflictes

**Informes i taulers** (previst)
- Estadístiques i tendències de socis
- Resums financers
- Exportació de dades (CSV, PDF)

## Tecnologies

| Capa | Tecnologia |
|------|-----------|
| Backend | Python 3.12+ / FastAPI / SQLAlchemy / Alembic |
| Frontend | Next.js / React / Tailwind CSS / Shadcn/ui |
| Base de dades | PostgreSQL 15 |
| Contenidors | Docker + Docker Compose |
| CI | GitHub Actions |
| Registre | GitHub Container Registry (ghcr.io) |

## Desenvolupament

### Inici ràpid

Inicieu els serveis del backend (Docker) i el servidor de desenvolupament del frontend (local):

```bash
./scripts/dev.sh start all
```

Comproveu l'estat:

```bash
./scripts/dev.sh status
```

Atureu-ho tot:

```bash
./scripts/dev.sh stop all
```

### Comandes de desenvolupament

| Comanda | Descripció |
|---------|-----------|
| `./scripts/dev.sh start all` | Iniciar backend (Docker) + frontend (local) |
| `./scripts/dev.sh start backend` | Iniciar només el backend (API + BD en Docker) |
| `./scripts/dev.sh start frontend` | Iniciar només el frontend (Next.js local) |
| `./scripts/dev.sh stop all` | Aturar tots els serveis |
| `./scripts/dev.sh restart all` | Reiniciar tots els serveis |
| `./scripts/dev.sh status` | Mostrar l'estat de tots els serveis |
| `./scripts/dev.sh logs backend` | Veure els registres de l'API |
| `./scripts/dev.sh logs frontend` | Veure els registres del frontend (tail -f) |
| `./scripts/dev.sh seed` | Executar la configuració inicial de la base de dades (interactiva) |
| `./scripts/dev.sh seed test` | Inicialitzar amb comptes de prova (sense preguntes) |
| `./scripts/dev.sh test` | Executar les proves del backend |

### URLs dels serveis

- **Frontend**: http://localhost:3000
- **API del backend**: http://localhost:8003
- **Documentació de l'API (Swagger)**: http://localhost:8003/api/docs
- **Base de dades**: localhost:5433
- **Adminer** (UI de BD): http://localhost:8181 (iniciar amb `--profile tools`)

### Fitxers de registre

- Frontend: `frontend/logs/dev-server.log`
- Backend: `docker compose -f backend/docker/docker-compose.yml logs -f api`

### Primera configuració

Després d'iniciar els serveis, executeu la comanda de seed per crear les dades inicials:

```bash
./scripts/dev.sh seed          # Interactiu — demana les credencials d'administrador
./scripts/dev.sh seed test     # Ràpid — crea comptes de prova (sense preguntes)
```

L'opció `seed test` crea comptes de prova i dades d'exemple per al desenvolupament:

| Rol | Correu electrònic | Contrasenya |
|-----|-------------------|-------------|
| Superadministrador | super@test.com | TestSuper1! |
| Administrador | admin@test.com | TestAdmin1! |
| Soci | member@test.com | TestMember1! |

A més, 5 comptes de soci addicionals (maria@test.com, joan@test.com, etc. / TestMember1!), 4 activitats d'exemple amb modalitats i preus, i inscripcions d'exemple.

> **Avís:** No utilitzeu els comptes de prova en producció. Utilitzeu `./scripts/dev.sh seed` (interactiu) per a desplegaments reals.

## Instal·lació (Docker)

### Requisits previs

- Docker i Docker Compose instal·lats
- Git (per clonar el repositori)

### Opció A: Imatges precompilades (recomanat)

Utilitza imatges publicades al [GitHub Container Registry](https://github.com/marcandreuf/memship/pkgs/container/memship-backend).

```bash
git clone https://github.com/marcandreuf/memship.git
cd memship

# Configuració
cp .env.example .env
# Editeu .env — com a mínim canvieu SECRET_KEY i DB_PASSWORD
# Definiu la versió de la imatge:
#   IMAGE_TAG=0.1.3

# Descarregueu i inicieu tots els serveis (Caddy + API + Frontend + PostgreSQL)
docker compose pull
docker compose up -d

# Executeu la configuració inicial (crea els comptes d'administrador)
docker compose exec -it api uv run python -m app.cli.seed

# Obriu http://localhost
```

### Opció B: Compilar des del codi font

Compila les imatges Docker localment a partir del codi font del repositori.

```bash
git clone https://github.com/marcandreuf/memship.git
cd memship
cp .env.example .env
docker compose up -d --build
docker compose exec -it api uv run python -m app.cli.seed
```

### Serveis

| Servei | URL | Descripció |
|--------|-----|-----------|
| Frontend | http://localhost | Portal del soci (via Caddy) |
| API | http://localhost/api/v1/health | API del backend (via Caddy) |
| API directa | http://localhost:8003 | API del backend (directa) |
| Documentació de l'API | http://localhost:8003/api/docs | Swagger UI (només en mode dev) |

### Còpies de seguretat

```bash
# Crear una còpia de seguretat
./scripts/db-backup.sh

# Llistar i restaurar des d'una còpia de seguretat (simulació per defecte)
./scripts/db-restore.sh

# Restaurar amb confirmació
./scripts/db-restore.sh --confirm
```

Les còpies de seguretat s'emmagatzemen al directori `backups/`. Les còpies antigues s'eliminen automàticament al cap de 10 dies.

## Contribucions

Memship està en les seves fases inicials. Les contribucions de codi seran benvingudes un cop la base del projecte estigui consolidada — estigueu atents.

Mentrestant, no dubteu a [obrir una issue](https://github.com/marcandreuf/memship/issues) per compartir idees, suggerir funcionalitats o fer preguntes. Qualsevol retroalimentació és benvinguda.

## Llicència

Memship està llicenciat sota la [Elastic License 2.0 (ELv2)](LICENSE). Podeu utilitzar, modificar i autohospedar Memship lliurement. La llicència restringeix oferir-lo com a servei gestionat a tercers.
