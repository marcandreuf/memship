<!-- source: es/admin-guide/entities.md -->
<!-- source-hash: 7a3abc620686 -->

# Entities

Companies, foundations, public bodies and other organisations the club deals with:
donors, sponsors or partners. They are not members: they have no membership fee, portal access or
registrations. What they do have is their own record, addresses, contacts and, above all,
**receipts in their name**, so a donation from a company is recorded without inventing a member.

> **In Spanish:** [Entidades](../../es/admin-guide/entities.md).

Access requires the **View entities** / **Edit entities** permissions, which the
administrator role has out of the box and which you can grant separately in a custom role.

## Entity list

Under **Entities** (in the people group of the menu) you can search by name, tax ID (NIF/CIF) or
email, and filter by **kind** (company, association, public body, foundation or other). **New
entity** opens the creation form: kind, name, legal name, tax ID (NIF/CIF) and email.

## Entity record

The top of the page shows the entity's details and is edited in place with **Edit**. Below it,
the tabs:

- **Receipts**: the receipts issued to the entity, with **New Receipt** to create one manually.
  For a donation, choose the origin **Donation**: that way it counts as a donation in the list and
  in the export, starts with 0 VAT and is left out of non-payment reminders. Use the **description**
  and the **notes** for the detail (campaign, purpose, agreement). The receipt follows the normal
  flow: issue, collect online or mark as paid. See [Donations](donations.md).
- **Address**: the entity's postal address.
- **Contacts**: people or contact channels for the entity (phone, email…), with a type and
  label, just as on a member's record.

## SEPA mandates

A direct debit mandate can also be in an entity's name: in **Mandates** →
**New Mandate**, the **Member or entity** field searches all records (members and
entities) by name, tax ID (NIF) or email.

## Deleting an entity

An entity can only be deleted if it has no receipts or mandates attached, so the financial history
is never erased. If it has any, the application prevents the deletion and says so.
