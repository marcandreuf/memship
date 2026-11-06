<!-- source: en/self-hosting/domain-and-dns.md -->
<!-- source-hash: 2d38b31431ce -->

# El domini de la teva entitat

[Installation](../../en/getting-started/installation.md) _(en anglès)_ dona per fet un nom de
màquina que ja resol cap al teu servidor. Aquesta pàgina tracta de com arribar-hi quan el domini és
d'una entitat i no teu: quin nom triar, quins registres crear, i les dues o tres maneres com surt
malament que et costen una hora cadascuna.

> **En anglès:** [Your organisation's domain](../../en/self-hosting/domain-and-dns.md).

Res d'aquí és específic del funcionament intern de memship. Si el teu DNS ja està configurat i
només vols instal·lar, ves directament a [Installation](../../en/getting-started/installation.md)
_(en anglès)_.

## Qui ha de fer què

El domini d'una associació normalment no el té la persona que fa la instal·lació. Esbrina qui té
cadascuna d'aquestes coses abans de reservar-hi un vespre: esperar l'accés al registrador és el
motiu més habitual pel qual una posada en marxa es retarda.

| Què | Qui ho sol tenir | Cal per a |
|---|---|---|
| El compte del registrador (on es va comprar el domini) | algú de la junta, o la persona que va muntar el web | res, normalment, tret que el DNS també se serveixi allà |
| La zona DNS (on s'editen els registres) | qui porti el web de l'entitat | el registre `A` per a memship |
| El correu de l'entitat | de vegades, encara un altre proveïdor | el domini d'enviament, més endavant |
| El servidor | tu | tota la resta |

El registrador i el proveïdor de DNS sovint, però no sempre, són la mateixa empresa. El que
necessites és qui pugui afegir un registre a la zona.

## Tria el nom de màquina

**Fes servir un subdomini, no el domini arrel.** `socios.myclub.org`, `members.myclub.org`,
`app.myclub.org`, el que l'entitat reconegui. El domini arrel (`myclub.org` sense prefix) gairebé
sempre apunta ja al web de l'entitat, i fer-lo apuntar a memship deixa aquest web fora de servei.

Un subdomini també vol dir que no toques mai un registre existent: n'afegeixes un, i el web
continua funcionant tota l'estona. Si alguna cosa surt malament, esborrar el registre que has
afegit ho deixa tot com estava.

> **memship respon exactament en un sol nom de màquina.** El `Caddyfile` serveix un sol lloc, el
> que s'indica a `SITE_ADDRESS`. No hi ha àlies `www` ni segon nom: `www.socios.myclub.org` no
> resoldrà, i si posessis memship al domini arrel, `www.myclub.org` tampoc no hi arribaria.
> Tria el nom que es donarà a la gent, i fes servir aquest a tot arreu.

Tria el nom abans d'instal·lar, no després. S'escriu en quatre paràmetres de configuració (l'adreça
del lloc de Caddy més les tres URL públiques que construeixen els enllaços dels correus, l'origen
CORS i la crida de retorn del proveïdor de pagament), i després es registra a mà en uns quants
llocs més; mira [Canviar-lo més endavant](#canviar-lo-més-endavant) per saber què costa.

## Els registres que cal crear

Un registre. Al teu proveïdor de DNS, a la zona de `myclub.org`:

| Camp | Valor |
|---|---|
| Tipus | `A` |
| Nom / Host | `socios` (només l'etiqueta, la majoria de proveïdors hi afegeixen el domini) |
| Valor | l'**adreça IPv4 pública** del teu servidor |
| TTL | 300 segons mentre ho estàs configurant |

Un TTL curt no costa res i fa que un error es pugui corregir en cinc minuts en lloc d'un dia.
Després, si vols, l'apuges.

### Si el servidor té IPv6

O bé afegeixes un registre `AAAA` amb l'adreça IPv6 del servidor, o bé t'assegures que el nom
**no** té cap registre `AAAA`. Totes dues opcions són vàlides. El que no és vàlid és un registre
`AAAA` que apunti a una altra banda, i en el domini d'una entitat és una possibilitat real, perquè un
comodí o un registre heretat de l'allotjament del web en pot aportar un que no has creat mai.

> **Aquest és el parany que val la pena conèixer.** `install.sh` només comprova el registre `A`,
> així que informa que tot ha anat bé. Let's Encrypt, en validar el certificat, es connecta per
> IPv6 quan existeix un registre `AAAA`, i només recorre a IPv4 quan la connexió *falla*, no quan
> funciona i retorna el que no toca. Un `AAAA` antic que apunta a un allotjament web en marxa
> respon, serveix un 404, i la validació falla. Llavors tens cinc intents fallits per hora abans
> que Let's Encrypt et faci esperar.
>
> Comprova-ho explícitament: `dig +short AAAA socios.myclub.org` hauria d'imprimir l'adreça del
> teu servidor o res de res.

### El que no s'ha de fer

- **No activis el proxy del teu proveïdor de DNS**, el núvol taronja de Cloudflare, ni cap
  interruptor de "CDN"/"proxy web" al registre. La validació del certificat ha d'arribar
  directament a la teva màquina, i el proxy acabaria ell mateix el TLS. `install.sh` avisa quan ho
  detecta, i diu de quin es tracta.
- **Un `CNAME` només funciona si, al final, resol cap a aquest servidor.** Un registre `A` és més
  senzill i una cosa menys en què pensar. A més, molts proveïdors no admeten un `CNAME` al domini
  arrel.
- **No facis servir el nom de màquina del servidor que surt al tauler del teu proveïdor**
  (`vps-12345.example-host.net`). Resol, així que la instal·lació funciona, però és seu: pot
  canviar, i els socis el tindran als navegadors i a cada enllaç dels correus.

## Comprova-ho i després instal·la

Des del servidor:

```bash
dig +short A    socios.myclub.org    # your server's IPv4
dig +short AAAA socios.myclub.org    # your server's IPv6, or nothing
curl -fsS https://api.ipify.org      # what this host's public IPv4 actually is
```

La primera i la tercera han de coincidir. La propagació sol ser qüestió de minuts; un nom que abans
resolia cap a una altra cosa pot trigar tant com el seu TTL antic.

Després instal·la amb el nom, seguint [Installation](../../en/getting-started/installation.md)
_(en anglès)_:

```bash
./scripts/install.sh --data-root /srv/openmemship/data \
                     --domain socios.myclub.org --tag 2.19.0
```

> **Deixa el port 80 obert després.** Els certificats es renoven amb la mateixa validació HTTP que
> els va emetre, aproximadament cada 60 dies, i un tallafoc que més endavant es restringeixi a
> "només el 443" trenca la renovació en silenci: te n'assabentes quan el certificat caduca.
> `vps-bootstrap.sh` obre el 80 i el 443, i tots dos s'han de quedar oberts.

Si el DNS encara no està a punt i igualment vols tenir la plataforma en marxa, instal·la sense
`--domain` i afegeix-lo en una execució posterior. És el camí d'assaig documentat, i
[Installation](../../en/getting-started/installation.md#without-a-domain) _(en anglès)_ explica per
què, a més, t'estalvia gastar certificats.

## El correu és una decisió de domini a part

L'adreça des de la qual envia memship **no** ha de ser, i normalment no hauria de ser, al subdomini
que acabes de crear. Els socis reconeixen `no-reply@myclub.org`; ningú no reconeix
`no-reply@socios.myclub.org`.

Això vol dir un segon conjunt de registres DNS, sense relació amb l'anterior:

- El registre `A` del lloc fa que l'aplicació sigui accessible. No fa res pel correu.
- Un domini d'enviament necessita els registres que demani el teu proveïdor de correu: amb Resend,
  un registre DKIM més una parella SPF/MX en un subdomini `send.`. El recorregut és a
  [Integracions → Correu](../admin-guide/integrations.md#4-correu), i
  [Enviament de correu](email.md) explica com triar entre Resend i SMTP.

Dues coses per acordar amb qui porti el correu de l'entitat, perquè són seves i no teves:

- **Des de quina adreça envia memship**, i que sigui d'un domini on puguin afegir registres.
- **Si el domini publica una política DMARC.** Si en publica, un servei d'enviament nou s'hi ha
  d'alinear o se'n ressent la reputació del correu de la mateixa entitat. Afegir memship com a
  remitent és un canvi a la seva configuració de correu, no només a la teva.

El correu que no funciona és invisible per disseny: [Enviament de correu](email.md) explica que,
sense cap proveïdor actiu, els enviaments s'ometen i es registren al log en lloc de posar-se a la
cua o d'informar-ne. Envia un missatge de prova des de la pantalla de configuració abans de dir a
ningú que la instància ja està en marxa, i recorda que els socis no poden iniciar sessió fins que
funcioni el correu, perquè primer confirmen la seva adreça.

## Canviar-lo més endavant

Tornar a executar `install.sh --domain <new-name>` actualitza `SITE_ADDRESS` i les tres URL
públiques alhora, així que no queda res apuntant al servidor antic. El que no pot actualitzar és tot
el que hi ha fora de memship i que coneixia el nom antic:

| On | Què es trenca |
|---|---|
| SSO de Google / Apple | l'URI de redirecció es registra per nom de màquina i ha de coincidir exactament, o l'inici de sessió falla. [Integracions → SSO](../admin-guide/integrations.md#3-inici-de-sessió-únic-sso) |
| Webhooks de Stripe | la URL de l'endpoint està registrada al tauler de Stripe. **Edita l'endpoint existent** en lloc de crear-ne un: una destinació nova genera un secret de signatura nou, memship en desa un, i llavors tots els esdeveniments fallarien la verificació, cosa que sembla exactament un pagament que no arriba mai i en silenci |
| Correus ja enviats | els seus enllaços continuen apuntant al nom de màquina antic mentre aquest resolgui |
| Adreces d'interès dels socis | el nom antic ha de continuar resolent, o redirigint, tant de temps com t'importi |

Redsys no necessita cap canvi: memship envia la URL de la crida de retorn amb cada transacció en
lloc de tenir-la registrada.

Res d'això és difícil, però és per això que triar el nom de màquina una sola vegada, abans de la
posada en marxa, val deu minuts de reflexió.

## Mira també

- [Installation](../../en/getting-started/installation.md) _(en anglès)_, la instal·lació en si, i
  els avisos sobre el límit de certificats que val la pena llegir abans del primer intent
- [Primera posada en marxa](../getting-started/first-setup.md), el que l'entitat ha de decidir un
  cop la instància està en marxa
- [Referència de configuració](configuration.md), `SITE_ADDRESS`, `FRONTEND_URL`, `CORS_ORIGINS`,
  `BACKEND_PUBLIC_URL` i la resta
- [Resolució de problemes](troubleshooting.md), quan la plataforma està en marxa però el lloc no és
  accessible
