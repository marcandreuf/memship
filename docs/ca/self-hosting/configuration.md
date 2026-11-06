<!-- source: en/self-hosting/configuration.md -->
<!-- source-hash: 500c0f9893b8 -->

# Referència de configuració

Memship es configura amb variables d'entorn, normalment definides en un fitxer `.env` al costat de
`docker-compose.yml`. Copia `.env.example` a `.env` i ajusta'l. Aquesta pàgina documenta totes les
opcions que llegeix el backend.

> **En anglès:** [Configuration reference](../../en/self-hosting/configuration.md).

> **Mínim per a producció:** canvia `SECRET_KEY` i `DB_PASSWORD`, posa a `IMAGE_TAG` una versió
> publicada i configura el [correu](email.md).

## Disposició del desplegament

| Variable            | Per defecte | Descripció                                                         |
|---------------------|----------|--------------------------------------------------------------------|
| `MEMSHIP_DATA_ROOT` | `./data` | Ruta absoluta que conté totes les rutes persistents: base de dades, fitxers pujats, estat del planificador, certificats TLS, còpies de seguretat. Fes-ne còpia de seguretat. Mira [Installation](../../en/getting-started/installation.md#the-data-root) _(en anglès)_. |
| `SITE_ADDRESS`      | _(buit)_ | L'adreça que serveix Caddy. Un nom de màquina sol (`memship.example.com`) fa que Caddy obtingui automàticament un certificat de Let's Encrypt; buit, serveix HTTP sense xifrar al port 80. |
| `HOST_UID`          | `1001`   | Uid amb què s'executen els contenidors del backend. Posa-hi el teu `id -u` perquè els fitxers pujats als bind mounts siguin teus i els puguis llegir sense `sudo`. |
| `HOST_GID`          | `1001`   | Gid, igualment, el teu `id -g`.                                    |

`scripts/install.sh` les defineix totes quatre per tu.

## Seguretat

| Variable      | Per defecte             | Descripció                                                                  |
|---------------|-------------------------|-----------------------------------------------------------------------------|
| `SECRET_KEY`  | _(es genera a `storage/session.key`)_ | Signa les cookies de sessió i els codis QR del carnet, i en deriva la clau que xifra les credencials desades dels proveïdors de pagament. Si la deixes en blanc, es genera una clau per instal·lació en el primer arrencament; **defineix-la explícitament** si vols que sobrevisqui a la pèrdua de l'arrel de dades. Genera-la amb `openssl rand -hex 32`. Els valors d'exemple que porten els fitxers d'exemple es reconeixen i s'ignoren: tot el que se signa amb una clau publicada es pot falsificar. |
| `SESSION_KEY_FILE` | `<STORAGE_LOCAL_PATH>/session.key` | On es desa la clau de signatura generada automàticament quan `SECRET_KEY` és en blanc. Ha de ser en emmagatzematge persistent, o cada reinici fa sortir tots els usuaris i les credencials de pagament desades deixen de desxifrar-se. |
| `COOKIE_SECURE` | _(derivat de `FRONTEND_URL`)_ | Força l'atribut `Secure` de la cookie de sessió a activat o desactivat. El valor per defecte llegeix l'esquema de `FRONTEND_URL`, que és correcte llevat que el TLS el termini un proxy anterior que parla HTTP sense xifrar amb Caddy; en aquest cas, posa-hi `true`. |
| `MEMSHIP_SECRET_KEY` | _(es genera a `storage/secret.key`)_ | Xifra les credencials de SSO i dels proveïdors de pagament desades a la base de dades. **Defineix-la explícitament**: una clau generada automàticament només viu a l'arrel de dades, així que una màquina reconstruïda no pot desxifrar sense ella una còpia de seguretat restaurada. Canviar-la fa que les credencials desades deixin de ser llegibles. |
| `SECRETS_KEY_FILE` | `<STORAGE_LOCAL_PATH>/secret.key` | On es desa la clau generada automàticament quan `MEMSHIP_SECRET_KEY` no està definida. Ha de ser en emmagatzematge persistent, o les credencials desades deixen de ser llegibles després d'un reinici. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30`      | Durada del testimoni d'accés, en minuts.                                    |

## Base de dades

| Variable        | Per defecte                                                | Descripció                                              |
|-----------------|------------------------------------------------------------|---------------------------------------------------------|
| `DB_PASSWORD`   | `memship`                                                  | **Canvia-la.** Contrasenya de PostgreSQL que fa servir Compose. |
| `DATABASE_URL`  | `postgresql://memship:memship@localhost:5433/memship_db`   | Cadena de connexió completa. A Compose apunta al servei `db`. |

## Aplicació

| Variable         | Per defecte              | Descripció                                                         |
|------------------|--------------------------|--------------------------------------------------------------------|
| `APP_ENV`        | `development`            | Posa-hi `production` als desplegaments. Afecta el comportament de depuració i l'exposició de la documentació de l'API. |
| `APP_VERSION`    | _(de la imatge / l'etiqueta de git)_ | S'incorpora a la imatge en construir-la; deixa-la sense definir quan executis imatges publicades. |
| `DEFAULT_LOCALE` | `es`                     | Idioma per defecte de la interfície: `es`, `ca` o `en`.            |
| `CORS_ORIGINS`   | `http://localhost:3000`  | Llista separada per comes dels orígens de navegador permesos. Posa-hi els URL del teu lloc. |
| `FRONTEND_URL`   | `http://localhost:3000`  | URL públic del frontend; es fa servir als enllaços dels correus.   |
| `TRUSTED_PROXY_HOPS` | `1`                  | Quants proxies hi ha davant de l'API. Cadascun afegeix a `X-Forwarded-For` l'interlocutor que ha acceptat, així que l'adreça de qui fa la petició és a aquest nombre d'entrades des de la dreta. `1` és el Caddy inclòs. El frontend no compta com a salt: les seves rutes de proxy passen la capçalera sense canviar-la, així que l'API veu la mateixa cadena tant si la petició ha passat per elles com si ha anat directament a `/api/v1`. Apuja-ho si hi poses qualsevol altra cosa al davant (una CDN, un balancejador de càrrega, el teu propi proxy invers), o el límit d'intents d'inici de sessió per IP assigna tots els que fan peticions a aquell proxy i limita tot el teu lloc alhora. Posa-hi `0` només si l'API està publicada sense res al davant, cosa que fa que la capçalera la proporcioni qui fa la petició i que el límit per IP es pugui eludir. |
| `BACKEND_PUBLIC_URL` | `http://localhost:8003` | URL del backend accessible públicament per a les crides de retorn dels proveïdors de pagament (p. ex. `Ds_Merchant_MerchantURL` de Redsys). En producció **ha de ser** el nom de màquina extern al qual la passarel·la pot fer POST. |

## Ports

Es defineixen al `.env` per a la plataforma de Compose (els valors per defecte són a
`.env.example`):

| Variable     | Per defecte | Descripció                     |
|--------------|---------|--------------------------------|
| `HTTP_PORT`  | `80`    | Port HTTP de Caddy.            |
| `HTTPS_PORT` | `443`   | Port HTTPS de Caddy.           |
| `API_PORT`   | `8003`  | Port directe de l'API del backend. |
| `DB_PORT`    | `5433`  | Port de PostgreSQL a la màquina. |

## Correu

El correu està **desactivat** llevat que hi hagi definida una clau d'API de Resend o un servidor
SMTP. Mira [Enviament de correu](email.md) per a una guia completa.

**Resend (preferit, enviament gestionat):**

| Variable            | Per defecte | Descripció                      |
|---------------------|---------|---------------------------------|
| `RESEND_API_KEY`    | _(buit)_ | Activa l'enviament amb Resend.  |
| `RESEND_FROM_EMAIL` | _(buit)_ | Adreça de remitent verificada.  |

**SMTP (alternativa autoallotjada):**

| Variable        | Per defecte             | Descripció                           |
|-----------------|-------------------------|--------------------------------------|
| `SMTP_HOST`     | _(buit)_                | Activa l'enviament per SMTP quan està definida. |
| `SMTP_PORT`     | `587`                   | Port SMTP.                           |
| `SMTP_USER`     | _(buit)_                | Usuari SMTP.                         |
| `SMTP_PASSWORD` | _(buit)_                | Contrasenya SMTP.                    |
| `SMTP_FROM`     | `noreply@memship.local` | Adreça del remitent.                 |
| `SMTP_TLS`      | `true`                  | Fa servir STARTTLS.                  |

Si tots dos estan configurats, té preferència Resend.

Totes les variables anteriors també es poden definir des de **Configuració → Integracions →
Correu**, inclòs el servidor SMTP. Un cop desada aquesta pantalla, els seus valors tenen
preferència i el proveïdor actiu és el que hi triïs: mira [Enviament de correu](email.md#quin-està-en-vigor).

## Tasques en segon pla (Celery / Redis)

| Variable            | Per defecte                | Descripció                                                 |
|---------------------|----------------------------|------------------------------------------------------------|
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Broker Redis per al correu asíncron, la facturació recurrent i els recordatoris, i on es compten els límits d'intents d'inici de sessió i de restabliment de contrasenya, perquè tots els processos de l'API els comparteixin. Redis ve inclòs a la plataforma de Compose. |
| `CELERY_CONCURRENCY` | `2`                       | Processos del worker. Cadascun ocupa uns 50 MiB en repòs. El valor per defecte del mateix Celery és un per CPU, cosa que fa créixer la memòria del worker amb la màquina i no amb la feina; les tasques programades són lleugeres, així que amb dos n'hi ha prou. Apuja-ho només si el correu en cua s'acumula. |

El worker i el planificador (Celery beat) s'executen com a part de la plataforma i fan funcionar
els correus asíncrons, la generació programada de quotes i els recordatoris de pagament.

## Còpies de seguretat fora del servidor

Les llegeix `scripts/push-backup.sh`, mai l'aplicació. Mira
[Còpies de seguretat i restauració](backups-and-restore.md#còpies-fora-del-servidor) per configurar cada destinació.

| Variable | Per defecte | Descripció |
|---|---|---|
| `BACKUP_TARGET` | _(buit)_ | On van les instantànies: `ssh://user@host[:port]/absolute/path` o `s3://bucket[/prefix]`. Obligatòria per executar l'script. |
| `BACKUP_RETENTION_DAYS` | `30` | Les instantànies més antigues que això s'eliminen de la destinació després d'un enviament correcte. |
| `BACKUP_SSH_KEY` | _(el per defecte d'ssh)_ | Fitxer d'identitat per a una destinació `ssh://`. |
| `BACKUP_S3_ACCESS_KEY_ID` | _(buit)_ | Clau d'accés per a una destinació `s3://`. |
| `BACKUP_S3_SECRET_ACCESS_KEY` | _(buit)_ | El seu secret. Es passa al contenidor per l'entorn, mai en una línia d'ordres. |
| `BACKUP_S3_REGION` | `us-east-1` | Regió del bucket. |
| `BACKUP_S3_ENDPOINT` | _(AWS)_ | Endpoint d'un emmagatzematge que no sigui d'AWS, p. ex. `https://s3.eu-central-003.backblazeb2.com`. |
| `BACKUP_AWS_CLI_IMAGE` | `amazon/aws-cli:2.27.0` | La imatge que executa un enviament a `s3://`. |

## Emmagatzematge de fitxers

| Variable             | Per defecte | Descripció                                               |
|----------------------|-----------|----------------------------------------------------------|
| `STORAGE_LOCAL_PATH` | `storage` | Ruta dins del contenidor per als fitxers pujats (logotips, imatges d'activitats, PDF). Es munta des de `$MEMSHIP_DATA_ROOT/storage`, que també conté `secret.key`; inclou-la a les [còpies de seguretat](backups-and-restore.md). |
| `MAX_UPLOAD_SIZE_MB` | `10`      | Mida màxima d'un fitxer pujat, en megabytes.             |

## Servidor

| Variable | Per defecte | Descripció                   |
|----------|-----------|------------------------------|
| `HOST`   | `0.0.0.0` | Adreça on escolta el backend. |
| `PORT`   | `8000`    | Port del backend dins del contenidor. |

## Migracions

| Variable         | Per defecte | Descripció                                                              |
|------------------|---------|-------------------------------------------------------------------------|
| `RUN_MIGRATIONS` | _(a `1` a Compose)_ | Quan val `1`, el backend executa les migracions de la base de dades en arrencar. Mira [Actualitzar](upgrading.md). |
