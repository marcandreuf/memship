<!-- source: es/admin-guide/sepa.md -->
<!-- source-hash: 86bc4eb6bffe -->

# Domiciliació SEPA

Cobrament de rebuts per domiciliació bancària mitjançant mandats SEPA i remeses.

> **En castellà:** [Domiciliación SEPA](../../es/admin-guide/sepa.md).

> **Requisit previ.** Configura l'**identificador del creditor** i les dades bancàries de
> l'entitat a [Configuració → Pagaments → General](settings.md#domiciliació-sepa).

## Mandats

Un **mandat** és l'autorització del soci per domiciliar cobraments al seu compte. Cada mandat
té una **referència**, el **titular** i l'**IBAN/BIC** del compte, un **tipus** (**recurrent** o
**puntual**) i una **signatura** (**paper** o **digital**).

Flux habitual:

1. **Nou mandat** per al soci.
2. **Descarregar PDF** del mandat perquè el signi.
3. **Pujar signat** el document (PDF, JPG o PNG).
4. El mandat queda **Actiu** i es pot fer servir en remeses.

**Un soci només pot tenir un mandat actiu.** Si intentes registrar-ne un segon, Memship el
rebutja i indica la referència i el compte del mandat vigent. Quan un soci canvia de banc,
**anul·la primer** el mandat actual i registra després el nou, el mateix ordre que segueix la
paperassa. Si la teva instància ve d'una versió anterior a la **2.18.0** i tenia mandats actius
duplicats, l'actualització els va cancel·lar i va conservar el més recent.

L'**IBAN** es valida en desar-lo, **dígits de control inclosos**, així que un IBAN amb una xifra
malament es rebutja al formulari en lloc d'acabar al fitxer del banc, que retornaria la remesa
sencera. El pots enganxar tal com surt a l'extracte: les majúscules i els espais es normalitzen.

Un mandat es pot **cancel·lar** (acció irreversible); passa a **Cancel·lat**. També pot constar
com a **Expirat**.

## Remeses

Una **remesa** agrupa rebuts domiciliats en un lot per enviar-lo al banc.

1. **Nova remesa** i **selecciona els rebuts**, només rebuts **emesos** o **vençuts** amb
   mandats SEPA actius. Veuràs el nombre de rebuts seleccionats i el total.

   La **data de cobrament** no pot ser anterior a avui (es comprova contra el dia de l'entitat,
   no el del servidor), perquè el banc rebutja el fitxer complet si ho és. Si cau en cap de
   setmana, el formulari t'avisa però no t'ho impedeix: el termini mínim i el calendari de
   liquidació els fixa cada banc.
2. **Generar XML**, produeix el fitxer **ISO 20022 pain.008**, estàndard per als bancs de la zona
   SEPA. **Descarrega l'XML** i presenta'l a la teva banca electrònica.

   **El fitxer es genera una sola vegada i no se sobreescriu**: és el registre del que es va
   enviar al banc. Si en necessites un de diferent (perquè un mandat ha canviat, per exemple)
   **cancel·la la remesa i torna-la a crear**; en cancel·lar-la, els seus rebuts queden lliures
   per a una altra.
3. **Marcar enviada** quan l'hagis presentat al banc.

   Des d'aquest moment i fins que tanquis la remesa, els seus rebuts **no es poden cobrar ni
   anul·lar a mà**: hi ha una ordre en curs al banc i Memship no pot afirmar el contrari. Les dues
   sortides són les dels passos següents: importar la devolució, o tancar la remesa. Un pagament
   amb targeta o Bizum confirmat pel proveïdor sí que marca el rebut com a cobrat, perquè aquí els
   diners s'han mogut de debò; aquesta és justament la situació que descriu l'avís del pas 4.
4. **Importar devolucions**, SEPA només informa dels cobraments que **fallen**. Enganxa les línies
   de devolució en **JSON** (el quadre del diàleg mostra el format), amb el número de rebut i, si
   el tens, el motiu; no es puja el fitxer del banc tal qual. Un text buit es rebutja: no equival a
   "el banc no ha retornat res". Si no hi ha devolucions, **salta't aquest pas** en lloc d'importar
   una llista buida.

   El resultat agrupa els rebuts pel que ha passat amb cadascun, **Retornats**, **Ja constaven
   retornats**, **Sense canvis: el seu estat no admet una devolució**, **Línies repetides al
   fitxer**, **No són d'aquesta remesa** (indicant en quina són) i **No trobats**, i anomena els
   rebuts de cada grup. Només es poden marcar com a retornats els rebuts **emesos** o **vençuts**.

   **Si alguna línia correspon a un rebut que a Memship consta com a cobrat, no s'importa res.**
   El banc diu que ha retornat els diners i Memship diu que els va cobrar: algú el va cobrar per
   una altra via mentre el càrrec era en curs. Revisa aquests rebuts, decideix quin cobrament és
   el real i torna a importar el fitxer sense aquestes línies.
5. **Tornar a cobrar el que s'ha retornat**, una devolució per saldo insuficient és rutina, i
   recuperar-la són **dos passos**, no un. Al rebut retornat prem **Reemetre**: torna a l'estat
   **Pendent** i surt de la remesa en què era, perquè un rebut no pot entrar en una remesa nova
   mentre pertanyi a una altra. Un rebut **Pendent** encara no s'ofereix per cobrar, així que prem
   després **Emetre**, i llavors ja apareix al selector de **Nova remesa**. No consumeix un número
   de document nou: és el mateix rebut, amb el mateix número.

   Si vas a *Nova remesa* just després de **Reemetre** i el rebut no apareix, és que falta aquest
   segon pas.
6. **Tancar** la remesa quan hagi passat el termini de devolucions. SEPA només informa dels
   cobraments que fallen, així que en tancar es marquen com a **Cobrats** tots els rebuts del lot
   que continuïn pendents, amb la data de cobrament de la remesa. Abans de confirmar veuràs quants
   rebuts es marcaran: **un cop tancada la remesa ja no es poden importar devolucions**, així que
   no la tanquis abans que venci el termini del teu banc.

Estats d'una remesa: **Esborrany → Llesta → Enviada → Processada → Tancada** (o **Cancel·lada**;
en cancel·lar-la es desvinculen tots els rebuts). Una remesa **Enviada** es pot tancar
directament, sense passar per **Processada**: el lot en què ha pagat tothom no té devolucions per
importar.

### Què veus en una remesa ja enviada

Els comptadors de la fitxa, **Rebuts** i **Import**, són el registre del **que es va enviar al
banc** i no es recalculen: el banc té aquest fitxer, i canviar la xifra després reescriuria el que
se li va demanar. Una remesa en **Esborrany** o **Llesta** sí que es recalcula, perquè d'aquí encara
en pot sortir un fitxer i ha de demanar exactament el que diu.

Per això la taula de rebuts d'una remesa enviada inclou també els que **ja n'han sortit**, el
retornat que has reemès, per exemple. Cada línia així ho indica, amb la data i el motiu
(*retornat i reemès*, *rebut anul·lat*, *cobrat per una altra via*, *remesa cancel·lada*), i
mostra l'estat que el rebut té **ara**, que és el que et diu què et queda per fer: un rebut reemès
apareix com a **Pendent**, cosa que vol dir que falta tornar-lo a emetre. L'import de la línia és
el que portava la remesa, no el que tingui el rebut avui.

Si la remesa es va enviar des d'una instal·lació anterior a la 2.19.0, dels rebuts que ja n'havien
sortit no en queda registre: aquella taula no existia, així que aquestes remeses mostren només el
que conserven.
