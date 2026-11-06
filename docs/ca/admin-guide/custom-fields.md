<!-- source: es/admin-guide/custom-fields.md -->
<!-- source-hash: b517f44617a3 -->

# Camps de perfil personalitzats

Permeten definir camps propis per a les fitxes dels socis **sense canviar el codi** (per exemple:
talla de l'equipació, número de llicència federativa, al·lèrgies…).

> **En castellà:** [Campos de perfil personalizados](../../es/admin-guide/custom-fields.md).

> **Requisit previ.** Activa'ls a **Configuració → Socis → Camps de perfil**.

## Definir un camp

Des d'**Afegir camp** configures:

- **Clau**, identificador estable en minúscules. **No es pot canviar** després de crear el camp.
- **Tipus**, **Text**, **Text llarg**, **Número**, **Data**, **Sí/No** o **Llista d'opcions**.
  **No es pot canviar** després de crear el camp.
- **Etiqueta**, en cada idioma (ES/CA/EN) i un **text d'ajuda** opcional.
- **Opcions**, per al tipus *Llista d'opcions*, cadascuna amb el seu valor i la seva etiqueta.
- **Obligatori**, **Actiu** i **Ordre**.

## Visibilitat i edició

Cada camp controla per separat qui el pot veure i editar:

- **Accés del soci**, què pot fer el soci amb el seu propi valor: **Ocult**, **Només lectura** o
  **Editable**.
- **Accés de l'administrador**, els administradors **sempre poden veure** el camp; el
  superadministrador **sempre el pot editar**.

## Eliminar un camp

Si un camp ja té dades desades, en eliminar-lo **s'arxiva** en lloc d'esborrar-se, per no perdre
la informació existent. Els camps arxivats apareixen marcats com a **Arxivat**.
