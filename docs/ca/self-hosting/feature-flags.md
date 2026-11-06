<!-- source: en/self-hosting/feature-flags.md -->
<!-- source-hash: 70b6870a042d -->

# Feature flags

Memship porta tots els mòduls en una sola imatge. Quins fa servir realment una entitat ho decideixen
**vint-i-una claus** en una única columna JSONB, `organization_settings.features`, a l'única fila
que admet la base de dades (`CHECK (id = 1)`). S'editen des de **Configuració** al portal
d'administració, no des del `.env` ni des d'un fitxer del servidor. Res d'això necessita reiniciar.

> **En anglès:** [Feature flags](../../en/self-hosting/feature-flags.md).

Aquesta pàgina existeix perquè "el flag no hi és" i "el flag està desactivat" són el mateix per a
l'aplicació però no per a una persona que llegeix una pantalla, i fins que no es va posar per escrit
no hi havia manera de distingir un mòdul que ningú no havia activat d'un mòdul espatllat.

## Amb què comença una instal·lació nova

**Dues de les vint-i-una.** Totes les altres no hi són.

| Definida | Per què |
|---|---|
| `custom_roles` | La capa de permisos sempre està activa; amagar l'única pantalla que la pot ajustar no ajuda ningú. |
| `gender_options` | Cinc opcions sembrades, perquè el formulari de soci tingui alguna cosa per oferir des del primer dia. |

És deliberat, no un descuit. Un club activa cada mòdul quan hi està preparat, i `install.sh`
produeix exactament aquest estat. Això sí, vol dir que el primer arrencament es veu escàs: **set
rutes redirigeixen al tauler** fins que no s'activa el seu mòdul.

| Ruta | Necessita |
|---|---|
| `/communications`, `/announcements` | `communications` |
| `/spaces`, `/book`, `/my-bookings` | `bookings` |
| `/scan`, `/my-card` | `member_card` |

Un mòdul desactivat també **respon 404 als seus propis endpoints**, i per això el frontend
redirigeix en lloc de mostrar una carcassa damunt d'una API morta.

**Que no hi sigui no sempre vol dir que estigui desactivat.** Dues claus valen *activat* per
defecte quan falten, `public_registration` i `registration_requires_approval`, que totes dues es
llegeixen com `features.get(key, True)` a `domains/auth/service.py`. Així que en una instal·lació
nova el registre està obert *per política*, i cada registre va a parar a la cua de pendents
d'aprovació en lloc de convertir-se en un soci actiu. Si no vols un formulari de registre obert,
posa `public_registration` a `false` explícitament: treure la clau fa el contrari del que sembla.

Obert per política no vol dir que funcioni. `POST /auth/register` es nega amb **503, "the club has
not finished setting up email"** fins que es configura un transport de correu, perquè confirmar
una adreça necessita un enllaç i l'enllaç necessita un transport. És deliberat: és millor que crear
un compte amb què ningú no podrà iniciar sessió mai. En una instal·lació autoallotjada nova és la
resposta que rep qualsevol visitant, així que el formulari de registre està obert a Configuració i
tancat a la pràctica fins que no configures Resend o SMTP. Comprovat en una instal·lació neta, no
deduït.

## Vols una instància ja configurada?

```bash
python -m app.cli.seed --demo     # or: ./scripts/dev.sh seed demo
```

El camí de demostració activa **totes vint-i-una** i omple al darrere les dades d'un club sencer. És
per avaluar i revisar, mai per a una entitat real, perquè també crea socis i rebuts de demostració.

