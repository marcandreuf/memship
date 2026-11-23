# Spaces and bookings

Spaces are the club's bookable resources: a court, a room, a lane. Each space has opening hours
and dated **slots**, and members book a slot from **Book** in the member portal. Spaces appear
when the **bookings** module is switched on.

> **En español:** [Espacios y reservas](../../es/admin-guide/spaces.md).
> **En català:** [Espais i reserves](../../ca/admin-guide/spaces.md).

## Spaces and slots

A space has a name, a type, opening hours, an optional **price** per booking (before tax) and,
optionally, the membership types allowed to book it. A slot is a date and a time inside those
hours, with a **capacity** (how many members may hold it at once) and, if it differs from the
space's, its own price; a price of 0 is a free slot in a paid space. A repeat rule creates a
whole series of slots at once.

**Deactivating** a space hides it from members and keeps everything. **Deleting** a slot or a
space removes its bookings for good, so it is refused while any of them carries money: a paid
booking whose slot is still to come, or a cancelled one with a refund due. Cancel those first,
which records what is owed, or deactivate instead.

## Payment and booking confirmation

In a paid space a booking stays **awaiting payment** until its [receipt](payments.md) is paid:
it takes a place, but it is not confirmed. It confirms itself when the payment is recorded,
whether through a gateway, by bank transfer or in cash. A free space or a free slot books at
once.

- **Accepted payment methods.** Card, Bizum, bank transfer or cash. A space with a price needs
  at least one, and only those the club can take today are offered: card needs Stripe or Redsys
  active, Bizum a Redsys with Bizum enabled, and transfer the club's IBAN. The member is only
  offered the ones the space accepts, in emails and in *My receipts*.
- **Confirm without payment.** From the space's **Bookings** tab, confirms a pending booking and
  cancels its receipt. Who did it is recorded.
- **Marking a payment received.** The payment column links to the receipt, where a transfer or
  cash is marked paid; the booking confirms itself.
- **Cancelling a paid booking.** It goes to **Refunds** unless you tick *Keep the payment*. The
  refund is made from the gateway or by hand; memship only records it as returned. The member is
  told by email, and the email says the amount will be returned.
- **Late payment.** If the gateway collects a booking already released, it comes back if the slot
  has not started and there is room; otherwise the amount goes to refunds. Either way the club is
  alerted by email and on the dashboard.

Spaces created before this way of working carry the **legacy** mark: they confirm the booking at
once and the receipt is collected afterwards. Unlike an activity, a legacy space can be switched
to the new flow from its edit form. The switch cannot be undone, and only bookings made after it
follow the new flow.

### The payment deadline

Every pending booking has a deadline, because a slot is for one date and often for tomorrow. In
**Settings › Payments › General**, under *Paid bookings*, the club sets:

- **Margin before the slot** (default 60 minutes): a pending booking must be paid at the latest
  this long before its slot starts. A booking never reaches its slot unpaid. Set it to 0 if you
  take cash at the door and mark it paid before the start.
- **Shortest time to pay** (default 15 minutes): a booking that would have less time than this is
  refused, and the member is told why. Slots too close to their start are shown as no longer
  bookable.
- **Release unpaid bookings earlier** (off by default, 24 hours): with it on, a pending booking is
  also released if it is not paid within that time, whichever comes first. Each space can follow
  the club, switch it on or off, or change the time. Switching it on brings the deadline of
  bookings already pending forward, and their members are told.

The member is shown the deadline before booking, receives it in the email, and is warned once
before it. A booking not paid in time is cancelled, its receipt voided, and its member told.

### Waiting list

When a place frees up in a paid slot, what happens depends on how long a booking made now would
have to be paid:

| Time to pay | What happens |
|---|---|
| At least the *shortest time to hand a place out by itself* (default 120 minutes) | The first person on the waiting list is given the place, awaiting payment, and is told how and by when to pay |
| Between the *shortest time to pay* and that | Nobody is promoted. Everyone on the waiting list is emailed that a place is free; whoever books and pays it first takes it |
| Less than the *shortest time to pay* | The place is left free |

A free place in a free or legacy slot goes to the first person on the list, as before.

### Emails

A paid space releases unpaid bookings, so it can only charge while the *Booking awaiting
payment*, *Booking deadline reminder* and *Booking cancelled for non-payment* emails are on in
**Settings › Members › Communications**. For the same reason, while a paid space exists those
emails cannot be switched off. A new installation has them on, together with *Place freed at the
last minute*, which carries the call to the waiting list.

## Refunds and late payments

**Refunds**, reached from Activities or Spaces, lists every cancelled registration and booking
whose payment is owed back, with the method and the gateway reference. Mark each one returned
once the money has gone back. Payments that arrived after their place was released also appear
as a banner on the dashboard until someone has looked at them.
