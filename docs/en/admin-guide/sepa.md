<!-- source: es/admin-guide/sepa.md -->
<!-- source-hash: ad9dec598839 -->

# SEPA Direct Debit

Collecting receipts by direct debit through SEPA mandates and remittances.

> **In Spanish:** [Domiciliación SEPA](../../es/admin-guide/sepa.md).

> **Prerequisite.** Set up the organisation's **creditor identifier** and bank details in
> [Settings → Payments → General](settings.md#sepa-direct-debit).

## Mandates

A **mandate** is the member's authorisation to direct-debit charges to their account. Each mandate
has a **reference**, the account **holder** and the account **IBAN/BIC**, a **type**
(**Recurrent** or **One-off**) and a **signature** (**Paper** or **Digital**).

Usual flow:

1. **New Mandate** for the member.
2. **Download PDF** of the mandate for signing.
3. **Upload Signed** document (PDF, JPG or PNG).
4. The mandate becomes **Active** and can be used in remittances.

**A member can only have one active mandate.** If you try to register a second one, Memship
rejects it and shows the reference and account of the current mandate. When a member changes bank,
**cancel the current mandate first** and then register the new one, the same order the paperwork
follows. If your instance comes from a version earlier than **2.18.0** and had duplicate active
mandates, the upgrade cancelled them and kept the most recent one.

The **IBAN** is validated when it is saved, **check digits included**, so an IBAN with one wrong
digit is rejected in the form instead of ending up in the bank file, where the bank would return
the whole remittance. You can paste it exactly as it appears on the statement: upper case and
spaces are normalised.

A mandate can be **cancelled** (an irreversible action); it becomes **Cancelled**. It can also be
recorded as **Expired**.

## Remittances

A **remittance** groups direct-debit receipts into a batch to send to the bank.

1. **New Remittance** and **Select Receipts**, only **issued** or **overdue** receipts with active
   SEPA mandates. You will see the number of receipts selected and the total.

   The **collection date** cannot be earlier than today. It is checked against the organisation's
   day, not the server's, because the bank rejects the entire file if it is. If it falls on a
   weekend, the form warns you but does not stop you: the minimum lead time and the settlement
   calendar are set by each bank.
2. **Generate XML** produces the **ISO 20022 pain.008** file, the standard for banks in the SEPA
   zone. **Download XML** and submit it in your online banking.

   **The file is generated only once and is never overwritten**: it is the record of what was sent
   to the bank. If you need a different one (because a mandate has changed, for example) **cancel
   the remittance and create it again**; cancelling it frees its receipts for another one.
3. **Mark Submitted** once you have submitted it to the bank.

   From that moment until you close the remittance, its receipts **cannot be marked paid or
   cancelled by hand**: there is an order in progress at the bank and Memship cannot claim
   otherwise. The two ways out are the following steps, importing the return or closing the
   remittance. A card or Bizum payment confirmed by the provider does mark the receipt as paid,
   because there the money really has moved; that is exactly the situation the warning in step 4
   describes.
4. **Import Returns**: SEPA only reports the collections that **fail**. Paste the return lines
   as **JSON** (the box in the dialog shows the format), with the receipt number and, if you have
   it, the reason; the bank's file is not uploaded as it is. Empty text is rejected: it does not
   mean "the bank has returned nothing". If there are no returns, **skip this step** instead of
   importing an empty list.

   The result groups the receipts by what happened to each one, **Returned**, **Already
   returned**, **Unchanged: their status does not allow a return**, **Duplicate lines in the
   file**, **Not in this remittance** (indicating which one they are in) and **Not Found**, and
   names the receipts in each group. Only **issued** or **overdue** receipts can be marked as
   returned.

   **If any line belongs to a receipt that Memship records as paid, nothing is imported.** The
   bank says it has returned the money and Memship says it collected it: someone collected it
   another way while the debit was in progress. Review those receipts, decide which collection is
   the real one and import the file again without those lines.
5. **Collect what was returned again**: a return for insufficient funds is routine, and
   recovering it takes **two steps**, not one. On the returned receipt press **Re-emit**: it goes
   back to **Pending** status and leaves the remittance it was in, because a receipt cannot join a
   new remittance while it belongs to another. A **Pending** receipt is not yet offered for
   collection, so then press **Emit**, and it now appears in the **New Remittance** selector. It
   does not use up a new document number: it is the same receipt, with the same number.

   If you go to *New Remittance* right after **Re-emit** and the receipt does not appear, that
   second step is missing.
6. **Close** the remittance once the return period has passed. SEPA only reports the collections
   that fail, so closing marks every receipt in the batch that is still outstanding as **Paid**,
   with the remittance's collection date. Before confirming you will see how many receipts are
   going to be marked: **once the remittance is closed, returns can no longer be imported**, so do
   not close it before your bank's deadline expires.

Remittance statuses: **Draft → Ready → Submitted → Processed → Closed** (or **Cancelled**;
cancelling unlinks all the receipts). A **Submitted** remittance can be closed directly, without
going through **Processed**: the batch in which everyone has paid has no returns to import.

### What you see in a remittance already submitted

The counters on the record, **Receipts** and **Amount**, are the record of **what was sent to the
bank** and are not recalculated: the bank has that file, and changing the figure afterwards would
rewrite what it was asked for. A remittance in **Draft** or **Ready** is recalculated, because a
file can still come out of it and it has to ask for exactly what it says.

That is why the receipts table of a submitted remittance also includes the ones that **have
already left it**, the returned receipt you re-emitted, for example. Each such line says so, with
the date and the reason (*returned and re-emitted*, *receipt voided*, *paid another way*, *batch
cancelled*), and shows the status the receipt has **now**, which is what tells you what is left to
do: a re-emitted receipt appears as **Pending**, which means it still has to be issued again. The
line's amount is the one the remittance carried, not the one the receipt has today.

If the remittance was submitted from an installation earlier than 2.19.0, there is no record of
the receipts that had already left it: that table did not exist, so those remittances show only
what they kept.