> **També arma les tasques programades.** `recurring_billing_enabled`,
> `payment_reminders_enabled` i `membership_lapse_enabled` són interruptors que una tasca de
> Celery beat llegeix a les 02:00, 03:00 i 04:00 UTC. Mentre estan activats, una instància en
> marxa genera rebuts, marca com a vençuts els impagats i passa al nivell gratuït els socis amb la
> quota caducada. Es comporta correctament, però les seves dades no seran exactament com les vas
> deixar.
>
> **La caducitat no suspèn ningú.** Un soci caducat és un soci de ple dret al nivell gratuït:
> `Member.status` no es toca a propòsit, i el nivell anterior es guarda a
> `Member.membership_reverted_from_id` perquè pagar la quota el restitueixi (mira
> `lapse_service.py` i memship#145). Per tant, els recomptes per estat de soci del tauler no es
> mouen quan s'executa una caducitat.
>
> **Són hores UTC, i l'UTC no és la teva jornada laboral.** A UTC+9 s'executen a les 11:00, 12:00
> i 13:00, en plena jornada del matí, no de nit. Si estàs revisant o fent una demostració d'una
> instància i vols que les seves dades es quedin quietes, desactiva aquestes tres mentre duri. Només
> controlen feina programada i no tenen pantalla pròpia, així que no perds res que puguis veure.

## Les vint-i-una

En aquesta columna hi viuen tres menes de coses diferents, i no es comporten igual.

- **Portes**: desactivades, una petició es rebutja. Són les que redirigeixen.
- **Valors**: parametritzen el comportament en lloc de barrar-lo. Si un no hi és, recorre a un
  valor per defecte escrit al codi, així que la instància *ja funciona amb aquest número* tant si
  la clau existeix com si no.
- **Dades**: una llista, validada entrada per entrada en desar-la.

| Clau | Tipus | Si no hi és | Controla |
|---|---|---|---|
| `custom_roles` | porta | desactivat | la pestanya de configuració Comptes/Rols |
| `communications` | porta | desactivat | `/communications`, `/announcements` |
| `member_card` | porta | desactivat | `/scan`, `/my-card` |
| `bookings` | porta | desactivat | `/spaces`, `/book`, `/my-bookings` |
| `custom_profile_fields` | porta | desactivat | camps personalitzats del soci |
| `public_registration` | porta | **activat** | l'autoregistre, però respon 503 fins que es configura el correu |
| `registration_requires_approval` | porta | **activat** | la cua de pendents d'aprovació |
| `payment_reminders_enabled` | porta | desactivat | la tanda de reclamacions i els recordatoris manuals |
| `recurring_billing_enabled` | porta | desactivat | la tanda programada de quotes de soci |
| `membership_lapse_enabled` | porta | desactivat | la tanda programada que retorna els socis caducats al nivell gratuït |
| `reminder_days_after_due` | valor | **3** | dies després del venciment abans del primer recordatori |
| `reminder_repeat_days` | valor | **7** | dies entre repeticions |
| `reminder_max_count` | valor | **3** | recordatoris per rebut |
| `recurring_billing_day` | valor | **1** | dia del mes en què emet la tanda de facturació |
| `membership_fee_due_days` | valor | **7** | dies des de l'emissió fins al venciment |
| `membership_lapse_grace_days` | valor | **21** | dies després del venciment abans que un soci caduqui |
| `booking_window_days` | valor | **14** | amb quanta antelació pot reservar un soci (1–365) |
| `booking_cancellation_deadline_hours` | valor | **24** | límit per cancel·lar (0–8760) |
| `booking_waitlist_enabled` | valor | **activat** | si una franja plena ofereix llista d'espera |
| `billing_notification_email` | valor | *sense definir* | on van els resums de les tandes de facturació i el resum diari de notificacions de pagament; no fa res si no està definit, i es valida com a adreça en desar |
| `gender_options` | dades | no s'ofereix cap opció | el camp de gènere del formulari de soci |

Els valors per defecte de més amunt són els valors de reserva literals de `reminder_service.py`,
`recurring_billing_service.py`, `lapse_service.py` i `bookings/rules.py`. Dues proves de
`backend/tests/integration/test_demo_data.py` els protegeixen: una fixa els sis valors numèrics per
defecte contra el que escriu la sembra de demostració, i l'altra fixa els tres flags que estan
**activats quan no hi són**.

Cal ser precís sobre què cobreix i què no: totes dues comparen *codi* amb *codi*. Cap de les dues
no llegeix aquesta pàgina, així que una fila d'aquí encara pot divergir del valor de reserva que
descriu, que és el que va passar amb `booking_waitlist_enabled`, que figurava com a desactivat tot
el temps que el codi el va tenir activat per defecte.

## Desactivar-ne un no és el mateix que no haver-lo activat mai

Un **valor** no té estat desactivat ni redirecció. Posar `reminder_max_count` a alguna cosa fora de
rang és una situació diferent de deixar-lo absent: cada valor es valida contra el seu rang en desar-lo i es rebutja
amb un 422, i els que es llegeixen a través d'un registre també recorren al seu
valor per defecte en lloc de fallar si una instància més antiga ja en té un de dolent desat. Si
estàs revisant aquesta àrea, un valor s'ha de mirar pel que fa *què fa la pantalla amb un número
sense sentit*, cosa que les portes no necessiten gens.

## Es rebutja qualsevol clau que aquesta pàgina no llisti

Les vint-i-una de més amunt són el conjunt sencer, i `PUT /api/v1/settings/` respon **422** a
qualsevol altra, indicant la clau que no ha reconegut.

Això importa si configures una instància a través de l'API en lloc de les pantalles
d'administració. Abans que s'apliqués, un nom de flag mal escrit s'acceptava, es desava i no feia
res en silenci: l'actualització fusiona de manera parcial, així que qualsevol clau que portés la
petició s'escrivia i es quedava per sempre, sense res enlloc que digués que la configuració no tenia
cap efecte. `booking_window_day` per `booking_window_days` va costar exactament això.

Dues conseqüències que val la pena conèixer:

- **Que una clau no hi sigui continua estant bé.** La norma és que es rebutja una clau desconeguda,
  no que calguin totes les conegudes. Una instal·lació nova en desa un subconjunt i la resta es
  resolen amb els valors per defecte de la taula de més amunt.
- **Envia només les claus que canvies.** Una clau que ja era a la columna d'abans que s'apliqués
  això es deixa tal com està, així que una instància que en tingui una continua funcionant, però un
  client que llegeix tot el diccionari `features` i el torna a enviar reenvia aquesta clau i serà
  rebutjat. Tornar a enviar una instantània no ha calgut mai, perquè l'endpoint fusiona.

Si necessites un lloc on posar valors propis, `custom_settings` és una columna a part de la mateixa
fila i hi accepta qualsevol cosa.

## Una coincidència de noms que val la pena conèixer

`activities.features` és una **columna diferent** d'una taula diferent, i conté una clau
`waiting_list`. Un grep de `features` troba totes dues. Res d'`organization_settings.features` no
s'anomena `waiting_list`, i la clau del nivell d'activitat no té res a veure amb
`booking_waitlist_enabled`.

## Relacionat

- [Referència de configuració](configuration.md), les variables d'entorn, que són un mecanisme
  completament a part
- [Primera posada en marxa](../getting-started/first-setup.md)
