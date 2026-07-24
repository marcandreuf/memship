# Roles y permisos

Memship distingue tres roles. El acceso a cada función depende del rol de la persona usuaria.

| Rol                    | Ámbito                                                                       |
|------------------------|------------------------------------------------------------------------------|
| **Superadministrador** | Administración a nivel de plataforma. Además de lo que puede el administrador de la organización, gestiona la **configuración de las pasarelas de pago** y otros ajustes de plataforma. |
| **Administrador de la organización** | Gestión diaria de la organización: **socios**, **actividades**, **pagos y recibos**, **SEPA**, **comunicaciones**, **carné digital**, **campos de perfil**, **informes** y **configuración**. |
| **Socio**              | Portal del socio: su **perfil**, sus **actividades**, sus **recibos y forma de pago**, y su **carné digital**. |

## Notas

- El acceso a algunas áreas depende además de que la función esté **activada** en la
  [configuración](../admin-guide/settings.es.md) (comunicaciones, tarjeta de socio, campos de
  perfil, etc.).
- En los **campos de perfil personalizados**, la visibilidad y edición se controlan por campo:
  los administradores **siempre pueden ver** un campo y el superadministrador **siempre puede
  editarlo**; para el socio, cada campo puede ser oculto, de solo lectura o editable. Ver
  [Campos de perfil](../admin-guide/custom-fields.es.md).
- Memship es de **un solo inquilino** (single-tenant): una base de datos por organización.

> Un modelo de **roles y permisos flexibles** (múltiples roles y permisos por rol, más allá de
> los tres actuales) está en la hoja de ruta; esta página se actualizará cuando se publique.
