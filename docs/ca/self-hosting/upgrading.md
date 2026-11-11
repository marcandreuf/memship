<!-- source: en/self-hosting/upgrading.md -->
<!-- source-hash: 7d0bceda9dfa -->

# Actualitzar

Memship es publica com a imatges de Docker versionades, més un grapat de fitxers que viuen al seu
costat: el fitxer de Compose, la configuració de Caddy, els scripts. Actualitzar vol dir refrescar
totes dues coses i després executar una ordre que fa la còpia, aplica la versió i la verifica. Les
migracions de la base de dades s'executen automàticament en arrencar.

> **En anglès:** [Upgrading](../../en/self-hosting/upgrading.md).

## Versions

Memship segueix el [versionat semàntic](https://semver.org/). **Les etiquetes de git són l'única
font de veritat** de la versió, no hi ha cap fitxer `VERSION`. Les imatges publicades s'etiqueten
amb la versió publicada (p. ex. `2.19.0`) i amb `latest`.

Cada instal·lació queda fixada a una versió en lloc de seguir `latest`, de manera que les
actualitzacions són deliberades i una instància pot dir quina versió executa. `IMAGE_TAG` a
`.env` la guarda; `install.sh
--tag` i `upgrade.sh` l'escriuen per tu, i `/api/v1/health` la retorna:

```bash
curl -s http://127.0.0.1:8003/api/v1/health
{"status":"healthy","version":"2.19.0","environment":"production"}
```

## Procediment d'actualització

**Revisa primer les notes de la versió** de destinació: els canvis incompatibles i els nous
paràmetres obligatoris s'hi assenyalen, a la
[pàgina de versions](https://github.com/marcandreuf/memship/releases).

Després, dues ordres. Refresca els fitxers del desplegament i aplica la versió:

```bash
MEMSHIP_VERSION=3.3.0
MEMSHIP_APP=/srv/openmemship/app          # wherever your install lives

curl -fsSL "https://github.com/marcandreuf/memship/archive/refs/tags/v${MEMSHIP_VERSION}.tar.gz" \
  | tar -xz -C "$MEMSHIP_APP" --strip-components=1

cd "$MEMSHIP_APP"
./scripts/upgrade.sh "$MEMSHIP_VERSION"
```

**Per què la primera ordre.** Una part de cada versió es distribueix al costat de les imatges i
no a dins: `docker-compose.yml`, el `Caddyfile`, `scripts/`. Canviar només `IMAGE_TAG` deixa una
instal·lació mig actualitzada: el backend nou funcionant darrere de la configuració antiga del
proxy. Desempaquetar sobre el directori substitueix aquests fitxers i deixa `.env` intacte, ja que
`.env` no és a l'arxiu. No hi intervenen ni git ni cap còpia del codi font.

`tar -xz` escriu al seu directori `-C`, així que indica'l en lloc de dependre del directori actual
del shell: un `curl | tar` enganxat tot sol, sense el `cd`, desempaqueta una versió allà on et
trobis i no diu res. Tingues en compte també que desempaquetar *afegeix i substitueix*; mai no
elimina, així que un fitxer que una versió ha suprimit es queda fins que l'eliminis tu.

**No cal que recordis aquest pas.** `upgrade.sh` ho comprova, mira el pas 5 més avall.

**Què fa la segona**, per ordre, aturant-se si falla qualsevol pas. Els passos de l'1 al 7
s'executen tots **abans de substituir res a la instància**, així que si qualsevol d'ells s'atura,
la versió que tenies continua servint, i cada refús indica l'estat que ha trobat:

1. **Es nega a anar enrere.** Tornar a fixar `IMAGE_TAG` fa tornar enrere les imatges però no
   l'esquema, així que una versió més antiga es troba amb una base de dades que no entén. En lloc
   d'això, restaura la instantània presa abans d'actualitzar, mira
   [Tornar enrere](#tornar-enrere). Si saps que la versió que deixes no portava cap migració, o ja
   has restaurat la base de dades, `--allow-downgrade` continua. Només es compara entre dues
   versions publicades: una RC o una instal·lació amb `latest` no tenen cap ordre sobre el qual
   raonar, així que es deixen tranquil·les en lloc d'endevinar.

2. **Comprova que `.env` porta el que la versió espera.** Compara els paràmetres del teu `.env`
   amb els que l'instal·lador d'aquesta versió escriu en un `.env` que crea. Un `.env` escrit per
   la mateixa versió els té tots, així que en una instància al dia no diu res; en una d'antiga
   indica què s'hi ha afegit des d'aleshores, que és el paràgraf de les notes de la versió que
   potser no has llegit.

   Només un d'ells atura l'actualització: **un `.env` sense cap línia `IMAGE_TAG`.** Aplicar una
   versió reescriu aquesta línia on és, i no hi ha res per reescriure, així que l'etiqueta
   s'acceptaria, es perdria, i la pila arrencaria amb el que apunti `latest`. Afegeix la línia i
   torna-ho a executar.

3. **Comprova que hi ha espai al disc** per a les imatges que està a punt de descarregar i per a
   la instantània que està a punt d'escriure, abans de fer cap de les dues coses. Una
   actualització que es queda sense espai a mig camí és pitjor que una que es nega: la base de
   dades i el proxy escriuen al mateix disc que la descàrrega està omplint.

   Les xifres estan mesurades, no endevinades. Per a les imatges es reserva 1 GB en una
   actualització i 1,8 GB en una primera instal·lació: una primera instal·lació descarrega tota
   la pila (1,55 GB mesurats), una actualització només el que ha canviat (771 MB mesurats entre
   dues versions consecutives, perquè la capa de dependències del backend es reconstrueix a cada
   versió). No es demana res per imatges que ja són locals, així que tornar a executar-ho contra
   la versió ja instal·lada mai no es rebutja per falta d'espai per descarregar-la. La instantània
   es dimensiona a partir del **teu propi últim bolcat**, multiplicat per dos, i quan no hi ha cap
   bolcat del qual aprendre no es demana res en lloc d'inventar-se una xifra.

   `--skip-disk-check` continua igualment, per a una màquina on `df` informa malament de
   l'emmagatzematge, un sistema de fitxers de xarxa o thin provisioning per sota.

4. **Descarrega les imatges de la versió.** Totes, abans de tocar res de la instància, així que
   una versió que no existeix, o una versió amb imatges que no s'han publicat totes, és una
   actualització que es nega mentre l'antiga continua servint. No se substitueix res i encara no
   s'escriu cap instantània, així que no costa res quan s'atura.

5. **Confirma que els fitxers del desplegament d'aquí són els de la versió.** Compara
   `docker-compose.yml` i el `Caddyfile` del directori d'instal·lació, per checksum, amb el que la
   versió espera que siguin, i s'atura si difereixen, que és l'aspecte que té una actualització en
   què s'ha saltat la primera ordre. S'executa abans de la instantània, així que un refresc oblidat
   no costa res.

   Els checksums esperats viatgen **dins la imatge**, escrits com una etiqueta quan es va
   construir, i es llegeixen de la còpia que s'acaba de descarregar. Llegir-los només necessita el
   registre d'imatges, que l'actualització ja necessitava igualment, així que un desplegament que
   pot descarregar també pot comprovar, i res d'això depèn de poder arribar a GitHub.

   D'aquí se'n deriven dues coses. Una versió que distribueix fitxers de desplegament idèntics als
   de l'anterior no diu res aquí, com ha de ser: els bytes coincideixen, així que no hi ha res a
   informar. I una versió construïda abans que existís aquesta etiqueta no porta res amb què
   comparar; es diu clarament i l'actualització continua, de manera que les versions antigues es
   poden continuar instal·lant.

   Si mantens aquests fitxers tu mateix (un desplegament que conserva un fitxer de Compose
   personalitzat, per exemple), `--skip-file-check` continua sense comparar-los.

6. **Fa una còpia de la base de dades** amb `scripts/db-backup.sh`. Una versió que porta una
   migració d'esquema no es pot desfer tornant a fixar `IMAGE_TAG`: les imatges tornen enrere,
   l'esquema migrat no, així que aquest bolcat és l'única sortida d'una actualització fallida. Si
   falla, l'actualització no es fa. En una primera instal·lació encara no hi ha base de dades i ho
   diu en lloc d'això.

7. **Executa les comprovacions pròpies de la versió contra la base de dades** que la versió antiga
   encara està servint. Una migració que es negaria (mira més avall) ho diu ara, mentre la
   instància continua funcionant, i no es canvia res. Superar-les vol dir que no es vulnera cap
   condició prèvia de dades declarada per una migració, no que l'actualització no pugui fallar
   per altres motius.

8. **Aplica la versió** mitjançant `scripts/install.sh --tag "$MEMSHIP_VERSION"`, que escriu
   `IMAGE_TAG`, descarrega i recrea la pila. Mai no sobreescriu un `.env` existent. També força la
   recreació de Caddy, cosa important: el `Caddyfile` és un bind mount, així que canviar-ne el
   contingut no dona a `docker compose up -d` cap motiu per recrear el contenidor, i altrament
   continuaria servint la configuració antiga.

9. **Verifica el resultat** amb `scripts/verify-deployment.sh`, que espera l'API, comprova que
   informa de la versió que acabes de desplegar i fa un ping al worker de Celery. Que `docker compose
   up -d` retorni només diu que s'han creat els contenidors: les migracions s'executen abans que
   l'API serveixi, així que una de fallida sembla una API que no respon mai més que no pas un
   contenidor que ha mort.

Aquesta és la mateixa ordre que el workflow de desplegament executa per SSH, deliberadament: el
que està automatitzat i el que escriu un operador no s'haurien de separar.

> El bolcat previ a l'actualització va a parar a `$MEMSHIP_DATA_ROOT/backups`, al mateix disc que
> la base de dades que protegeix. Cobreix una actualització fallida, no una màquina perduda, mira
> [Còpies de seguretat i restauració](backups-and-restore.md#còpies-fora-del-servidor) per treure'n
> còpies de la màquina.

## Actualitzar des d'una versió anterior al backend sense root

Els contenidors del backend s'executaven abans com a root, així que tot el que escrivien al
directori d'emmagatzematge quedava com a propietat de root. Ara s'executen com a
`HOST_UID`/`HOST_GID`, que és el que fa que els fitxers pujats en bind mount es puguin llegir des
de la màquina sense `sudo`, però el contenidor ja no pot escriure els fitxers que va deixar la
seva versió de l'època de root.

Pren-ne la propietat una vegada, després d'actualitzar:

```bash
sudo chown -R $(id -u):$(id -g) "$MEMSHIP_DATA_ROOT/storage"
```

`scripts/install.sh` ho detecta i mostra l'ordre exacta; executar-la a mà té el mateix efecte.

Dos canvis relacionats a la mateixa versió:

- **`uv run` ja no funciona dins dels contenidors.** En lloc d'això, el virtualenv és al `PATH`,
  així que no s'escriu res sota `/app` en temps d'execució, i això és el que permet que el
  contenidor s'executi amb qualsevol uid. Fes servir `docker compose exec api python -m …`, no
  `docker compose exec api uv run python -m …`. Qualsevol cosa que tinguis automatitzada contra
  els contenidors necessita el mateix canvi.
- **Les dades persistents han passat de volums amb nom a bind mounts** sota `MEMSHIP_DATA_ROOT`.
  Si actualitzes una instal·lació que feia servir volums amb nom, copia cadascun abans
  d'arrencar:

  ```bash
  docker run --rm -v pgdata:/from -v /srv/openmemship/data/postgres:/to \
      alpine cp -a /from/. /to/
  ```

## Migracions de la base de dades

Les migracions s'executen automàticament en arrencar el backend quan `RUN_MIGRATIONS=1` (el valor
per defecte a la pila de Compose). En una actualització estàndard no cal cap pas manual de
migració, i gairebé sempre no hi ha res a pensar aquí.

**Una migració té permès negar-se.** Algunes porten una protecció: inspeccionen les dades abans
de canviar-les i s'aturen si troben alguna cosa que només hauria de decidir una persona, per
exemple dos comptes que només es diferencien per les majúscules de l'adreça de correu, on
fusionar-los voldria dir triar un guanyador entre els accessos de dues persones. La protecció
escriu un informe que indica exactament què ha trobat, **no fa cap canvi**, i l'actualització
s'atura aquí.

Com es veu: `upgrade.sh` s'atura a les seves comprovacions prèvies a l'actualització i mostra
l'informe, indicant la migració que es negaria.

Tres coses que val la pena saber quan passa:

- **La base de dades no s'ha tocat.** Una protecció no escriu res abans de negar-se, així que no
  hi ha cap estat mig migrat. No restauris la instantània prèvia a l'actualització: no hi ha res
  a desfer, i restaurar perd tot el que s'hagi escrit des que es va prendre.
- **La teva instància continua servint.** Les comprovacions s'executen abans de substituir res,
  així que la versió que tenies continua responent mentre resols l'informe. Pren-te el temps que
  necessitis.
- **Resol les dades i torna a executar la mateixa ordre d'actualització**: no cal tornar a
  descarregar ni tornar a fixar res.

> Les actualitzacions anteriors a això executaven la comprovació en arrencar l'API, *després* de
> substituir la pila, així que un refús volia dir que l'API entrava en un bucle de fallades i els
> socis rebien errors fins que algú resolia les dades
> ([issue #194](https://github.com/marcandreuf/memship/issues/194)). Si arribes a un refús
> d'aquesta manera, perquè has executat `install.sh` directament o has actualitzat des d'una
> versió antiga, el consell sobre les dades de més amunt no canvia; simplement, la instància està
> caiguda mentre el segueixes.

[Resolució de problemes](troubleshooting.md#una-migració-sha-negat-a-executar-se-i-lapi-no-arrenca) té els passos, inclòs per què la solució és
*canviar* una fila en lloc d'eliminar-la.

Si prefereixes executar les migracions manualment, posa `RUN_MIGRATIONS=0` i executa-les tu mateix
contra el contenidor del backend després de descarregar la imatge nova.

## Tornar enrere

Per tornar enrere, torna a executar l'actualització contra la versió anterior: refresca els
fitxers des del tarball d'aquella versió i després `./scripts/upgrade.sh <older-version>`. Tornar
enrere pel mateix camí pel qual has vingut manté els fitxers del desplegament i les imatges a la
mateixa versió.

Tingues en compte que **les migracions de la base de dades no es desfan automàticament.** Si la
versió que deixes n'incloïa una, les imatges tornen enrere i l'esquema migrat no, així que
restaura el bolcat que `upgrade.sh` va prendre abans d'aplicar aquella versió, és a
`$MEMSHIP_DATA_ROOT/backups`, amb el nom per marca de temps, en lloc de limitar-te a baixar la
versió de la imatge.
