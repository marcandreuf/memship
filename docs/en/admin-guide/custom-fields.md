<!-- source: es/admin-guide/custom-fields.md -->
<!-- source-hash: acc2babfb3ac -->

# Custom profile fields

They let you define your own fields for member records **without changing the code** (for
example: kit size, federation licence number, allergies…).

> **In Spanish:** [Campos de perfil personalizados](../../es/admin-guide/custom-fields.md).

> **Prerequisite.** Enable them in **Settings → Members → Profile fields**.

## Defining a field

From **Add field** you configure:

- **Key**, a stable lower-case identifier. It **cannot be changed** after the field is
  created.
- **Type**, **Text**, **Long text**, **Number**, **Date**, **Yes/No** or **Option list**. It
  **cannot be changed** after the field is created.
- **Label**, in each language (ES/CA/EN), and an optional **Help text**.
- **Options**, for the *Option list* type, each with its value and label.
- **Required**, **Active** and **Order**.

## Visibility and editing

Each field controls separately who can see it and edit it:

- **Member access**, what the member can do with their own value: **Hidden**, **Read
  only** or **Editable**.
- **Admin access**, administrators **can always see** the field; the super administrator **can
  always edit it**.

## Deleting a field

If a field already has saved data, deleting it **archives it** instead of erasing it, so the
existing information is not lost. Archived fields are marked as **Archived**.
