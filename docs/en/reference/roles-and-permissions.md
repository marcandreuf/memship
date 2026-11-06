<!-- source: es/reference/roles-and-permissions.md -->
<!-- source-hash: 5a3e8950b7cf -->

# Roles and permissions

Memship distinguishes three roles. Access to each feature depends on the user's role.

> **In Spanish:** [Roles y permisos](../../es/reference/roles-and-permissions.md).

| Role                   | Scope                                                                        |
|------------------------|------------------------------------------------------------------------------|
| **Super admin**        | Platform-level administration. On top of everything the organisation administrator can do, manages the **payment gateway configuration** and other platform settings. |
| **Organisation administrator** | Day-to-day management of the organisation: **members**, **activities**, **payments and receipts**, **SEPA**, **communications**, **digital member card**, **profile fields**, **reports** and **settings**. |
| **Member**             | Member portal: their **profile**, their **activities**, their **receipts and payment method**, and their **digital member card**. |

## Notes

- Access to some areas also depends on the feature being **enabled** in the
  [settings](../admin-guide/settings.md) (communications, member card, profile
  fields, etc.).
- For **custom profile fields**, visibility and editing are controlled per field:
  administrators **can always see** a field and the super admin **can always
  edit it**; for the member, each field can be hidden, read-only or editable. See
  [Profile fields](../admin-guide/custom-fields.md).
- Memship is **single-tenant**: one database per organisation.

> A model of **flexible roles and permissions** (multiple roles and permissions per role, beyond
> the current three) is on the roadmap; this page will be updated when it is released.
