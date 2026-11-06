<!-- source: es/reference/roles-and-permissions.md -->
<!-- source-hash: 82c741c57681 -->

# Roles and permissions

What each account can do depends on its **roles**, and each role is a set of **permissions**. An
account can hold several roles and has the permissions of all of them.

> **In Spanish:** [Roles y permisos](../../es/reference/roles-and-permissions.md).

## System roles

Memship ships three roles, marked **System**. They cannot be renamed or deleted.

| Role | Scope |
|------|-------|
| **Super Admin** | Everything, including the **reserved permissions**: creating and editing roles, and managing integration credentials (payment gateways, SSO, email). Its permissions cannot be changed. |
| **Administrator** (organisation administrator) | Day-to-day management: **members**, **entities**, **activities**, **payments and receipts**, **SEPA**, **communications**, **bookings**, **reports** and **membership types**. It does not have the reserved permissions and cannot edit profile field definitions. |
| **Member** | The member portal: their **profile**, their **activities**, their **receipts and payment method**, their **digital member card**, their **bookings** and their **communications**. |

The superadmin can adjust which permissions **Administrator** and **Member** have.

## Custom roles

In **Settings → Roles**, the superadmin creates tailored roles, for example a treasurer who
only sees billing, choosing their permissions from a list grouped by area (**Administration**
and **Personal area**). Permissions **reserved to the super admin** cannot be given to a custom
role. A role can only be deleted when no account holds it.

In **Settings → Accounts**, administrators assign roles to existing accounts. Nobody can assign
a role with more permissions than they have, only a superadmin assigns the **Super Admin** role,
and the last one cannot be removed.

The **Custom roles** switch in **Settings → Roles** shows or hides role authoring and the
**Accounts** tab. It is on in a new installation. Turning it off does not turn permissions off:
every account stays limited to those of its roles.

## Notes

- Access to some areas also depends on the feature being **enabled** in the
  [settings](../admin-guide/settings.md) (communications, member card, profile
  fields, etc.).
- For **custom profile fields**, visibility and editing are controlled per field:
  administrators **can always see** a field and the super admin **can always
  edit it**; for the member, each field can be hidden, read-only or editable. See
  [Profile fields](../admin-guide/custom-fields.md).
- Memship is **single-tenant**: one database per organisation.
