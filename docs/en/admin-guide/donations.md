<!-- source: es/admin-guide/donations.md -->
<!-- source-hash: b6cb319b4585 -->

# Donations

There are three ways to receive a donation. The difference is not technical: it is **what record
you need to be left** and **who is donating**.

> **In Spanish:** [Donaciones](../../es/admin-guide/donations.md).

## Which path is yours

Two questions, in this order.

> **1. Does anyone need a record beyond the payment gateway's dashboard?** That is: a receipt
> with the organisation's numbering, an annual total per donor, or a certificate for a tax
> deduction.
>
> - **No** → **path 1**: publish a payment link on the organisation's website. The gateway
>   hosts the page, collects the money and keeps the record. Memship is not involved.
> - **Yes** → go on to question 2.
>
> **2. Who is donating?**
>
> - **A company, foundation or public body** → **path 2**: register it as an
>   [entity](entities.md) and issue the receipt in its name. **It does not need to become a
>   member**: an entity has no fee, no portal access and no registrations.
> - **A person** → **path 3**: they become a member and the donation is a receipt that they
>   download themselves from **My Receipts**.

Path 3 does not force you to charge a fee. A **membership type with a base amount of 0** is an
intended case: the person is registered, with their receipt and their history, without
recurring billing generating anything for them.

Paths 2 and 3 are the same mechanism with a different holder, and the **Receipts** tab is
literally the same screen on an entity's record and on a member's.

## Path 1: a link on the organisation's website

This is the answer when **you do not want to register the donor at all**. Memship deliberately
does not store anonymous donors, so this path lives entirely outside the application. If the
donor is a company and you do want its record, path 2 does not make it a member either.

### How it is done

The link is created in the **payment provider's dashboard**, not in memship. Both Stripe and
PayPal offer a permanent donation URL that needs no programming, and both can be configured so
that the donor chooses the amount.

- **Stripe**: *Payment Links*. Create a link, mark the amount as customisable and copy the URL.
- **PayPal**: *Donate buttons*. Same result: a URL you can paste wherever you like.

Publishing it is an ordinary link:

```html
<a href="https://donate.stripe.com/XXXXXXXX">Make a donation</a>
```

The website needs no API key, no form that processes anything, no webhook and no deployment of
any kind. This matters if the organisation's website is a static site, because it has nowhere to
keep a secret.

**PayPal is not integrated into memship**, and neither is Stripe on this path: here the link has
no relation to the gateway the instance uses to collect fees. It is the organisation's website
pointing at the provider, and nothing more.

### Link, do not embed

Use a link that takes the donor to the provider's page. Do not put the payment form inside a
page with an `iframe`:

- Memship sends `Content-Security-Policy "frame-ancestors 'none'"` and `X-Frame-Options DENY` in
  all its responses, so it cannot be embedded anyway.
- A card form inside a third-party page is a much larger surface than a redirect to the
  provider's own page.
- It is also what the donor should see: first the organisation's site, then the gateway's, with
  its padlock and its domain.

### What record is left, and where

Read this slowly, because the natural assumption is the opposite when you are used to seeing the
organisation's money in a single place:

| Where | Record left |
|---|---|
| Payment provider's dashboard | Yes |
| Email the provider sends to the donor | Yes |
| Receipt in memship | **No** |
| Member in memship | **No** |
| Annual summary and financial dashboard | **No** |

The donation **does not appear in memship**. No receipt, no member, nothing in the annual
summary.

### If you want to reconcile it with your books

Someone records it by hand. From a member's record, **Receipts → Add receipt**, with origin
**Donation** (see below). It is manual work with no automation: if that is a burden, path 1 is
not yours.

### Redsys: ask your bank

Redsys is a bank card terminal, and whether a permanent payment link exists depends on the bank
and the contract. Memship's Redsys integration cannot produce one: it signs a form whose order
identifier encodes a specific receipt, so every payment it starts belongs to a receipt that
already exists.

If the organisation collects through Redsys and wants public donations, ask the bank or use a
second provider just for this.

## Paths 2 and 3: the donation as a receipt in memship

When you do want the record, the donation is a receipt with **origin Donation**, created by hand
from **Receipts → Add receipt** on the entity's or the member's record. The screen is the same in
both places.

The origin does three things that `Manual` did not:

- **It can be queried.** The receipt list filters by origin, and the CSV export respects the
  filter, so the annual total of donations is a query and not a reading of descriptions.
- **It is not chased.** An unpaid donation does not enter the overdue reminder cycle or the
  **pending** amount on the financial dashboard. A donation someone thought better of is not a
  debt, and nobody should receive a reminder for it.
- **It starts with 0 VAT.** A donation is not a supply of goods or services. The field remains
  editable, because a donation with something given in return can be subject to it; what changes
  is the default value, which used to be 21%.

A member downloads the PDF from **My Receipts** like any other. An entity has no portal, so an
administrator downloads its receipt from the record and sends it to them.

### The Donation origin counts from this version

Donation receipts you have already recorded as **Manual** remain Manual: there is no way to
reclassify them. Nothing distinguishes them from any other manual charge, because that
distinction was only in the text of the description.

If you need the annual total for an earlier financial year, you will have to search for it by
description as before. From this version onwards, filter by origin.

## Related

- [Payments and receipts](payments.md): the receipt, its life cycle, VAT and numbering
- [Entities](entities.md): companies, foundations and public bodies, with receipts in their name
  and without making them members
- [Payment providers guide](../admin-guide/payment-providers.md): setting up Stripe or Redsys on
  the instance, to collect fees
