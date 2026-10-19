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

> **Per provar Memship, no per fer-lo servir.** És la via més ràpida a una instància
> funcionant a la vostra màquina: imatges publicades, volums llencívols i una
> contrasenya de base de dades fixa. Per gestionar una organització real, seguiu la
> [Instal·lació](docs/getting-started/installation.md) — el mateix producte, configurat
> per poder-lo copiar, actualitzar i conservar.

Proveu Memship amb una sola comanda — sense necessitat de clonar el repositori:

```bash
mkdir -p "$HOME/memship-quickstart" && cd "$HOME/memship-quickstart"
curl -fsSL https://raw.githubusercontent.com/marcandreuf/memship/main/docker-compose.quickstart.yml -o docker-compose.yml
docker compose pull        # descarrega les últimes imatges publicades
PORT=8081 docker compose up -d
```

A continuació, executeu la configuració, que us fa tres preguntes:

```bash
docker compose exec -it demo-memship-api python -m app.cli.seed
```

1. **Superadministrador** — trieu l'adreça i la contrasenya. No hi ha res predefinit.
2. **Dades del club** — només s'ofereix si n'hi ha, així que en una instal·lació nova no fa res.
3. **Configuració del club** — introduïu les dades reals de la vostra organització, o genereu un club de demostració.

Trieu el club de demostració per explorar: crea un any complet de dades d'exemple
realistes — ~60 socis en tots els estats, activitats, rebuts en tots els estats repartits
pels mesos, mandats SEPA i recordatoris del tauler. També genera accessos per a un
administrador de club i dos socis, i **mostra aquestes contrasenyes una sola vegada**, així
que deseu la sortida. Es pot tornar a executar sense duplicar (idempotent).

Obriu http://localhost:8081 i inicieu sessió com a superadministrador. Canvieu `PORT=8081`
per qualsevol port que preferiu (per defecte és el 80).

Quan acabeu d'avaluar-lo, torneu a executar la mateixa comanda i responeu *sí* a la
pregunta sobre les dades del club: esborra el club de demostració conservant el vostre
superadministrador i les passarel·les de pagament que hàgiu configurat. Consulteu
[Configuració inicial](docs/getting-started/first-setup.md).

## Llançaments

