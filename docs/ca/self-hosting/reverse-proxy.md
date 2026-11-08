<!-- source: en/self-hosting/reverse-proxy.md -->
<!-- source-hash: f28547d2c7c4 -->

# Darrere del teu propi proxy invers

Memship inclou Caddy al davant: termina l'HTTPS, obté el certificat, posa les capçaleres de
seguretat i encamina cada petició al contenidor que toca. **Fes-lo servir si no tens cap motiu per
no fer-ho.** La instal·lació el configura, i res d'aquesta pàgina no li cal.

> **En anglès:** [Behind your own reverse proxy](../../en/self-hosting/reverse-proxy.md).

Aquesta pàgina és per a l'altre cas: un servidor que ja executa un proxy invers per a altres llocs,
o una organització on tot el trànsit ha de passar pel seu propi proxy. Llavors Memship s'executa
sense el seu Caddy, i el teu proxy n'ocupa el lloc. Els contenidors de l'aplicació són els mateixos
en tots dos casos; només canvia el que hi ha al davant. El proxy compatible és **Traefik** (v2 o
v3), mitjançant etiquetes (labels) de Docker.

## Què ha de fer el teu proxy

Aquestes són les regles del Caddy inclòs, i un proxy extern les ha de mantenir totes:

| Petició | Va a |
|---|---|
| `/api/v1/*` | l'API, `api:8000` |
| tota la resta | el frontend, `frontend:3000` |

**No hi ha cap ruta `/uploads`, a propòsit.** Els fitxers pujats arriben al navegador pel camí
`/api/uploads` del frontend, que passa la sessió del soci al router de fitxers pujats autenticat de
l'API. Una regla que enviï `/uploads` directament a l'API se salta aquesta comprovació. Quan aquell
router era un muntatge de fitxers estàtics, una regla així lliurava la clau de xifratge i els
fitxers SEPA. Si el teu proxy té el costum d'afegir una ruta `/uploads` per a aplicacions com
aquesta, no l'afegeixis aquí.

Cada resposta també necessita aquestes capçaleres, les mateixes que posa el Caddy inclòs:

| Capçalera | Valor |
|---|---|
| `X-Content-Type-Options` | `nosniff` |
| `Content-Security-Policy` | `frame-ancestors 'none'` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Strict-Transport-Security` | `max-age=31536000` |
| `Server` | eliminada |

No les jutgis des d'una pestanya del navegador: el frontend en posa quatre ell mateix, de manera
que una pàgina pot semblar completa mentre totes les respostes de `/api/v1/*` no les tenen.
Comprova-ho amb `curl -sI https://<your-host>/api/v1/health`.

## Configurar-ho amb Traefik

`docker-compose.external-proxy.yml`, al costat de `docker-compose.yml`, fa tot l'anterior amb
etiquetes de Traefik:

- desactiva el Caddy inclòs
- uneix l'API i el frontend a la xarxa Docker del teu proxy
- encamina `/api/v1/*` a l'API i tota la resta al frontend, sense cap ruta `/uploads`
- afegeix les sis capçaleres com un sol middleware, connectat als dos contenidors
- dona als callbacks dels proveïdors de pagament (`/api/v1/webhooks/*`) un router propi

**1. El teu Traefik.** Ja s'ha d'executar amb el proveïdor Docker, un entrypoint (punt d'entrada)
HTTPS i un certificate resolver, i ha d'estar connectat a una xarxa Docker a la qual es puguin unir
els contenidors de Memship. Apunta't el nom de la xarxa, el de l'entrypoint i el del resolver.

**2. Instal·la com sempre,** seguint la [Instal·lació (Docker)](../getting-started/installation.md),
amb `--domain` igual al nom de màquina que servirà el teu proxy. Això escriu `FRONTEND_URL`,
`CORS_ORIGINS` i `BACKEND_PUBLIC_URL` com a `https://<your-host>`, de què depenen els enllaços dels
correus, l'inici de sessió i els callbacks de pagament. `install.sh` comprova que el nom resol cap
a aquest servidor, igual que ho fa amb el Caddy inclòs.

**3. Activa l'overlay a `.env`:**

```bash
COMPOSE_FILE=docker-compose.yml:docker-compose.external-proxy.yml
MEMSHIP_HOST=memship.example.org
TRAEFIK_NETWORK=traefik
TRAEFIK_ENTRYPOINT=websecure
TRAEFIK_CERTRESOLVER=letsencrypt
```

`MEMSHIP_HOST` és el nom de màquina sense `https://`. Les altres tres prenen els noms del pas 1; els
valors que es mostren són els predeterminats. `COMPOSE_FILE` és el que fa que tota ordre
`docker compose` llegeixi els dos fitxers, incloses les dels scripts: no hi ha cap ordre separada
que calgui recordar.

**4. Aplica-ho.** `install.sh` va arrencar el Caddy inclòs, i desactivar-lo a l'overlay no atura
un contenidor que ja s'està executant, així que primer elimina'l i després recrea la resta:

```bash
docker compose stop caddy
docker compose rm -f caddy
docker compose up -d
```

Mentre Caddy no hagi desaparegut ocupa els ports 80 i 443, i el teu proxy no els pot agafar si
s'executa al mateix servidor.

**5. Comprova-ho**, des de qualsevol màquina:

```bash
curl -sI https://memship.example.org/api/v1/health
```

Hauria de respondre `200` amb les cinc capçaleres de la taula anterior i cap línia `Server`.

## Callbacks de pagament i control d'accés

Si poses el lloc darrere de l'autenticació bàsica o l'inici de sessió únic (SSO) del teu proxy, per
a una demo o una còpia de staging, afegeix aquest middleware només als routers `memship-api` i
`memship-frontend`, **mai** a `memship-webhooks`. Stripe i Redsys criden aquest camí des dels seus
propis servidors i s'identifiquen amb una signatura, no amb una contrasenya: un inici de sessió al
davant rebutja totes les confirmacions de pagament, i els rebuts pagats es queden sense pagar.

## Actualitzacions, còpies de seguretat i restauracions

No canvia res. `upgrade.sh`, `db-backup.sh` i `db-restore.sh` executen `docker compose` des del
directori d'instal·lació, de manera que llegeixen `COMPOSE_FILE` i mantenen l'overlay;
`push-backup.sh` fa el seu bolcat a través de `db-backup.sh`.
`install.sh` recarrega el Caddy inclòs després d'una actualització només quan Caddy forma part de
la pila, així que una actualització mai no l'arrenca al costat del teu proxy.

L'API continua publicada a `127.0.0.1:8003`, només en loopback, com a la configuració per defecte.
`verify-deployment.sh` hi comprova la salut de l'API després d'una actualització; res de fora del
servidor no hi pot arribar.

## Tornar al Caddy inclòs

Treu la línia `COMPOSE_FILE` de `.env` (les altres quatre es poden quedar, llavors no s'utilitzen),
fes que el DNS del domini apunti al servidor si el teu proxy era en una altra màquina, allibera els
ports 80 i 443 si el teu proxy s'executa al mateix servidor, i executa `docker compose up -d`. Caddy
arrenca i demana el seu certificat.
