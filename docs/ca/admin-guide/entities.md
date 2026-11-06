<!-- source: es/admin-guide/entities.md -->
<!-- source-hash: 49fb1fa84949 -->

# Entitats

Empreses, fundacions, organismes públics i altres organitzacions amb què tracta el club:
donants, patrocinadors o col·laboradors. No són socis: no tenen quota, accés al portal ni
inscripcions. El que sí que tenen és fitxa pròpia, adreces, contactes i, sobretot, **rebuts al
seu nom**, i així es registra la donació d'una empresa sense inventar-se un soci.

> **En castellà:** [Entidades](../../es/admin-guide/entities.md).

L'accés requereix els permisos **Veure entitats** / **Editar entitats**, que el rol
d'administrador té de sèrie i que pots concedir per separat en un rol personalitzat.

## Llista d'entitats

A **Entitats** (grup de persones del menú) pots cercar per nom, NIF/CIF o correu, i filtrar per
**tipus** (empresa, associació, organisme públic, fundació o altra). Amb **Nova entitat** s'obre
el formulari d'alta: tipus, nom, raó social, NIF/CIF i correu.

## Fitxa d'una entitat

La part superior mostra les dades de l'entitat i s'edita al mateix lloc amb **Editar**. A sota,
les pestanyes:

- **Rebuts**, els rebuts emesos a l'entitat, amb **Nou rebut** per crear-ne un de manual. Per a
  una donació, tria l'origen **Donació**: així compta com a donació al llistat i a l'exportació,
  comença amb IVA 0 i no entra als avisos d'impagament. Fes servir la **descripció** i les
  **notes** per al detall (campanya, destinació, acord). El rebut segueix el flux normal: emetre,
  cobrar en línia o marcar com a pagat. Mira [Donacions](donations.md).
- **Adreça**, l'adreça postal de l'entitat.
- **Contactes**, persones o mitjans de contacte de l'entitat (telèfon, correu…), amb tipus i
  etiqueta, igual que a la fitxa d'un soci.

## Mandats SEPA

Un mandat de domiciliació també pot estar a nom d'una entitat: a **Mandats** → **Nou mandat**, el
camp **Soci o entitat** cerca entre tots els registres (socis i entitats) per nom, NIF o correu.

## Eliminar una entitat

Una entitat només es pot eliminar si no té rebuts ni mandats associats, l'historial econòmic no
s'esborra. Si en té, l'aplicació ho impedeix i ho indica.
