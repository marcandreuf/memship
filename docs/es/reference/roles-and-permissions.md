# Roles y permisos

Lo que puede hacer cada cuenta depende de sus **roles**, y cada rol es un conjunto de
**permisos**. Una cuenta puede tener varios roles y reúne los permisos de todos ellos.

> **In English:** [Roles and permissions](../../en/reference/roles-and-permissions.md).

## Roles del sistema

Memship trae tres roles, marcados como **Del sistema**. No se pueden renombrar ni eliminar.

| Rol | Ámbito |
|-----|--------|
| **Super Admin** (superadministrador) | Todo, incluidos los **permisos reservados**: crear y editar roles y gestionar las credenciales de las integraciones (pasarelas de pago, SSO, correo). Sus permisos no se pueden cambiar. |
| **Administrator** (administrador de la organización) | Gestión diaria: **socios**, **entidades**, **actividades**, **pagos y recibos**, **SEPA**, **comunicaciones**, **reservas**, **informes** y **tipos de membresía**. No tiene los permisos reservados ni puede editar las definiciones de los campos de perfil. |
| **Member** (socio) | Portal del socio: su **perfil**, sus **actividades**, sus **recibos y forma de pago**, su **carné digital**, sus **reservas** y sus **comunicaciones**. |

El superadministrador puede ajustar qué permisos tienen **Administrator** y **Member**.

## Roles personalizados

En **Configuración → Roles**, el superadministrador crea roles a medida, por ejemplo un tesorero
que solo ve la facturación, eligiendo sus permisos de una lista agrupada por área
(**Administración** y **Área personal**). Los permisos **reservados al superadministrador** no
se pueden dar a un rol personalizado. Un rol solo se puede eliminar cuando ninguna cuenta lo
tiene.

En **Configuración → Cuentas**, los administradores asignan roles a las cuentas existentes. Nadie
puede asignar un rol con más permisos de los que tiene, solo un superadministrador asigna el rol
**Super Admin**, y no se puede retirar el último.

El interruptor **Roles personalizados** de **Configuración → Roles** muestra u oculta la creación de
roles y la pestaña **Cuentas**. Está activado en una instalación nueva. Desactivarlo no
desactiva los permisos: cada cuenta sigue limitada a los de sus roles.

## Notas

- El acceso a algunas áreas depende además de que la función esté **activada** en la
  [configuración](../admin-guide/settings.md) (comunicaciones, tarjeta de socio, campos de
  perfil, etc.).
- En los **campos de perfil personalizados**, la visibilidad y edición se controlan por campo:
  los administradores **siempre pueden ver** un campo y el superadministrador **siempre puede
  editarlo**; para el socio, cada campo puede ser oculto, de solo lectura o editable. Ver
  [Campos de perfil](../admin-guide/custom-fields.md).
- Memship es de **un solo inquilino** (single-tenant): una base de datos por organización.
