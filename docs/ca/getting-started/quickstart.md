<!-- source: en/getting-started/quickstart.md -->
<!-- source-hash: 191c18947f23 -->

# Inici ràpid

Prova Memship a la teva màquina en un minut, aproximadament, sense clonar res. Fa servir imatges
ja construïdes i està pensat per a l'**avaluació**, no per a producció. Per a un desplegament
real, mira [Instal·lació](installation.md).

> **En anglès:** [Quick start](../../en/getting-started/quickstart.md).

## Requisits previs

- Docker i Docker Compose

## 1. Crea'n una carpeta

Tot el que segueix s'executa des d'un sol directori, que acaba contenint l'únic fitxer que cal.
Compose pren el **nom del projecte** del nom d'aquest directori, i la pila d'inici ràpid desa les
dades en volums de Docker amb el nom d'aquest projecte, així que executa totes les ordres
`docker compose` d'aquesta guia des de dins d'aquesta carpeta. Des de qualsevol altre lloc,
Compose busca un projecte diferent i no trobarà ni els teus contenidors ni les teves dades.

```bash
mkdir -p "$HOME/memship-quickstart"
cd "$HOME/memship-quickstart"
echo "STACK_PREFIX=$(date +%Y%m%d-%H%M%S)" > .env
```

L'última línia posa als contenidors d'aquesta pila el nom del moment en què la vas engegar, de
manera que `docker ps` et diu quina avaluació és quina i quan la vas començar:
`20261105-043107-memship-api`. Compose llegeix el `.env` d'aquesta carpeta a cada ordre, així que
ho configures una sola vegada. També vol dir que una segona avaluació en una segona carpeta té els
seus propis noms i pot funcionar al costat d'aquesta, amb el seu propi `PORT` i `MAILPIT_PORT`. Si
et saltes la línia, els contenidors es diuen `demo-memship-*`, cosa que funciona fins que en vols
dues.

## 2. Descarrega el fitxer compose d'inici ràpid i engega

```bash
curl -fsSL https://raw.githubusercontent.com/marcandreuf/memship/main/docker-compose.quickstart.yml -o docker-compose.yml
docker compose pull          # fetch the latest published images
PORT=8081 docker compose up -d
```

Canvia `PORT=8081` per qualsevol port que prefereixis (per defecte és `80`).

Això executa les darreres imatges publicades, i `/api/v1/health` informa de `"version":"latest"`.
Per avaluar una versió concreta, defineix `IMAGE_TAG` a totes dues ordres. Aleshores health informa
d'aquesta versió:

```bash
IMAGE_TAG=3.1.0 docker compose pull
IMAGE_TAG=3.1.0 PORT=8081 docker compose up -d
```

## 3. Executa la posada en marxa

La mateixa ordre configura Memship a tots els entorns. És interactiva i fa tres preguntes
independents:

```bash
docker compose exec -it demo-memship-api python -m app.cli.seed
```

1. **Superadministrador**: tu tries l'adreça i la contrasenya. No hi ha res predefinit i no es
   publiquen credencials enlloc.
2. **Dades del club**: només s'ofereix quan n'hi ha, així que en una instal·lació nova no fa res.
3. **Configuració del club**: introdueix les dades reals de l'entitat o genera un club de
   demostració.

Les tres preguntes també tenen opcions, per automatitzar una avaluació o executar-la on no hi ha
cap terminal per respondre les preguntes:

```bash
# same three steps, unattended
docker compose exec -T -e MEMSHIP_ADMIN_PASSWORD='...' demo-memship-api \
  python -m app.cli.seed --admin-email you@example.org
docker compose exec -T demo-memship-api python -m app.cli.seed --demo

# ... or --club-name instead of --demo, for the real-details path
docker compose exec -T demo-memship-api \
  python -m app.cli.seed --club-name 'Your Organization'
```

