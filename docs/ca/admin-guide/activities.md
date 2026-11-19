<!-- source: es/admin-guide/activities.md -->
<!-- source-hash: c7247c2fcf3e -->

# Activitats

Les activitats són esdeveniments, cursos, tallers o competicions als quals els socis es poden
inscriure. Cada activitat pot tenir modalitats, nivells de preu i regles d'elegibilitat.

> **En castellà:** [Actividades](../../es/admin-guide/activities.md).

## Crear una activitat

En crear una activitat configures:

- **Informació bàsica**, nom, descripció i descripció breu.
- **Dates**, inici i fi de l'activitat, i el **període d'inscripció** (obertura i tancament).
- **Ubicació**, amb detalls i URL opcionals.
- **Capacitat**, mínim i màxim de participants.
- **Elegibilitat**, interval d'edat (edat mínima/màxima).
- **Cancel·lació**, permetre o no la cancel·lació per part del soci, i el termini (hores abans de
  l'inici).
- **Imatge de portada**, visible per als socis com a miniatura.

## Estats i publicació

Una activitat passa pels estats **Esborrany → Publicada → Arxivada** (a més de *Cancel·lada* i
*Completada*). Només les activitats **publicades** són visibles per als socis. Fes servir les
accions **Publicar**, **Arxivar** i **Cancel·lar activitat** segons correspongui.

## Modalitats

Les **modalitats** són variants d'una mateixa activitat, cadascuna amb la seva pròpia
**capacitat**, **preu** i **data límit d'inscripció** (p. ex. diferents grups de nivell o torns).

## Preus

Pots definir diversos **preus**, a nivell d'activitat o de modalitat, amb **validesa temporal**
(*vàlid des de / fins a*) per configurar, per exemple, tarifes d'inscripció anticipada. Un preu es
pot marcar com a **per defecte** o **opcional**, i un import de 0 es mostra com a **Gratuït**.

## Descomptes

Els **codis de descompte** poden ser de tipus **percentatge** o **import fix**, amb un nombre
**màxim d'usos** (o il·limitat) i dates de validesa. El soci introdueix el codi en inscriure's.

## Consentiments

Cada activitat pot requerir **consentiments** (obligatoris o opcionals) que el soci ha d'acceptar
durant la inscripció. S'ordenen i s'editen des de la pestanya corresponent.

## Documents adjunts

Pots definir **tipus de document** que el soci ha d'adjuntar en inscriure's, indicant les
**extensions permeses**, la **mida màxima** i si són obligatoris.

## Inscripcions

Des de la pestanya **Inscripcions** veus els socis inscrits i el seu estat: **Confirmat**, **En
espera**, **Pendent de pagament** o **Cancel·lat**. Si actives la **llista d'espera** a
l'activitat, quan s'omple les noves inscripcions hi passen i es promocionen, per ordre, quan
s'alliberen places. Pots **canviar l'estat** d'una inscripció manualment.

## Pagament i confirmació de la plaça

En una activitat de pagament la plaça queda **pendent de pagament** fins que es cobra el seu
[rebut](payments.md): ocupa aforament, però no està confirmada. Es confirma sola quan es registra
el pagament, sigui per passarel·la, per transferència o en efectiu. Una activitat gratuïta, o un
preu 0, confirma al moment.

- **Formes de pagament acceptades.** Targeta, Bizum, transferència o efectiu. Una activitat de
  pagament en necessita almenys una per publicar-se, i només s'ofereixen les que el club pot
  cobrar avui: la targeta necessita Stripe o Redsys actiu, Bizum un Redsys amb Bizum habilitat i
  la transferència l'IBAN del club. Al soci només se li ofereixen les que accepta l'activitat, als
  correus i a *Els meus rebuts*.
- **Confirmar sense pagament.** Confirma una plaça pendent i anul·la el seu rebut. Queda
  registrat qui ho ha fet.
- **Cancel·lar una plaça pagada.** Passa a **Activitats › Devolucions** llevat que marquis
  *Quedar-se el pagament*. La devolució es fa des de la passarel·la o a mà; a memship només es
  marca com a retornada. Cancel·lar des del tauler avisa el soci per correu.
- **Pagament tardà.** Si la passarel·la cobra una plaça ja alliberada, la plaça es recupera si
  queda aforament; si no, l'import passa a devolucions. En tots dos casos s'avisa el club per
  correu i al tauler. El soci rep «Pagament rebut» si recupera la plaça; si no, un correu que li
  diu que no està inscrit i que se li retornarà l'import.

Les activitats creades abans d'aquesta manera de treballar porten la marca **legacy**: confirmen
la inscripció al moment i el rebut es cobra després, com sempre. No es poden canviar.

### Cancel·lació automàtica

Si el soci no paga dins del termini, la inscripció es cancel·la, el rebut s'anul·la i la plaça
passa al següent de la llista d'espera. El valor del club es configura a **Configuració ›
Pagaments › General** (termini per defecte: 72 hores) i cada activitat la pot activar,
desactivar o canviar-ne el termini.

Només es pot activar amb els correus *Inscripció pendent de pagament*, *Plaça a punt de caducar*
i *Inscripció cancel·lada per manca de pagament* activats a **Configuració › Socis ›
Comunicacions**: sense ells, el soci perdria la plaça sense avís. Pel mateix motiu, mentre la
cancel·lació automàtica estigui activa al club o en alguna activitat, aquests correus no es poden
desactivar.

> **En activar-la en una activitat que ja té places pendents**, o al club amb activitats que
> segueixen el seu valor, aquestes places reben el termini complet **a partir d'aquell moment**,
> el seu rebut venç en aquesta data i cada soci rep de nou el correu de plaça pendent, ara amb el
> termini. Les places que ja tenien termini el conserven.