Memship segueix el [versionat semàntic](https://semver.org/) i **els números de versió s'assignen en el moment del llançament, mai es reserven per endavant.** Una línia per versió; les notes completes de cadascuna són a la [pàgina de llançaments](https://github.com/marcandreuf/memship/releases). El que vindrà després és al [Full de ruta](#full-de-ruta), i [Escollir una versió](CONTRIBUTING.md#choosing-a-version) explica com es tria el número.

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
| v0.4.0 | Domiciliació SEPA — gestió de mandats, remeses, XML pain.008, forma de pagament del soci | Fet |
| v0.4.1 | Configuració de passarel·les de pagament — gestió configurable des del panell de super admin | Fet |
| v0.4.2 | Infraestructura de webhooks + Stripe Checkout — webhooks de passarel·la, estat de pagament en temps real, flux "Paga ara" del soci | Fet |
| v0.4.3 | Integració Redsys — passarel·la bancària espanyola amb 3D Secure + Bizum | Fet |
| v0.4.4 | Facturació recurrent — generació automàtica de quotes | Fet |
| v0.4.5 | Recordatoris de pagament — notificacions per correu de rebuts vençuts | Fet |
| v0.5.0 | Comunicacions simples — anuncis de l'administrador a tots els socis / grup / tipus de quota | Fet |
| v0.5.1 | Vista d'enviaments de comunicacions — seguiment de destinataris + "Vist" a l'app | Fet |
| v0.7.0 | Carnet digital de soci + registre QR — carnet en PDF, numeració automàtica de socis | Fet |
| v0.7.1 | Millores del carnet — vista de carnet per a l'admin, foto de perfil del soci, redisseny del perfil | Fet |
| v1.0.0 | Estabilització i llançament — exportacions CSV, tauler financer, notes i recordatoris, resum anual, dades demo, polit de docs | Fet |
| v1.0.1 | Pedaç — corregeix el registre de tasques programades de facturació/recordatoris a Celery; protecció de CI contra la sobreescriptura d'etiquetes d'imatge | Fet |
| v1.1.0 | Camps de perfil personalitzats — dades de soci configurables per l'organització (text, número, data, selecció, …) amb validació per camp i visibilitat/edició per camp | Fet |
| v1.1.1 | Pedaç — reorganització de la navegació de configuració: ajustos de pagaments i de socis agrupats a les pestanyes Pagaments i Socis | Fet |
| v1.2.2 | SSO i configuració de correu — alta pública amb verificació per correu i aprovació per la junta, inici de sessió amb Google / Apple, i configuració de Resend / Google SMTP des d'una pestanya d'Integracions | Fet |
| v1.3.0 | Reserves simples — reserves de socis en espais compartits mitjançant un calendari setmanal, amb aforament per franja i llista d'espera FIFO | Fet |
| v1.4.0 | Rols i permisos flexibles — assignació multi-rol i comprovacions granulars per permís en lloc dels quatre rols fixos. També repara els stacks de desplegament que no executaven cap worker de Celery ni muntaven volum al servei d'API | Fet |
| v2.0.0 | Revisió de l'autoallotjament — muntatges bind visibles a l'amfitrió sota un únic `MEMSHIP_DATA_ROOT`, contenidors del backend amb l'uid de l'operador i un `install.sh` d'una sola ordre. **Seguretat:** PostgreSQL i l'API deixen de publicar-se a internet. **Canvi incompatible:** `uv run` ja no funciona als contenidors. | Fet |
| v2.1.0 | Configuració inicial sense credencials publicades — el mateix procés interactiu a tots els entorns, sense comptes amb contrasenyes publicades en aquest repositori, més opcions desateses per a instal·lacions automatitzades | Fet |
| v2.2.0 | Recuperació del superadministrador des del servidor — la seva contrasenya es restableix amb `python -m app.cli.seed` a la màquina, no per correu. **Seguretat:** l'accés a la bústia equivalia a controlar tota la instància | Fet |
| v2.3.0 | Fitxers pujats després d'autenticació, i un inici de sessió que no es pot endevinar indefinidament — l'emmagatzematge es servia com a fitxers estàtics, els testimonis de restabliment tornaven en la resposta de l'API i la clau de signatura publicada era el valor per defecte. **Canvi incompatible:** qui la feia servir rep una de nova i es tanquen totes les sessions. | Fet |
| v2.3.1 | Rutes de diners que fallaven en silenci — un fitxer SEPA ja no descarta rebuts el mandat dels quals es va cancel·lar, un webhook de pagament ja no registra un import diferent com a pagament complet, i una activitat ja no supera el seu aforament si dues persones s'inscriuen alhora. | Fet |
| v2.4.0 | L'inici de sessió exigeix una adreça de correu confirmada, i la numeració de rebuts és correlativa i sense buits. **Canvi incompatible:** un compte que mai va confirmar la seva adreça ja no pot entrar. **Migració:** la numeració passa a un comptador per any, inicialitzat amb els números ja emesos. | Fet |
| v2.5.0 | Tot el correu sortint en una única plantilla amb la identitat de l'organització — nom, logotip i color es llegeixen de la configuració, cada missatge porta una alternativa en text pla al costat de l'HTML, i l'enviament de rebuts i el resum de facturació passen a ser plantilles. | Fet |
| v2.6.0 | Un super administrador decideix quins correus envia el sistema — una pantalla de Configuració amb un interruptor per plantilla i els 17 punts d'enviament passant per una única porta. **Canvi incompatible:** el correu opcional queda desactivat, així que una instal·lació existent es queda en silenci en actualitzar. | Fet |
| v2.7.0 | Sessions que es desplacen en lloc de caducar a mitja tasca — una sessió activa es renova a la meitat de la seva finestra i, en esgotar-se, ho diu i et torna a l'inici de sessió. **Autoallotjament:** una versió es desplega en un VPS sense git ni còpia del codi, des d'un tarball de la publicació. | Fet |
| v2.7.1 | Una primera instal·lació deixa un `POST-INSTALL.md` al servidor amb el que l'instal·lador no pot fer per tu — copiar `.env` fora de l'amfitrió, crear l'organització i el super administrador, programar còpies i configurar el correu — amb totes les rutes emplenades. L'avís de la v2.7.0 era correcte i ningú el va llegir. | Fet |
| v2.8.0 | Una quota que el soci compra, i pot perdre — el pla es compra des del portal del soci a un preu prorratejat amb impostos inclosos, es concedeix quan arriba el diner per qualsevol via, i es retira 21 dies després que venci una quota impagada, desant el nivell perdut per restituir-lo en pagar. | Fet |
| v2.9.0 | La pantalla on el soci compra el seu pla — la v2.8.0 sabia cobrar però no deixava demanar-ho. **El meu pla** mostra el pla contractat i els disponibles, amb el primer càrrec prorratejat abans de confirmar res. Comprar emet un rebut; el pla s'activa en cobrar-lo. | Fet |
| v2.9.1 | Una primera instal·lació capaç de seguir les seves pròpies instruccions — cada correcció va sortir d'executar la guia de dalt a baix en un servidor nou. `vps-bootstrap.sh` s'interrompia pel bloqueig d'apt en arrencar Ubuntu i deixava l'amfitrió sense tallafocs ni fail2ban. | Fet |
| v2.10.0 | Tretze correccions a les rutes que gestionen diners, dades personals i càrrega; cap pantalla nova. Els testimonis de restabliment es desen com a resum, l'IBAN complet deixa de retornar-se al costat de l'emmascarat i les exportacions CSV neutralitzen les cel·les amb fórmula. **Canvi incompatible:** els enllaços de restabliment pendents deixen de funcionar en actualitzar. | Fet |
| v2.11.0 | El personal no és soci del club — un super administrador o un administrador gestiona la instància sense pertànyer-hi, en lloc de portar número de soci i comptar en cada llistat, exportació i facturació. **Migració irreversible:** els comptes de personal perden la seva fitxa de soci. | Fet |
| v2.12.0 | Accés, correu, pagaments i la mateixa actualització — les rutes amb què ensopega un club les primeres setmanes. Les adreces es desen i es comparen en minúscules, i `upgrade.sh` pregunta a l'API nova per les dades abans de substituir la pila. **Migració:** les adreces existents passen a minúscules. | Fet |
| v2.13.0 | La versió d'auditoria — disset defectes trobats llegint el codi contra la seva pròpia documentació, cap funció nova. Restablir la contrasenya tanca totes les sessions que va obrir, el límit d'intents s'aplica a qui truca en lloc de blocar tots els socis, i la facturació data en la zona horària del club. | Fet |
| v2.14.0 | La versió de caça d'errors — setze defectes reportats i una compilació que podia publicar una imatge incapaç d'arrencar, sense funcions noves. Les compilacions instal·len `uv.lock` amb `--locked` i cada imatge candidata s'arrenca abans de publicar-se; els preus d'activitat deixen de retornar l'IVA a zero. | Fet |
| v2.15.0 | Funcions assolibles i la ruta d'actualització — tres funcions publicades que no es podien fer servir, i les comprovacions que ho haurien detectat. | Fet |
| v2.16.0 | La versió de les rutes dels diners — el circuit de cobrament SEPA que un club executa cada mes, repassat a mà en lloc de llegit. | Fet |
| v2.17.0 | La versió de revisió — onze defectes trobats llegint l'arbre i treballant les pantalles, cap reportat per ningú, i la canonada de compilació que publicava imatges descompassades. | Fet |
| v2.18.0 | La versió de validació SEPA — setze defectes trobats conduint el cobrament en una instància desplegada. Una devolució contra un rebut ja cobrat deixa de constar com a atesa, i un fitxer bancari generat no se sobreescriu. **Canvi incompatible:** `import-returns` informa per grups. **Migració:** els mandats actius duplicats es cancel·len, es conserva el més recent. | Fet |
| v2.19.0 | La versió dels proveïdors de pagament — Bizum es pot oferir per separat de la targeta, un secret desat ja no s'esborra amb un desament en blanc, i una remesa enviada anomena el rebut que el banc va retornar. **Canvi incompatible:** Bizum ve desactivat. **Migració:** `remittance_receipts` registra quins rebuts va portar cada remesa. | Fet |

## Full de ruta

Prioritzat, encara sense versió. Cada element esdevé un llançament versionat quan es publica, i el llançament pren el següent número semàntic per ordre. Cada element té una incidència amb el seu resum i les idees actuals — consulta les [incidències amb l'etiqueta `roadmap`](https://github.com/marcandreuf/memship/labels/roadmap).

- **Invitacions d'usuaris** — convidar un nou superadministrador, administrador del club o soci indicant la seva adreça de correu i el seu rol; la persona tria el seu propi nom i contrasenya. S'envien per correu quan el correu està configurat, i com a enllaç copiable quan no ho està, de manera que una instal·lació acabada de crear pugui afegir un segon administrador sense accés per consola
- **Còpies de seguretat** — descarregar una còpia completa des de l'àrea d'administració, amb la base de dades i els fitxers pujats, i una restauració documentada i provada
- **Convocatòries** — convocatòries formals d'Assemblea General amb confirmació del soci mitjançant token
- **Biblioteca de documents** — estatuts, actes, formularis amb visibilitat per grup
- **Calendari d'esdeveniments + confirmació d'assistència** — vista de calendari i seguiment de participació
- **Integracions** — connectar memship amb les eines que el club ja utilitza, en comptes de demanar-li que les abandoni. Primer missatgeria instantània (WhatsApp, Telegram, Signal, Instagram), que és on la majoria de clubs es comuniquen realment; després subscripcions de calendari, exportacions a comptabilitat i facturació electrònica, enviament de llicències a federacions esportives i webhooks sortints com a via genèrica per a la resta. Cada connector té el seu propi cost i les seves pròpies limitacions, i es publica per separat

Les variacions complexes es construeixen sota demanda, quan una implementació real les necessita: GoCardless e-mandats, PayPal, flux d'Stripe Invoice, accions massives en rebuts, generador d'informes personalitzats, enquestes, facturació familiar, pagaments i reserves recurrents, lloguer d'equipament, votació i adjunts en convocatòries, i variants més profundes de les funcions anteriors.

**Ajornat — les extensions com a sistema de mòduls/connectors.** Els complements opcionals com àlbums de fotos, fòrum, llibre de visites, directori d'enllaços, inventari/préstecs i ginys del portal necessiten un sistema de mòduls dissenyat dins de l'arquitectura, no afegit al damunt. Això espera una futura revisió d'aquesta arquitectura en lloc de publicar-se com una funció.

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

**Domiciliació SEPA** (disponible — v0.4.0)
- Gestió de mandats SEPA (crear, PDF, pujar signat, cancel·lar)
- Processament de remeses amb XML SEPA (pain.008.001.02)
- Importació de devolucions bancàries i seguiment d'estat
- Pàgina de forma de pagament per a socis

**Passarel·les de pagament** (previst — v0.4.x)
- Gestió configurable de passarel·les de pagament (configuració del super admin)
- Integració Stripe — pagaments amb targeta basats en factura amb webhooks
- GoCardless — e-mandats SEPA gestionats amb flux allotjat
- Patró d'adaptador extensible per a proveïdors regionals (MercadoPago, Razorpay, etc.)

**Comunicacions** (previst)
- Campanyes de correu electrònic amb plantilles i segmentació d'audiència
- Missatgeria directa entre administradors i socis
- Plantilles de correu multiidioma

**Reserves i espais** (disponible)
- Espais reservables amb horari d'obertura diari i franges amb data definides per la junta
- Regles de repetició que materialitzen una sèrie de dates (dies de la setmana triats, cada N setmanes) i franges de dia complet
- Aforament per franja amb llista d'espera FIFO i promoció automàtica en cancel·lar
- Calendari setmanal del soci amb ocupació en viu i autocancel·lació fins a un termini configurable
- Correus de confirmació, llista d'espera, promoció i cancel·lació per la junta

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
| Tasques en segon pla | Celery worker + beat, amb Redis com a broker |
| Proxy invers | Caddy — obté i renova els certificats TLS pel seu compte |
| Contenidors | Docker + Docker Compose |
| CI | GitHub Actions |
| Registre | GitHub Container Registry (ghcr.io) |

## Desenvolupament

El backend en Docker i el frontend en local amb recàrrega en calent de pnpm, governats per
`scripts/dev.sh`:

```bash
./scripts/dev.sh start all      # backend (Docker) + frontend (local)
./scripts/dev.sh status
./scripts/dev.sh test           # tests del backend
```

La instal·lació completa, totes les ordres, les URL dels serveis, la càrrega de dades inicial i les
suites de tests són a
**[Entorn de desenvolupament local](docs/development/local-environment.md)** _(en anglès)_.

Consulta [CONTRIBUTING](CONTRIBUTING.md) per a branques, versionat i com es publica una versió.

## Instal·lació (Docker)

L'autoallotjament en producció viu a la documentació, perquè només hi hagi una còpia per mantenir correcta:

- **[Instal·lació](docs/getting-started/installation.md)** — `vps-bootstrap.sh` en un servidor nou i
  després `install.sh`, que genera secrets reals, fixa una versió i posa les teves dades en un únic
  directori amb còpia de seguretat
- **[Configuració inicial](docs/getting-started/first-setup.md)** — crear el super administrador i
  l'organització
- **[Referència de configuració](docs/self-hosting/configuration.md)** — totes les variables
  d'entorn
- **[Còpies de seguretat i restauració](docs/self-hosting/backups-and-restore.md)** — configura-ho
  abans de posar-ho en producció
- **[Actualitzacions](docs/self-hosting/upgrading.md)** — passar a una versió nova
- **[Resolució de problemes](docs/self-hosting/troubleshooting.md)** — quan alguna cosa no arrenca

L'[Inici ràpid](#inici-ràpid-docker) de dalt és només per avaluar: inclou una clau de signatura
publicada en aquest repositori i guarda les dades en volums d'un sol ús.

## Contribucions

Les contribucions de codi són benvingudes. La base del projecte — infraestructura, CI/CD i l'arquitectura central — ja està consolidada, i [CONTRIBUTING](CONTRIBUTING.md) explica el model de branques, les convencions de commits i pull requests, el versionatge i com es publica una release _(en anglès)_. En resum: creeu una branca `feature/*` de vida curta a partir de `main` i obriu un pull request cap a `main`. Per preparar l'entorn, comenceu per [Local development environment](docs/development/local-environment.md) _(en anglès)_.

No escriviu codi? [Obriu una issue](https://github.com/marcandreuf/memship/issues) — els informes d'errors, les propostes de funcionalitats, les preguntes i explicar com faríeu servir Memship són igual de benvinguts, i per als dos primers hi ha plantilles.

Les vulnerabilitats de seguretat es comuniquen per un canal privat, no en una issue pública — vegeu [SECURITY](SECURITY.md). Qui participa en el projecte queda cobert pel [Codi de conducta](CODE_OF_CONDUCT.md).

[Accessibilitat](ACCESSIBILITY.md) explica a què aspira el projecte, què s'espera que comprovi qui hi contribueix i com informar d'una barrera — inclòs què s'ha provat de debò i què no _(en anglès)_. Si us topeu amb una, allà hi ha la via per informar, amb una adreça de correu per quan GitHub sigui precisament l'obstacle.

## Llicència

Memship està llicenciat sota la [Elastic License 2.0 (ELv2)](LICENSE). Podeu utilitzar, modificar i autohospedar Memship lliurement. La llicència restringeix oferir-lo com a servei gestionat a tercers.
