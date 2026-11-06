<!-- source: es/reference/roles-and-permissions.md -->
<!-- source-hash: ba3f1f3a29f7 -->

# Rols i permisos

El que pot fer cada compte depèn dels seus **rols**, i cada rol és un conjunt de **permisos**. Un
compte pot tenir diversos rols i reuneix els permisos de tots.

> **En castellà:** [Roles y permisos](../../es/reference/roles-and-permissions.md).

## Rols del sistema

Memship porta tres rols, marcats com a **Del sistema**. No es poden canviar de nom ni eliminar.

| Rol | Àmbit |
|-----|--------|
| **Super Admin** (superadministrador) | Tot, inclosos els **permisos reservats**: crear i editar rols i gestionar les credencials de les integracions (passarel·les de pagament, SSO, correu). Els seus permisos no es poden canviar. |
| **Administrator** (administrador de l'organització) | Gestió diària: **socis**, **entitats**, **activitats**, **pagaments i rebuts**, **SEPA**, **comunicacions**, **reserves**, **informes** i **tipus d'afiliació**. No té els permisos reservats ni pot editar les definicions dels camps de perfil. |
| **Member** (soci) | Portal del soci: el seu **perfil**, les seves **activitats**, els seus **rebuts i forma de pagament**, el seu **carnet digital**, les seves **reserves** i les seves **comunicacions**. |

El superadministrador pot ajustar quins permisos tenen **Administrator** i **Member**.

## Rols personalitzats

A **Configuració → Rols**, el superadministrador crea rols a mida, per exemple un tresorer que
només veu la facturació, triant-ne els permisos d'una llista agrupada per àrea
(**Administració** i **Àrea personal**). Els permisos **reservats al superadministrador** no es
poden donar a un rol personalitzat. Un rol només es pot eliminar quan cap compte no el té.

A **Configuració → Comptes**, els administradors assignen rols als comptes existents. Ningú no pot
assignar un rol amb més permisos dels que té, només un superadministrador assigna el rol
**Super Admin**, i no es pot retirar l'últim.

L'interruptor **Rols personalitzats** de **Configuració → Rols** mostra o amaga la creació de rols
i la pestanya **Comptes**. Està activat en una instal·lació nova. Desactivar-lo no desactiva els
permisos: cada compte continua limitat als dels seus rols.

## Notes

- L'accés a algunes àrees depèn, a més, que la funció estigui **activada** a la
  [configuració](../admin-guide/settings.md) (comunicacions, targeta de soci, camps de perfil,
  etc.).
- Als **camps de perfil personalitzats**, la visibilitat i l'edició es controlen per camp: els
  administradors **sempre poden veure** un camp i el superadministrador **sempre pot editar-lo**;
  per al soci, cada camp pot ser ocult, de només lectura o editable. Mira
  [Camps de perfil](../admin-guide/custom-fields.md).
- Memship és d'**un sol inquilí** (single-tenant): una base de dades per organització.
