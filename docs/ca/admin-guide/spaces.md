<!-- source: en/admin-guide/spaces.md -->
<!-- source-hash: 724f69b7d567 -->

# Espais i reserves

Els espais són els recursos que el club posa a reservar: una pista, una sala, un carrer de
piscina. Cada espai té un horari i **franges** amb data, i els socis reserven una franja des de
**Reservar**, al portal del soci. Els espais apareixen quan el mòdul de **reserves** està activat.

> **In English:** [Spaces and bookings](../../en/admin-guide/spaces.md).
> **En español:** [Espacios y reservas](../../es/admin-guide/spaces.md).

## Espais i franges

Un espai té nom, tipus, horari d'obertura, un **preu** opcional per reserva (abans d'impostos) i,
si es vol, els tipus de soci que el poden reservar. Una franja és una data i una hora dins
d'aquest horari, amb una **capacitat** (quants socis la poden tenir alhora) i, si és diferent del
de l'espai, el seu propi preu; un preu de 0 és una franja gratuïta en un espai de pagament. Una
regla de repetició crea tota una sèrie de franges de cop.

**Desactivar** un espai l'amaga als socis i ho conserva tot. **Esborrar** una franja o un espai
elimina les seves reserves per sempre, així que es rebutja mentre alguna tingui diners pel mig:
una reserva pagada la franja de la qual encara no ha arribat, o una de cancel·lada amb una
devolució pendent. Cancel·la-les abans, amb la qual cosa queda registrat el que es deu, o
desactiva en lloc d'esborrar.

## Pagament i confirmació de la reserva

En un espai de pagament, la reserva queda **pendent de pagament** fins que es paga el seu
[rebut](payments.md): ocupa plaça, però no està confirmada. Es confirma sola quan es registra el
pagament, sigui per passarel·la, per transferència o en efectiu. Un espai gratuït o una franja
gratuïta es reserven a l'instant.

- **Formes de pagament acceptades.** Targeta, Bizum, transferència o efectiu. Un espai amb preu
  en necessita almenys una, i només s'ofereixen les que el club pot cobrar avui: la targeta
  necessita Stripe o Redsys actius, Bizum un Redsys amb Bizum activat i la transferència l'IBAN
  del club. Al soci només se li ofereixen les que accepta l'espai, als correus i a *Els meus
  rebuts*.
- **Confirmar sense pagament.** Des de la pestanya **Reserves** de l'espai, confirma una reserva
  pendent i anul·la el seu rebut. Queda registrat qui ho ha fet.
- **Marcar un pagament rebut.** La columna de pagament enllaça amb el rebut, on es marca pagada
  una transferència o un pagament en efectiu; la reserva es confirma sola.
- **Cancel·lar una reserva pagada.** Passa a **Devolucions** llevat que marquis *Quedar-se el
  pagament*. La devolució es fa des de la passarel·la o a mà; memship només la registra com a
  retornada. El soci rep un correu que li diu que se li retornarà l'import.
- **Pagament tardà.** Si la passarel·la cobra una reserva ja alliberada, la reserva torna si la
  franja no ha començat i hi ha lloc; si no, l'import passa a devolucions. En tots dos casos
  s'avisa el club per correu i al tauler.

Els espais creats abans d'aquesta manera de treballar porten la marca **legacy**: confirmen la
reserva a l'instant i el rebut es cobra després. A diferència d'una activitat, un espai legacy es
pot passar al flux nou des del seu formulari d'edició. El canvi no es pot desfer, i només
segueixen el flux nou les reserves que es facin després.

### El termini de pagament

Tota reserva pendent té un termini, perquè una franja és per a una data concreta i sovint per a
demà. A **Configuració › Pagaments › General**, a *Reserves de pagament*, el club fixa:

- **Marge abans de la franja** (60 minuts per defecte): una reserva pendent s'ha de pagar com a
  molt tard aquest temps abans que comenci la franja. Cap reserva arriba a la seva franja sense
  pagar. Posa-ho a 0 si cobres en efectiu a la porta i ho marques pagat abans de començar.
- **Temps mínim per pagar** (15 minuts per defecte): una reserva que tindria menys temps es
  rebutja, i se li diu al soci per què. Les franges massa a prop del seu inici es mostren com que
  ja no es poden reservar.
- **Alliberar abans les reserves no pagades** (desactivat per defecte, 24 hores): si s'activa,
  una reserva pendent també s'allibera si no es paga en aquest temps, el que arribi abans. Cada
  espai pot seguir el club, activar-ho o desactivar-ho, o canviar el temps. En activar-ho, les
  reserves ja pendents avancen el seu termini i s'avisa els seus socis.

Al soci se li mostra el termini abans de reservar, el rep al correu i se l'avisa un cop abans que
venci. Una reserva que no es paga a temps es cancel·la, el seu rebut s'anul·la i s'avisa el soci.

### Llista d'espera

Quan s'allibera una plaça en una franja de pagament, el que passa depèn del temps que tindria per
pagar-se una reserva feta en aquell moment:

| Temps per pagar | Què passa |
|---|---|
| Almenys el *temps mínim per donar la plaça sola* (120 minuts per defecte) | La plaça passa al primer de la llista d'espera, pendent de pagament, i se li diu com i fins quan ha de pagar |
| Entre el *temps mínim per pagar* i aquest | No es promociona ningú. Tota la llista d'espera rep un correu que hi ha una plaça lliure; se la queda qui la reservi i pagui primer |
| Menys que el *temps mínim per pagar* | La plaça es queda lliure |

En una franja gratuïta o legacy, la plaça lliure passa al primer de la llista, com abans.

### Correus

Un espai de pagament allibera les reserves no pagades, així que només pot cobrar mentre estiguin
activats els correus *Reserva pendent de pagament*, *Avís de termini d'una reserva* i *Reserva
cancel·lada per manca de pagament* a **Configuració › Socis › Comunicacions**. Pel mateix motiu,
mentre existeixi un espai de pagament aquests correus no es poden desactivar. Una instal·lació
nova els porta activats, juntament amb *Plaça alliberada a última hora*, que porta l'avís a la
llista d'espera.

## Política de cancel·lació

Cada espai té la seva pròpia política de cancel·lació, diferent de la de les activitats. El termini
de devolució es fixa en minuts, hores o dies abans de l'inici d'una franja; si es deixa buit,
l'espai segueix el valor per defecte del club (**Ajustos › Reserves**, 24 hores tret que es canviï).

- **Abans del termini** el soci que cancel·la allibera la plaça, i un pagament ja fet es marca com
  a *devolució pendent*.
- **Passat el termini** tries **Rebutjar la cancel·lació** (per defecte) o **Permetre-la; el club es
  queda el pagament**. En el segon cas la plaça queda lliure, el rebut continua pagat i no es deu
  res. *Les meves reserves* avisa el soci abans de confirmar.
- **Quan cancel·les tu** una reserva, tries si el pagament es retorna. Quan elimines una franja o un
  espai, les reserves amb diners es cancel·len abans i sempre s'han de retornar, perquè la causa és
  del club.
- Una reserva que mai no es va pagar no té res a retornar. Una reserva pendent sempre pot ser
  alliberada pel seu soci fins al seu termini de pagament.

## Devolucions i pagaments tardans

**Devolucions**, a la qual s'arriba des d'Activitats o des d'Espais, llista totes les
inscripcions i reserves cancel·lades el pagament de les quals cal retornar, amb la forma de
pagament i la referència de la passarel·la. Marca cadascuna com a retornada quan els diners
s'hagin retornat. Els pagaments que arriben després que s'hagi alliberat la seva plaça apareixen
a més com a avís al tauler fins que algú els revisa.
