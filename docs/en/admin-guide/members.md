<!-- source: es/admin-guide/members.md -->
<!-- source-hash: 499db6850771 -->

# Members

Managing the member life cycle, membership types and groups.

> **In Spanish:** [Socios](../../es/admin-guide/members.md).
> **En català:** [Socis](../../ca/admin-guide/members.md).

## Member list

The list lets you search, filter by **status** and by **membership type**, and paginate the
results. From there you can open each member's record or create a new one with **New member**.

## Creating and editing a member

When a member is registered, the details recorded include, among others:

- **Name**, **Date of birth**, **National ID** and **Gender**.
- **Membership type** (see below).
- **Internal notes**, visible only to administrators.

The **Joined** date is recorded automatically.

### Contacts

In the **Contact Info** tab of the record you can add several means of contact (phone, email,
etc.), each with a **type** and a **label** (e.g. "Personal", "Work").

You can mark one as **primary for its channel**: a primary phone and a primary email at the same
time, but not two primary phones. Types are grouped by channel, so "Home phone" and "Mobile
phone" compete for the same slot. When you mark one as primary, the previous one on that channel
stops being primary: the last one you mark wins.

Each channel allows **up to 5 contacts**. When a channel is full, its types are no longer
offered when adding a new contact.

### Bank details

The member's **IBAN** and **BIC / SWIFT** are recorded on the record, needed for
[SEPA direct debit](sepa.md).

## Member statuses

From the record you can change the status with the **Activate**, **Suspend** and **Cancel**
actions. Memship **does not delete** members permanently in the normal flow: they are cancelled
to keep the history.

## Membership types

Membership types define the categories of members in your organisation (e.g. *Full Member*,
*Student*, *Senior*). Each type has:

- **Name** and **description**.
- **Base price (EUR)** and **billing frequency**.
- An associated **Group** (optional).
- Age restrictions (optional).

Membership types are the basis of [fee generation](payments.md#generate-membership-fees) and of
[recurring billing](settings.md#recurring-billing).

## Groups

Groups let you organise members into sets (by team, category, section…) that can then be used,
for example, to send [communications](communications.md) to a specific audience.

## Minors and guardians

Memship supports minor members with an associated guardian, for clubs with children's or youth
sections.

## Audit

The **Audit Log** tab of the record shows the log of changes made to that member.