Fixa't en el `-T` en lloc de `-it`, i en el fet que la contrasenya passa per
`docker compose exec -e`: el contenidor no hereta l'entorn del teu shell, i passar-la com a
argument la deixaria a l'historial del shell i a `ps`. `--reset-club-data` controla la tercera
pregunta. Mira `python -m app.cli.seed --help`.

### Quin camí triar a la pregunta 3

**Si avalues Memship per primera vegada, respon `2) demo club`.** No és només per tenir dades per
mirar. El club de demostració **activa** els mòduls opcionals, i una instal·lació amb dades reals
comença deliberadament amb gairebé tots **desactivats**: dues de les vint-i-una claus de
funcionalitat, amb set rutes que redirigeixen al tauler. Tria dades reals per veure què és
Memship, i el carnet de soci, el calendari de reserves i els avisos simplement no hi són, sense
res a la pantalla que digui que el mòdul existeix. [Feature flags](../self-hosting/feature-flags.md)
les llista totes i explica com s'activa cadascuna.

El club de demostració et dona ~60 socis en tots els estats, activitats, rebuts en tots els
estats, mandats SEPA i recordatoris al tauler, prou per avaluar el tauler financer i el resum
anual. Es pot tornar a executar sense risc (és idempotent).

El club de demostració també crea accessos per a un **administrador del club** i **dos socis**,
amb contrasenyes generades. Es mostren una sola vegada, al final de l'execució:

```
  Accounts:

    super admin  you@example.org             (the password you chose)
    club admin   admin@mediterrani.example   4hVqTmXeb9PkscYRt2Nu
    member       demo0@mediterrani.example   pQ7yKdRfw3TgLmXaB6ns
    member       demo1@mediterrani.example   Zj5rWnEcx8VbHtPqM4dy
```

Això és una execució interactiva que respon les tres preguntes. Amb les opcions de més amunt són
dues ordres, i cadascuna mostra només el que ha creat: el superadministrador amb la primera, i
l'administrador del club i els dos socis amb l'execució de `--demo`. L'execució de `--club-name`
no crea cap accés, així que no mostra cap bloc de comptes.

Guarda aquesta sortida: les contrasenyes només es desen com a hash i no es poden tornar a mostrar.
Els dos accessos de soci són la manera de veure el portal del soci sense haver de donar un compte
d'administrador, i és la meitat del producte que una sessió d'administrador no et mostra mai.

**Respon `1) real details` només si vols avaluar-lo amb les teves dades**, i llegeix això abans:

> **Una instància d'inici ràpid no és per conservar-la.** Tot el que hi introdueixis, real o no,
> viu en volums de Docker d'un sol ús darrere d'una contrasenya de base de dades fixa, i per
> defecte tots els correus que envia la instància els recull la safata de prova local en lloc
> d'arribar a la persona a qui van adreçats. Això és el que la fa segura de llençar i el que la fa
> inadequada per a un club. Quan vulguis una instància per conservar, torna a començar amb
> [Instal·lació](installation.md), que genera secrets reals i posa les dades en un lloc del qual
> pots fer còpies de seguretat.

## 4. Obre l'aplicació

Ves a **http://localhost:8081** i inicia sessió com el superadministrador que has creat.

