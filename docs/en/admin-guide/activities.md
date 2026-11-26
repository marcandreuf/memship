<!-- source: es/admin-guide/activities.md -->
<!-- source-hash: 8bce1a07c79a -->

# Activities

Activities are events, courses, workshops or competitions that members can register for. Each
activity can have modalities, price tiers and eligibility rules.

> **In Spanish:** [Actividades](../../es/admin-guide/activities.md).
> **En català:** [Activitats](../../ca/admin-guide/activities.md).

## Creating an activity

When you create an activity you configure:

- **Basic Information**, name, description and short description.
- **Dates**, start and end of the activity, and the **Registration Period** (opening and
  closing).
- **Location**, with optional details and URL.
- **Capacity**, minimum and maximum number of participants.
- **Eligibility**, age range (minimum/maximum age).
- **Cancellation**, whether or not the member may cancel, the refund deadline and what happens
  after it (see [Cancellation policy](#cancellation-policy)).
- **Cover Image**, visible to members as a thumbnail.

## Statuses and publishing

An activity goes through the statuses **Draft → Published → Archived** (as well as *Cancelled*
and *Completed*). Only **published** activities are visible to members. Use the **Publish**,
**Archive** and **Cancel Activity** actions as appropriate.

## Modalities

**Modalities** are variants of the same activity, each with its own **capacity**, **price** and
**registration deadline** (e.g. different level groups or time slots).

## Prices

You can define several **prices**, at activity or modality level, with **time validity**
(*valid from / until*) to set up, for example, early registration rates. A price can be marked as
**Default**, which preselects it on the member's registration form; only one price per
activity can be the default. An amount of 0 is shown as **Free**.

## Discounts

**Discount codes** can be of the **Percentage** or **Fixed Amount** type, with a **maximum number
of uses** (or unlimited) and validity dates. The member enters the code when registering.

## Consents

Each activity can require **consents** (mandatory or optional) that the member must accept during
registration. They are ordered and edited from the corresponding tab.

## Attachments

You can define **document types** that the member must attach when registering, specifying the
**allowed extensions**, the **maximum size** and whether they are mandatory.

## Registrations

From the **Registrations** tab you see the registered members and their status: **Confirmed**,
**Waitlisted**, **Payment pending** or **Cancelled**. If you switch on the activity's **waiting
list**, once it fills up new registrations join it and are promoted, in order, as places become
free. You can **change the status** of a registration manually.

## Payment and seat confirmation

In a paid activity the seat stays **payment pending** until its [receipt](payments.md) is paid:
it takes a place, but it is not confirmed. It confirms itself when the payment is recorded,
whether through a gateway, by bank transfer or in cash. A free activity, or a price of 0,
confirms at once.

- **Accepted payment methods.** Card, Bizum, bank transfer or cash. A paid activity needs at
  least one to be published, and only those the club can take today are offered: card needs
  Stripe or Redsys active, Bizum a Redsys with Bizum enabled, and transfer the club's IBAN. The
  member is only offered the ones the activity accepts, in emails and in *My receipts*.
- **Confirm without payment.** Confirms a pending seat and cancels its receipt. Who did it is
  recorded.
- **Cancelling a paid seat.** It goes to **Refunds** (from Activities or Spaces) unless you tick *Keep the
  payment*. The refund is made from the gateway or by hand; memship only records it as returned.
  Cancelling from the panel tells the member by email.
- **Late payment.** If the gateway collects a seat already released, the seat comes back if
  there is room; otherwise the amount goes to refunds. Either way the club is alerted by email and
  on the dashboard. The member is sent *Payment received* if the seat comes back; otherwise an
  email saying they are not registered and the amount will be returned.

Activities created before this way of working carry the **legacy** mark: they confirm the
registration at once and the receipt is collected afterwards, as before. This cannot be changed.

### Cancellation policy

When a member cancels their own seat, the policy of the activity decides what happens to what they
paid. The deadline is set in minutes, hours or days before the start; left empty there is no
deadline.

- **Before the deadline** the seat is released and a payment already made is marked *refund due*,
  so it appears in **Refunds**.
- **After the deadline** you choose, per activity, between **Refuse the cancellation** (the default)
  and **Allow it; the club keeps the payment**. In the second case the seat is released, the
  receipt stays paid and nothing is owed back. The member is warned before confirming.
- **The member is told up front.** The deadline and the rule after it show in the activity's
  details and on the registration page next to the price, and the confirmation email of a paid seat
  on an activity that keeps late payments says the payment will not be returned after the deadline.
- **When you cancel**, you choose at that moment whether the payment is returned, whatever the
  policy.
- A seat that was never paid (pending, free or exempt) has nothing to return.

Returning the money stays a manual act in the gateway or bank; memship only records it.

### Automatic cancellation

If the member does not pay in time, the registration is cancelled, the receipt is voided and the
seat goes to the next person on the waiting list. The club's default is set in **Settings ›
Payments › General** (default time: 72 hours), and each activity can switch it on or off or
change the time.

It can only be switched on while the *Registration pending payment*, *Seat about to expire* and
*Registration cancelled for non-payment* emails are on in **Settings › Members ›
Communications**: without them the member would lose the seat without warning. For the same
reason, while automatic cancellation is on for the club or any activity, those emails cannot be
switched off.

> **Switching it on for an activity that already has pending seats**, or for the club with
> activities that follow its default, gives those seats the full time **from that moment**, their
> receipt falls due on that date, and each member is sent the pending-payment email again, now
> with the deadline. Seats that already had a deadline keep it.
