<!-- source: es/admin-guide/donations.md -->
<!-- source-hash: e9c67dd3edf3 -->

# Donacions

Hi ha tres maneres de rebre una donació. La diferència no és tècnica: és **quin registre
necessites que quedi** i **qui fa la donació**.

> **En castellà:** [Donaciones](../../es/admin-guide/donations.md).

## Quin camí et toca

Dues preguntes, en aquest ordre.

> **1. Algú necessita un registre més enllà del tauler de la passarel·la de pagament?** És a dir:
> un rebut amb la numeració de l'organització, un total anual per donant, o un certificat per a
> una deducció fiscal.
>
> - **No** → **camí 1**: publica un enllaç de pagament al web de l'organització. La passarel·la
>   allotja la pàgina, cobra els diners i en guarda el registre. Memship no hi intervé.
> - **Sí** → passa a la pregunta 2.
>
> **2. Qui fa la donació?**
>
> - **Una empresa, fundació o organisme** → **camí 2**: dona-la d'alta com a
>   [entitat](entities.md) i emet el rebut al seu nom. **No cal fer-la sòcia**: una entitat no té
>   quota, ni accés al portal, ni inscripcions.
> - **Una persona** → **camí 3**: passa a ser sòcia i la donació és un rebut que ella mateixa
>   descarrega des d'**Els meus rebuts**.

El camí 3 no obliga a cobrar una quota. Un **tipus de quota amb import base 0** és un cas previst:
la persona queda registrada, amb el seu rebut i el seu historial, sense que la facturació
recurrent li generi res.

Els camins 2 i 3 són el mateix mecanisme amb un titular diferent, i la pestanya **Rebuts** és
literalment la mateixa pantalla a la fitxa d'una entitat i a la d'un soci.

## Camí 1: un enllaç al web de l'organització

És la resposta quan **no vols registrar el donant de cap manera**. Memship no guarda donants
anònims a propòsit, així que aquest camí viu sencer fora de l'aplicació. Si el donant és una
empresa i sí que en vols la fitxa, el camí 2 tampoc no la fa sòcia.

### Com es fa

L'enllaç es crea al **tauler del proveïdor de pagament**, no a memship. Tant Stripe com PayPal
ofereixen una URL de donació permanent que no requereix programar res, i tots dos es poden
configurar perquè el donant triï l'import.

- **Stripe**: *Payment Links*. Crea un enllaç, marca l'import com a personalitzable i copia la
  URL.
- **PayPal**: *Botones de donación*. El mateix resultat: una URL que pots enganxar on vulguis.

Publicar-lo és un enllaç normal:

```html
<a href="https://donate.stripe.com/XXXXXXXX">Hacer una donación</a>
```

No cal una clau d'API al web, ni un formulari que processi res, ni un webhook, ni cap desplegament.
Això importa si el web de l'organització és un lloc estàtic, perquè no té on guardar un secret.

**PayPal no està integrat a memship**, i Stripe per aquest camí tampoc: aquí l'enllaç no té cap
relació amb la passarel·la que la instància fa servir per cobrar quotes. És el web de
l'organització apuntant al proveïdor, i res més.

### Enllaça, no incrustis

Posa un enllaç que porti a la pàgina del proveïdor. No posis el formulari de pagament dins d'una
pàgina amb un `iframe`:

- Memship envia `Content-Security-Policy "frame-ancestors 'none'"` i `X-Frame-Options DENY` a
  totes les seves respostes, així que de tota manera no es pot incrustar.
- Un formulari de targeta dins d'una pàgina de tercers és una superfície molt més gran que una
  redirecció a la pàgina del mateix proveïdor.
- També és el que el donant hauria de veure: primer el lloc de l'organització, després el de la
  passarel·la, amb el seu cadenat i el seu domini.

### Quin registre queda, i on

Això convé llegir-ho a poc a poc, perquè el natural és suposar el contrari quan ja estàs acostumat
a veure els diners de l'organització en un sol lloc:

| On | En queda registre |
|---|---|
| Tauler del proveïdor de pagament | Sí |
| Correu que el proveïdor envia al donant | Sí |
| Rebut a memship | **No** |
| Soci a memship | **No** |
| Resum anual i tauler financer | **No** |

La donació **no apareix a memship**. Ni rebut, ni soci, ni res al resum anual.

### Si ho vols quadrar amb els teus llibres

Algú ho anota a mà. Des de la fitxa d'un soci, **Rebuts → Nou rebut**, amb origen **Donació**
(mira més avall). És feina manual i sense automatitzar: si això pesa, el camí 1 no és el teu.

### Redsys: pregunta al teu banc

Redsys és un TPV bancari, i que existeixi un enllaç de pagament permanent depèn del banc i del
contracte. La integració de Redsys de memship no en pot produir cap: signa un formulari
l'identificador de comanda del qual codifica un rebut concret, així que tot pagament que inicia
pertany a un rebut que ja existeix.

Si l'organització cobra per Redsys i vol donacions públiques, pregunta al banc o fes servir un
segon proveïdor només per a això.

## Camins 2 i 3: la donació com a rebut a memship

Quan sí que vols el registre, la donació és un rebut amb **origen Donació**, creat a mà des de
**Rebuts → Nou rebut** a la fitxa de l'entitat o del soci. La pantalla és la mateixa als dos
llocs.

L'origen fa tres coses que `Manual` no feia:

- **Es pot consultar.** El llistat de rebuts filtra per origen, i l'exportació CSV respecta el
  filtre, així que el total anual de donacions és una consulta i no una lectura de descripcions.
- **No es reclama.** Una donació sense pagar no entra en el cicle d'avisos d'impagament ni en
  l'import **pendent** del tauler financer. Una donació que algú s'ha repensat no és un deute, i
  ningú no hauria de rebre un recordatori per aquest motiu.
- **Comença amb IVA 0.** Una donació no és un lliurament de béns o serveis. El camp continua sent
  editable, perquè una donació amb contraprestació sí que hi pot estar subjecta; el que canvia és
  el valor per defecte, que abans era el 21%.

Un soci descarrega el PDF des d'**Els meus rebuts** igual que qualsevol altre. Una entitat no té
portal, així que el seu rebut el descarrega un administrador des de la fitxa i l'hi envia.

### L'origen Donació compta des d'aquesta versió

Els rebuts de donació que ja tinguis anotats com a **Manual** continuen sent Manual: no hi ha
manera de reclassificar-los. Res no permet distingir-los de qualsevol altre càrrec manual, perquè
aquesta distinció només era al text de la descripció.

Si necessites el total anual d'un exercici anterior, l'hauràs de buscar per descripció com fins
ara. D'aquesta versió endavant, filtra per origen.

## Relacionat

- [Pagaments i rebuts](payments.md): el rebut, el seu cicle de vida, l'IVA i la numeració
- [Entitats](entities.md): empreses, fundacions i organismes, amb rebuts al seu nom i sense fer-los
  socis
- [Guia de proveïdors de pagament](payment-providers.md): donar d'alta Stripe o Redsys a la
  instància, per cobrar quotes