> **Continua sent una pila d'avaluació.** Abans de posar Memship en una xarxa, segueix
> [Instal·lació](installation.md) i la
> [referència de configuració](../self-hosting/configuration.md). Mira
> [la pregunta 3 de més amunt](#quin-camí-triar-a-la-pregunta-3) per saber per què les dades
> reals dels socis no hi tenen cabuda.

## 5. Prova l'alta d'un soci

La pila inclou una **safata de prova** a **http://localhost:8025**. Tots els correus que envia la
instància (verificació d'adreça, aprovació d'alta, rebuts, recordatoris de pagament) hi arriben en
lloc de lliurar-se, sigui quina sigui l'adreça de destinació. Aquest és el flux per provar primer:

1. En una finestra privada, obre **http://localhost:8081/register** i registra't amb qualsevol
   adreça, real o no.
2. Obre la safata de prova, troba el correu de verificació i segueix-ne l'enllaç.
3. De tornada a la sessió d'administrador, obre **Altes pendents** a la barra lateral. La nova
   alta hi apareix, al costat d'unes quantes que crea el club de demostració, així que fes clic a
   **Aprovar** a la seva fila i confirma.
4. El correu d'aprovació arriba a la safata de prova, i el soci ja pot iniciar sessió.

La safata és local a la teva màquina: només es publica a `127.0.0.1` i no conté res real. Defineix
`MAILPIT_PORT` al costat de `PORT` si el 8025 està ocupat.

Només continua en vigor **mentre no s'hagi desat mai Configuració → Correu**. Configura-hi un
proveïdor real i, a partir d'aquell moment, envia aquest proveïdor, que és la precedència prevista
i no una errada, mira [Quin està en vigor](../self-hosting/email.md#quin-està-en-vigor).

## Passar de l'avaluació a l'ús real

No portis la pila d'inici ràpid a producció: instal·la-la com cal amb
[Instal·lació](installation.md), que genera secrets reals i posa les dades en un lloc del qual
pots fer còpies de seguretat.

Un club de demostració té nou mòduls opcionals activats perquè qui avalua els ha de veure, no
perquè un club els hagi de fer servir. Una instal·lació real comença amb gairebé tots desactivats
a propòsit, i actives cadascun quan estiguis a punt. No prenguis la configuració del club de
demostració com una configuració recomanada.

Si només vols treure el club de demostració d'una instància que conserves, torna a executar la
posada en marxa i respon *yes* a la pregunta de les dades del club. Esborra el club de
demostració i conserva el superadministrador, els rols del sistema i els proveïdors de pagament
que hagis configurat, mira [Configuració inicial](first-setup.md).

## Atura-ho tot

Executa aquestes ordres des de la carpeta que vas crear al pas 1: Compose identifica la pila pel
directori des del qual s'executa.

```bash
docker compose stop          # pause it; containers and data stay put
docker compose start         # ... and pick up where you left off
```

```bash
docker compose down          # stop and remove the containers and the network; data kept
docker compose down -v       # ... and delete the data volumes with them
```

`down` conserva la base de dades i els fitxers pujats, així que un `docker compose up -d` posterior
recupera el mateix club. **`down -v` és la que no deixa res**: el club de demostració, el
superadministrador que vas crear i tots els rebuts se'n van amb ella, i no es pot desfer.

Per recuperar també l'espai de disc, elimina les imatges un cop la pila estigui aturada:

```bash
docker image rm ghcr.io/marcandreuf/memship-backend:latest \
                ghcr.io/marcandreuf/memship-frontend:latest \
                axllent/mailpit:v1.29
```

Deixa `caddy`, `postgres` i `redis` tranquils tret que estiguis segur que res més de la màquina
no les fa servir: són imatges públiques corrents i és ben possible que alguna altra cosa les
utilitzi.

### Si ja no ets en aquesta carpeta

Tots els contenidors d'inici ràpid porten `-memship-` al nom, sigui quin sigui el prefix amb què
es van engegar, així que pots trobar-ne i aturar-ne un des de qualsevol lloc, cosa útil si has
esborrat el directori o no recordes on el vas posar:

```bash
docker ps -a --format '{{.Names}}' --filter name=-memship-   # which stacks exist
docker rm -f $(docker ps -aq --filter name=-memship-)        # remove all of them
```

El prefix de data i hora és el que distingeix les execucions en aquest llistat. La segona ordre
elimina tots els contenidors d'inici ràpid de la màquina, així que revisa la primera si n'estàs
executant més d'una.

Això elimina els contenidors, però no les dades. Els volums porten el nom del projecte de Compose,
que és el nom de la carpeta, `docker volume ls | grep demo-memship` els troba i
`docker volume rm <name>` n'esborra un.
