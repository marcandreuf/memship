<!-- source: es/admin-guide/members.md -->
<!-- source-hash: 499db6850771 -->

# Socis

Gestió del cicle de vida dels socis, els tipus d'afiliació i els grups.

> **En castellà:** [Socios](../../es/admin-guide/members.md).

## Llista de socis

La llista permet cercar, filtrar per **estat** i per **tipus d'afiliació**, i paginar els
resultats. Des d'allà pots obrir la fitxa de cada soci o crear-ne un de nou amb **Nou soci**.

## Crear i editar un soci

En donar d'alta un soci es registren, entre altres dades:

- **Nom**, **Data de naixement**, **DNI/NIE** i **Gènere**.
- **Tipus d'afiliació** (vegeu més avall).
- **Notes internes**, visibles només per als administradors.

La **Data d'alta** queda registrada automàticament.

### Contactes

A la pestanya **Contacte** de la fitxa pots afegir diversos mitjans de contacte (telèfon, correu,
etc.), cadascun amb un **tipus** i una **etiqueta** (p. ex. «Personal», «Feina»).

En pots marcar un com a **principal del seu canal**: un telèfon principal i un correu principal
alhora, però no dos telèfons principals. Els tipus s'agrupen per canal, així que «Telèfon
particular» i «Telèfon mòbil» competeixen per la mateixa plaça. En marcar-ne un com a principal,
l'anterior d'aquell canal deixa de ser-ho: guanya l'últim que marques.

Cada canal admet **fins a 5 contactes**. Quan un canal és complet, els seus tipus deixen d'oferir-se
en afegir un contacte nou.

### Dades bancàries

A la fitxa es registren l'**IBAN** i el **BIC/SWIFT** del soci, necessaris per a la
[domiciliació SEPA](sepa.md).

## Estats del soci

Des de la fitxa pots canviar l'estat amb les accions **Activar**, **Suspendre** i
**Cancel·lar**. Memship **no elimina** socis de manera permanent en el flux normal: es cancel·len
per conservar l'històric.

## Tipus d'afiliació

Els tipus d'afiliació defineixen les categories de socis de la teva organització (p. ex. *Soci
Ple*, *Estudiant*, *Sènior*). Cada tipus té:

- **Nom** i **descripció**.
- **Preu base (EUR)** i **freqüència de facturació**.
- **Grup** associat (opcional).
- Restriccions d'edat (opcional).

Els tipus d'afiliació són la base de la [generació de quotes](payments.md#generar-quotes) i de la
[facturació recurrent](settings.md#facturació-recurrent).

## Grups

Els grups permeten organitzar els socis en conjunts (per equip, categoria, secció…) que després
serveixen, per exemple, per adreçar [comunicacions](communications.md) a una audiència concreta.

## Menors i tutors

Memship admet socis menors amb un tutor associat, per a clubs amb seccions infantils o juvenils.

## Auditoria

La pestanya **Auditoria** de la fitxa mostra el registre de canvis fets sobre aquest soci.
