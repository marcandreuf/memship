<!-- source: en/getting-started/what-you-need.md -->
<!-- source-hash: b00dd8346157 -->

# Què necessites per executar Memship

Aquesta pàgina és per decidir **si** executaràs Memship. Explica què necessita la plataforma, què
costa i què no necessita. Qui tiri endavant després llegeix
[Installation](../../en/getting-started/installation.md) _(en anglès)_, escrita per a qui es posa
davant del terminal.

> **En anglès:** [What you need to run Memship](../../en/getting-started/what-you-need.md).

Tot el que segueix s'ha **mesurat** sobre la versió 2.19.0, no s'ha estimat. Quan una xifra és un
criteri i no una mesura, s'indica.

## La resposta curta

| | |
|---|---|
| **Un servidor** | 2 vCPU, 4 GB de RAM, 40 GB de SSD. Linux amb Docker. Un Memship per màquina |
| **Un nom de domini** | Amb un registre A que apunti al servidor. L'HTTPS es resol sol |
| **Una manera d'enviar correu** | Resend, Gmail o qualsevol servidor SMTP. Això no es pot saltar |
| **El que costa** | **De 8 a 12 € al mes**, IVA inclòs, per tot l'anterior |
| **Qui l'instal·la** | Tu, l'informàtic que ja tinguis, o el mantenidor com a servei de pagament |

Sense Kubernetes, sense base de dades gestionada, sense emmagatzematge d'objectes, sense llicència
per soci.

## El servidor

Memship executa set contenidors: un proxy invers Caddy, l'API, un worker de Celery, un
planificador Celery beat, el frontend de Next.js, Redis i PostgreSQL.

**Memòria mesurada.** Versió 2.19.0, després de sembrar un club de 60 socis, 28 activitats, 190
inscripcions, 80 rebuts i 25 mandats SEPA, i de recórrer les pantalles de socis, activitats,
rebuts, remeses i mandats i el resum anual:

| Contenidor | Memòria resident |
|---|---|
| Frontend (Next.js) | 236 MiB |
| Worker de Celery | 149 MiB |
| API (FastAPI) | 131 MiB |
| Celery beat | 107 MiB |
| PostgreSQL | 42 MiB |
| Caddy | 12 MiB |
| Redis | 5 MiB |
| **Total** | **682 MiB** |

