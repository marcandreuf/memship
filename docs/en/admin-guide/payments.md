<!-- source: es/admin-guide/payments.md -->
<!-- source-hash: 990a4f1807a6 -->

# Payments and receipts

Managing receipts, generating membership fees, VAT and collections (including online payment).

> **In Spanish:** [Pagos y recibos](../../es/admin-guide/payments.md).
> **En català:** [Pagaments i rebuts](../../ca/admin-guide/payments.md).

## The receipt and its life cycle

Each receipt has a **number**, a **member**, a **description**, amounts (**base**, **VAT**,
**discount**, **total**) and a **status**. The life cycle is:

**New** or **Pending** → **Issued** → **Paid**, and, depending on the case, **Returned**, **Cancelled**
or **Overdue**. A returned receipt that is re-emitted goes back to **Pending**.

Actions available depending on the status: **Emit**, **Mark Paid**, **Mark Returned**, **Cancel**
and **Re-emit** (for a returned receipt). From the receipt you can also **Download PDF**.

A receipt included in a remittance that is already **Submitted** or **Processed** cannot be
marked paid (**Mark Paid**) or cancelled (**Cancel**) by hand: the collection is in progress at the
bank. Import the return or close the remittance, see [SEPA Direct Debit](sepa.md#remittances).

## Correcting an issued receipt

An issued receipt is not edited: it is corrected by issuing a **credit note** from the receipt
itself (**Issue credit note**). The original receipt keeps its number, its amounts and its status;
the credit note is a new document, with a negative amount, that takes the next number in the same
series and links to the document it corrects. The two together add up to what the member really
owes.

You can correct a receipt that is **issued, overdue, returned or already paid**, which therefore
includes an amount that was overcharged. You give the **reason** and, if you do not want to correct
the total, the **amount**; several partial credit notes can be issued until they cover the
receipt's amount. A credit note is not collected by remittance and cannot be cancelled: the money
is refunded through the bank.

Cancelling is still available for a receipt that should never have been issued, but a receipt that
has already been paid can only be corrected with a credit note.

## Origin of receipts

A receipt can have one of these origins:

- **Membership**, a member's membership fee (see *Generate membership fees* and
  [recurring billing](settings.md#recurring-billing)).
- **Activity**, generated automatically when a [registration](activities.md) is confirmed; it is
  cancelled if the registration is cancelled.
- **Manual**, created by hand from the member's record.
- **Donation**: created by hand, with 0 VAT by default. It is not included in the payment reminders
  or in the dashboard's pending amount: an unfinished donation is not a debt. See
  [Donations](donations.md).

## Generate membership fees

The **Generate Membership Fees** action creates receipts for all active members according to their
**membership type**. It is the way to issue the periodic fee in bulk without creating them one by
one.

## VAT and invoicing

- The **VAT rate** is applied to the base; the default rate is configured in
  [Settings → Payments → General](settings.md#banking-and-invoicing).
- The **numbering** uses a configurable prefix and, optionally, restarts every year
  (e.g. `FAC-2026-0001`).
- The receipt **PDF** includes the organisation's header, the member's details and the VAT
  breakdown, in the corresponding language (ES/CA/EN).

## Payment methods and online collection

A receipt can be collected by **cash**, **bank transfer**, **card**, **direct debit**
(see [SEPA](sepa.md)) or through an **online payment gateway**.

When a provider is configured, the member sees the **Pay Now** button on their outstanding receipts
and can pay with:

- **Stripe**, card payment.
- **Redsys**, Spanish bank gateway with 3D Secure.
- **Bizum**, through Redsys, and only if **Offer Bizum** is enabled on that provider. Your bank has
  to enable it on the terminal first.

> The final confirmation of gateway payments arrives through the provider's **asynchronous
> notification**, not through the browser's return. Providers are configured in
> [Settings → Payments → Payment Providers](settings.md#payment-providers).

### When a payment notification fails

In **Settings → Payments → Payment Providers**, below the providers, **Payment notifications** lists what the
gateways sent and memship did not apply:

- **Failed**, it could not be applied. The gateway retries; if it keeps failing, it needs looking
  into.
- **Ignored**, it was received and deliberately nothing was done: a type of notice that is not
  handled, a different amount or a payment for a receipt that is **already paid**. That last one is
  a double charge: the second payment has to be refunded from the gateway.
- **Rejected by signature**, a count per provider above the list. If it keeps growing, the
  configured key is not the right one and no payment is being confirmed.

To receive an alert, set the billing notifications address: an email arrives once a day, only if
something happened in the last 24 hours. It is **Payment notification problems** in
Settings → Members → Communications: enabled by default on a new installation, and it can be disabled there.
An older installation starts with it disabled; enable it there.

If the gateway collected the money and the receipt is still pending, mark it as paid choosing
Redsys, Bizum or Stripe: memship asks for the **Gateway reference** (the authorisation code or the
payment identifier) so it can be reconciled with the bank.

> **To set them up step by step**, which credential to ask Stripe or the bank for, how to create
> the Stripe webhook and why Redsys does not need one, see the
> [payment providers guide](../admin-guide/payment-providers.md).

## Financial dashboard

The [dashboard](reports.md) shows the status of receipts and the **pending**, **paid this month**
and **overdue** amounts.
