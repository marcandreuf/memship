<!-- source: en/self-hosting/email.md -->
<!-- source-hash: 16d2ae445324 -->

# Enviament de correu

Memship envia correu transaccional per confirmar adreces, restablir contrasenyes, confirmar
inscripcions a activitats, avisar de promocions des de la llista d'espera, enviar rebuts de pagament
i avisar de rebuts vençuts. **El correu està desactivat fins que configures un transport.**

> **En anglès:** [Email delivery](../../en/self-hosting/email.md).

Hi ha dues maneres de configurar-ne un, i **no són equivalents**: la pantalla de configuració mana
sobre el `.env`. Llegeix [Quin està en vigor](#quin-està-en-vigor) abans de tocar res, sobretot en
una instal·lació que ja està en marxa.

| On | Proveïdors | El millor per a |
|-------|-----------|----------|
| **Configuració → Integracions → Correu** | Resend, qualsevol servidor SMTP (Gmail és una configuració predefinida) | Gairebé tothom. S'aplica a la petició següent, sense reiniciar. |
| **`.env`** | Resend, qualsevol servidor SMTP | Deixar les credencials posades en el moment de desplegar, i les instal·lacions anteriors a la pantalla de configuració. |

SMTP vol dir un servidor que accepti **STARTTLS**, normalment al port 587, o sense cap xifratge.
Un servidor accessible només pel port 465, que xifra des del primer byte, no és compatible.

## Opció A: la pantalla de configuració

Entra com a superadministrador i ves a **Configuració → Integracions → Correu**.

El recorregut complet (com obtenir les credencials, els registres DNS que necessita Resend, les
dades del teu servidor SMTP o una contrasenya d'aplicació de Gmail, el botó **Envia una prova** i
una taula de resolució de problemes) és a la
[guia de configuració d'integracions, secció 4](../admin-guide/integrations.md#4-correu). Val la pena
repetir-ne aquí dos punts, perquè són els que fan mal sense fer soroll:

- **Desar les credencials no les activa.** La insígnia de la targeta passa a *A punt*, no a
  *Actiu*. Després has de triar el selector **Proveïdor actiu** i tornar a desar. Configura →
  prova → activa, en aquest ordre. L'ordre és obligatori: un proveïdor no es pot activar fins que
  ha funcionat un enviament amb les credencials que té desades ara.
- **Sense cap proveïdor actiu, el correu s'omet en silenci**: es registra al log, no es posa a la
  cua i no dona cap error. Res de la interfície informa d'un enviament que no s'ha fet mai.

Cada targeta de proveïdor mostra també si se sap que les seves credencials funcionen: *Sense
verificar*, *Funciona* o *Falla* amb un motiu. S'actualitza amb cada correu enviat per aquell
proveïdor, inclosa la prova, i val també per a les credencials que venen del `.env`.

Els correus d'aprovació i de rebuig s'envien en el moment en què l'administrador decideix, de
manera que se li pot dir si han sortit. Si no s'ha pogut contactar amb el proveïdor o s'ha arribat
al seu límit d'enviament, es tornen a intentar automàticament al cap d'1, 5 i 25 minuts, i el
missatge d'aprovació ho diu. Qualsevol altra fallada, com unes credencials rebutjades, s'informa
de seguida i no es reintenta, perquè tornaria a fallar de la mateixa manera. Els reintents
s'executen al servei `worker`, que ha d'estar en marxa.

## Opció B: `.env`

Defineix les variables i torna a crear el backend perquè les agafi:

```bash
docker compose up -d --force-recreate api
```

**Resend:**

```bash
RESEND_API_KEY=re_your_key_here
RESEND_FROM_EMAIL=noreply@yourdomain.org
```

**SMTP** (qualsevol servidor, Gmail inclòs; per a Gmail fes servir `smtp.gmail.com` i una
contrasenya d'aplicació):

```bash
SMTP_HOST=smtp.yourprovider.com
SMTP_PORT=587
SMTP_USER=your-username
SMTP_PASSWORD=your-password
SMTP_FROM=noreply@yourdomain.org
SMTP_TLS=true
```

La correspondència completa entre camp de la pantalla i variable d'entorn és a la
[guia de configuració d'integracions, secció 6](../admin-guide/integrations.md#6-alternativa-amb-el-fitxer-de-configuració-env).

## Quin està en vigor

Tres casos, i la diferència importa:

| Situació | Què envia |
|-----------|------------|
| **La pantalla Correu no s'ha desat mai** | Els valors del `.env`, exactament com s'ha descrit més amunt: Resend si hi ha `RESEND_API_KEY`, si no SMTP si hi ha `SMTP_HOST`, i si no res. |
| **La pantalla s'ha desat i s'ha triat un proveïdor actiu** | Aquell proveïdor. Camp per camp, un valor desat a la pantalla mana; un camp que s'hi ha deixat buit recorre a la variable d'entorn corresponent. |
| **La pantalla s'ha desat però no s'ha triat cap proveïdor actiu** | **Res.** El correu s'omet en silenci, digui el que digui el `.env`. |

La [plataforma d'inici ràpid](../../en/getting-started/quickstart.md#5-try-a-member-joining)
_(en anglès)_ es basa en la primera fila: el seu fitxer compose apunta `SMTP_HOST` a una safata de
proves local, així que desar la pantalla substitueix la safata de proves pel proveïdor que s'hi
triï, o per res si no se'n tria cap.

La conseqüència a vigilar: un cop algú ha desat la pantalla Correu, **editar el `.env` pot no tenir
cap efecte visible**, perquè el valor desat mana i no es genera cap error. Si vas configurar Resend
a la pantalla i després canvies `RESEND_API_KEY` al `.env`, s'hi continua enviant amb la clau
antiga. Buida el camp a la pantalla per recórrer al valor de l'entorn.

La pantalla marca els camps que està llegint de l'entorn amb la insígnia **"de l'entorn"**, que és
la manera més ràpida de veure quina font està activa. El port i el TLS sempre tenen un valor, 587 i
activat, així que només porten la insígnia quan `SMTP_PORT` o `SMTP_TLS` estan definits de debò.

**Si actualitzes des d'una versió que oferia "Gmail" com a proveïdor:** sempre va ser el transport
SMTP, i ara s'anomena així. El correu continua anant on anava:

- Una instal·lació que havia configurat Gmail a la pantalla passa a ser el proveïdor SMTP amb el
  servidor de Google (`smtp.gmail.com`, port 587, STARTTLS) desat explícitament. No passa a seguir
  `SMTP_HOST`.
- Una instal·lació configurada només amb el `.env` continua fent servir el seu `SMTP_HOST`, i ara
  apareix com a SMTP en lloc de Gmail.

En tots dos casos, la targeta indica *Sense verificar* fins que passi el correu següent, perquè el
seu registre d'estat pertanyia al proveïdor antic. Mentrestant continua activa.

## Comprovar-ho

Provoca un enviament real per confirmar el lliurament, per exemple, demana un **restabliment de
contrasenya** des de la pàgina d'inici de sessió, o aprova un registre pendent i comprova que arriba
el correu d'aprovació. Els correus es localitzen (ES/CA/EN) segons l'idioma del destinatari.

Si ho has configurat des de la pantalla de configuració, fes servir preferentment el seu botó
**Envia una prova**: envia a través d'un proveïdor concret encara que no sigui l'actiu, així que
pots verificar les credencials abans de passar-hi el trànsit real.

Fes la prova de restabliment amb un compte de soci o d'administrador del club. Els
superadministradors queden fora d'aquest flux a propòsit (la seva contrasenya es restableix des del
servidor amb `python -m app.cli.seed`, mira
[Recuperar la contrasenya del superadministrador](../getting-started/first-setup.md#recuperar-la-contrasenya-del-superadministrador)), així que
provar-ho amb un d'ells sembla correu que no arriba mai.

## El que un soci pot desactivar

Cada soci té al seu perfil l'interruptor **Rebre correus del club**. Cobreix les plantilles
`optional`, les confirmacions de reserves i d'activitats i els anuncis del club, i res més:

| Nivell | Exemples | Baixa del soci |
|---|---|---|
| Obligatori | confirmació de l'adreça, restabliment de contrasenya | no s'hi aplica mai |
| Operatiu | rebuts, recordatoris de pagament, una reserva cancel·lada | no s'hi aplica mai |
| Opcional | confirmacions de reserves i d'inscripcions, anuncis | s'hi aplica |

Un soci que es dona de baixa continua rebent les seves factures i els avisos que precedeixen un
deute, que un club pot estar obligat a enviar. El personal pot canviar l'interruptor en nom d'un
soci des de la seva fitxa, per a algú que ho demani a la recepció o que no tingui accés al portal.

Quines plantilles van a cada nivell es veu a **Configuració → Socis → Comunicacions**, i primer es
comprova l'interruptor de la mateixa entitat: una plantilla desactivada allà no s'envia a ningú,
triï el que triï el soci.

A part dels correus obligatoris, les plantilles comencen **desactivades**, amb una excepció: una
instal·lació nova comença amb el correu d'**aprovació del registre** activat, perquè una persona
sol·licitant aprovada no té cap altra manera de saber que l'han admesa. Es pot desactivar com
qualsevol altra. Una instal·lació creada abans que existís aquest valor per defecte conserva el que
tenia; si els correus d'aprovació no arriben mai, comprova primer aquest interruptor. Aprovar un
registre també indica a l'administrador si el correu s'ha enviat, està desactivat o ha fallat, i
per què.

## Els socis no poden entrar fins que funcioni el correu

Per iniciar sessió cal una adreça confirmada, i l'única manera de confirmar-la pel teu compte és
l'enllaç que s'envia en registrar-se. Així que, fins que no es configura un proveïdor:

- **L'autoregistre es rebutja**, amb un missatge que diu al visitant que contacti amb el club, en
  lloc de crear un compte que el seu titular no podria fer servir mai.
- **Un soci que es va registrar abans i no va confirmar mai** apareix com a *actiu* i no pot
  iniciar sessió. Obre la seva fitxa de soci: indica que l'adreça no està confirmada i ofereix
  **Confirmar adreça**. Això requereix `users.write`, i queda registrat al registre d'auditoria
  com a confirmat per un administrador i no pel soci; confirma només una adreça que hagis
  comprovat per una altra via que és seva.
- Des del servidor, el mateix sense la interfície:
  `python -m app.cli.verify_email --email someone@example.org`, o `--list` per veure qui està
  esperant.

Un proveïdor que està *configurat però espatllat*, per exemple amb una clau d'API incorrecta, no
el detecta la protecció del registre: sembla utilitzable i falla al transport. Aquests socis es
queden encallats de la mateixa manera, i **Confirmar adreça** és la sortida.

## Resolució de problemes

- **No arriba cap correu**: comprova-ho en aquest ordre. (1) **Configuració → Integracions →
  Correu**: el *Proveïdor actiu* té un valor diferent de *Cap*? Un proveïdor desat però no activat
  no envia res. (2) Si la pantalla no s'ha fet servir mai, confirma que `RESEND_API_KEY` o
  `SMTP_HOST` estan definits al `.env`; si no n'hi ha cap dels dos, el correu està desactivat
  intencionadament.
- **Canviar el `.env` no ha fet res**: la pantalla Correu té un valor desat per a aquell camp, i
  mana. Mira [Quin està en vigor](#quin-està-en-vigor).
- **Resend rebutja l'enviament (403, "domain is not verified")**: l'adreça del remitent no és
  d'un domini verificat a Resend, o els seus registres DNS encara no s'han propagat. Resend
  rebutja qualsevol adreça de remitent de fora d'un domini verificat. L'única excepció és
  `onboarding@resend.dev`, que no necessita domini però **només lliura a l'adreça propietària del
  compte de Resend**: serveix per a una prova, no per a trànsit real.
- **Els correus arriben amb retard**: l'enviament és asíncron mitjançant Celery. Mira els logs del
  worker: `docker compose logs -f worker`.
- **Els enllaços apunten a un servidor equivocat**: defineix `FRONTEND_URL` amb la URL pública del
  teu lloc (mira la [referència de configuració](configuration.md)).
