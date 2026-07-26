# Campos de perfil personalizados

Permiten definir campos propios para las fichas de los socios **sin cambiar el código** (por
ejemplo: talla de equipación, número de licencia federativa, alergias…).

> **Requisito previo.** Actívalos en **Ajustes → Campos de perfil**.

## Definir un campo

Desde **Añadir campo** configuras:

- **Clave** — identificador estable en minúsculas. **No se puede cambiar** después de crear el
  campo.
- **Tipo** — **Texto**, **Texto largo**, **Número**, **Fecha**, **Sí/No** o **Lista de
  opciones**. **No se puede cambiar** después de crear el campo.
- **Etiqueta** — en cada idioma (ES/CA/EN) y un **texto de ayuda** opcional.
- **Opciones** — para el tipo *Lista de opciones*, cada una con su valor y etiqueta.
- **Obligatorio**, **Activo** y **Orden**.

## Visibilidad y edición

Cada campo controla por separado quién puede verlo y editarlo:

- **Acceso del socio** — qué puede hacer el socio con su propio valor: **Oculto**, **Solo
  lectura** o **Editable**.
- **Acceso del administrador** — los administradores **siempre pueden ver** el campo; el
  superadministrador **siempre puede editarlo**.

## Eliminar un campo

Si un campo ya tiene datos guardados, al eliminarlo **se archiva** en lugar de borrarse, para
no perder la información existente. Los campos archivados aparecen marcados como **Archivado**.