Així doncs, tota la plataforma funciona amb uns **0,7 GB**, i això val per a qualsevol màquina: el
worker de Celery engega dos processos, tingui la màquina les CPU que tingui. Cada procés de més
costa uns 50 MiB, si puges `CELERY_CONCURRENCY` (mira
[Referència de configuració](../self-hosting/configuration.md#tasques-en-segon-pla-celery--redis)).

**Amb 2 GB de RAM funciona; la recomanació són 4 GB.** La diferència no la demana l'aplicació. La
demanen PostgreSQL, per tenir memòria de sobres amb què fer memòria cau, i les actualitzacions, que
mantenen una estona les imatges noves al costat de les que estan en marxa. A més, 4 GB és el que
inclou el pla d'entrada de tots els proveïdors de més avall, així que demanar-ne menys no estalvia
res.

**Disc mesurat.** Les cinc imatges ocupen **1,06 GB** en disc i són una descàrrega de **358 MB**,
cinc i no set, perquè l'API, el worker i el planificador fan servir la mateixa imatge. Una base de
dades amb el club descrit més amunt ocupava 12 MB, dins d'un directori de dades de PostgreSQL de
50 MB.

Compta una base d'**1,5 GB**, més el sistema operatiu. L'únic que creix són els fitxers que puja la
gent:

- Una foto per soci i una imatge de portada per activitat, que es reemplacen en lloc d'acumular-se
- Els adjunts de les inscripcions a activitats, que sí que s'acumulen
- Els fitxers de remesa SEPA generats

Cada fitxer pujat està limitat a 10 MB (`MAX_UPLOAD_SIZE_MB`). **Els PDF de rebuts i mandats es
generen quan es demanen i no s'escriuen mai en disc**, així que no són un factor de creixement. Un
club de 500 socis amb una foto cadascun no arriba al gigabyte. Els 40 GB que porten els plans
d'entrada no són una restricció per la qual hagis de comparar proveïdors; deixa marge a sobre si
guardes les còpies de seguretat de la base de dades a la mateixa màquina.

**Sistema operatiu:** qualsevol Linux amb Docker Engine i el complement Compose.
`scripts/vps-bootstrap.sh` prepara un servidor acabat de crear amb **Debian 12** o
**Ubuntu 24.04**, que és el que aquest script espera.

**Un Memship per màquina.** Els contenidors tenen nom fix (`memship-db`, `memship-api`, …) i els
noms de Docker són únics a tot el dimoni, així que una segona instància a la mateixa màquina falla
a mig camí. Fes servir un altre servidor, o una màquina virtual.

## El que costa

Plans d'entrada de dos proveïdors europeus, tots dos de 2 vCPU / 4 GB / 40 GB NVMe, comprovats el
2026-10-20:

| Proveïdor | Pla | Sense IVA | Amb el 21 % d'IVA |
|---|---|---|---|
| [Hetzner](https://www.hetzner.com/cloud/) | CX23 | 5,49 €/mes | ≈ 6,64 €/mes |
| [OVHcloud](https://www.ovhcloud.com/es-es/vps/) | VPS-1 | 3,81 €/mes | 4,61 €/mes |

La xifra d'OVHcloud és la seva tarifa pagant dotze mesos per avançat; mes a mes costa més. Hetzner
va apujar els preus del seu núvol el 15 de juny de 2026, així que la xifra de més amunt és la
vigent i les comparacions més antigues es queden curtes.

A més del servidor:

- **Un domini**, normalment de 10 a 15 € l'any, és a dir, al voltant d'1 € al mes.
- **El correu**, gratuït per a una entitat petita. El pla gratuït de Resend cobreix 3.000 missatges
  al mes, i Gmail funciona amb un compte normal. Mira els límits de més avall abans de donar per fet
  que el pla gratuït et serveix.

Sumant: el pla de Hetzner a 6,64 € amb IVA, més aproximadament 1 € al mes de domini, més res de
correu en un pla gratuït, surt per **menys de 8 € al mes**. Compta amb **de 8 a 12 € al mes amb
IVA** i això et cobreix un servidor més gran o un pla de correu de pagament a mesura que l'entitat
creixi. No hi ha cap cost per soci, ni per administrador, ni per rebut.

## Un nom de domini

Un nom de màquina, amb un registre **A** del DNS que apunti a la IP del servidor. Tan bon punt això
resol, el Caddy que ve inclòs obté i renova un certificat de Let's Encrypt pel seu compte, no hi ha
cap certificat per comprar, instal·lar ni recordar-se de renovar.

Si el domini és de l'entitat i no de qui instal·la, de manera que el nom de màquina, la zona DNS i
el domini del correu són cosa de tres persones diferents, llegeix
[El domini de la teva entitat](../self-hosting/domain-and-dns.md) abans de
començar.

## Una manera d'enviar correu

Memship necessita enviar correu transaccional, i això **no és opcional**: el restabliment de la
contrasenya, la verificació de l'adreça i els avisos de pagament passen tots per aquí, i un soci no
pot entrar per primera vegada fins que funcioni.

Tres opcions, configurables des de la pantalla de Configuració o des del `.env`:

- **Resend**, una API de correu. Pla gratuït: 3.000 missatges al mes i 3 dominis, però **100 al
  dia**. Aquest límit diari és el que molesta: enviar avisos a més de 100 socis d'una tirada el
  supera. El pla de pagament són 20 USD al mes.
- **Gmail**, un compte de Google normal amb una contrasenya d'aplicació. Google aplica els seus
  propis límits diaris d'enviament.
- **Qualsevol servidor SMTP**, inclòs el de l'allotjament de correu que ja tingui l'entitat, sempre
  que accepti STARTTLS, normalment al port 587. Un servidor accessible només pel port 465 no és
  compatible.

[Enviament de correu](../self-hosting/email.md) cobreix les tres, inclosos els
registres DNS que necessita Resend.

## Quant de temps porta

Amb les imatges ja al servidor, la plataforma arrenca i respon com a saludable en **16 segons**.

El temps de principi a fi d'una primera instal·lació en un servidor acabat de crear,
`scripts/vps-bootstrap.sh`, després `scripts/install.sh` i després crear el primer administrador,
no s'ha mesurat, i aquesta pàgina no se l'inventarà. El que domina aquest temps és la descàrrega
de les imatges (358 MB) i la propagació del registre DNS que creïs per al domini.

## El que no necessita

- **Kubernetes, no**, ni cap orquestració més enllà de Docker Compose.
- **Base de dades gestionada, no.** PostgreSQL és un dels set contenidors.
- **Emmagatzematge d'objectes, no.** El que es puja va a un directori del disc del servidor.
- **Un servei de cues a part, no.** Redis i Celery ja hi són.
- **Sense quota de llicència i sense cost per soci.** Memship és programari lliure, amb llicència
  [AGPL v3 de GNU](https://github.com/marcandreuf/memship/blob/main/LICENSE). El pots fer servir,
  modificar i autoallotjar, tant per als teus propis socis com oferint-lo com a servei a altres
  organitzacions. L'única condició és que, si el modifiques i permets que altres persones el facin
  servir a través d'una xarxa, els has d'oferir el codi font de la teva versió modificada.
  Executar-lo sense modificar per als teus propis socis no t'exigeix res.

## Qui l'instal·la

- **Tu mateix**, o qualsevol persona que es manegi amb un servidor Linux i un tauler de DNS.
- **L'informàtic que ja faci servir l'entitat**, que no necessita res d'aquest projecte més enllà
  d'[Installation](../../en/getting-started/installation.md) _(en anglès)_.
- **El mantenidor, com a servei de pagament**, si ningú de l'entitat no vol fer-se càrrec d'un
  servidor.

## I ara

- Si ja està decidit, el següent és instal·lar: [Installation](../../en/getting-started/installation.md)
  _(en anglès)_.
- Si prefereixes tafanejar-lo abans, sense cap servidor: [Quick start](../../en/getting-started/quickstart.md)
  _(en anglès)_ aixeca tota la plataforma a la teva pròpia màquina amb una sola ordre. És només per
  avaluar.
