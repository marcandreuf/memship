<!-- source: es/admin-guide/settings.md -->
<!-- source-hash: 3303faf41a8e -->

# Organisation settings

General settings, invoicing, SEPA, payment providers and automations. Requires administration
permissions.

> **In Spanish:** [Configuración de la organización](../../es/admin-guide/settings.md).

## Organisation details

- **Organization Info**: name, legal name, tax ID (CIF/NIF), email, phone and website.
- **Branding**, **Brand Color** and **Logo** (JPG, PNG, WebP or SVG).
- **Address**, used on receipts and legal documents.
- **Localization**, **Default Language** (used for receipts, emails and number formatting),
  timezone, currency and date format.

## Banking and invoicing

- **Banking**: the organisation's bank name, **IBAN** and **BIC / SWIFT**.
- **Invoicing**: **Invoice Prefix**, **Next Invoice Number** and **Annual Numbering Reset**
  (restarts the numbering at the start of each year).
- **Default VAT Rate**: the rate applied by default when calculating receipts.

## SEPA direct debit

- **Creditor ID**: the SEPA creditor identifier (e.g.
  `ES12000B12345678`), required to generate remittances.
- **SEPA Format**: ISO 20022 **pain.008**, the standard for banks in the SEPA area.

See [SEPA direct debit](sepa.md) for the mandate and remittance flow.

## Payment providers

Configure the credentials of the **online payment** gateways that members will see under
*Pay Now*: **Stripe**, **Redsys**, **Bizum** (through Redsys, with its own **Offer Bizum**
switch, off by default) and **SEPA direct debit**. Each
provider has a **Display Name**, a **status** (Active / Test / Disabled) and the
**Test Connection** option to validate the configuration.

> The credential details and return URLs for each provider are covered in the
> [self-hosting guide](../self-hosting/configuration.md).

## Recurring billing

Automatically generates membership fee receipts on a schedule:

- **Enable recurring billing**.
- **Day of month** (1–28) on which it runs. Quarterly and annual fees are only billed
  in the first month of their period.
- An optional **Notification email** that receives a summary after each run.

## Payment reminders

Sends automatic emails to members with overdue receipts:

- **Days after due date** before the first reminder.
- **Repeat every (days)** between successive reminders.
- **Maximum reminders** per receipt (1–10).

## Emails to members

Under **Members → Communications**, below the announcements switch, you choose **which emails
the system sends**. Each email has its own switch, grouped by area (account and access,
sign-ups, activities, bookings, billing, announcements).

Three kinds:

- **Mandatory**: email verification and password reset. They appear
  locked and cannot be switched off: without them a new account cannot be activated, nor can
  access to an existing one be recovered.
- **Operational**: the member gains or loses something and gets no other notice (place freed up,
  booking cancelled by the club, receipt sent, payment reminder). They can be switched off, but
  the screen first warns what the member will stop receiving.
- **Optional**: confirmations the member also sees in the portal, the internal billing
  summary and the email delivery of announcements.

A switched-off email stops being sent on the next attempt; no restart is needed. An
installation that never visits this screen sends every email, as before.

## Other options

- **Communications**: enables sending [announcements](communications.md).
- **Member Card**: enables the [digital member card](member-cards.md) and its numbering.
- **Profile fields**: enables [custom fields](custom-fields.md).
- **Gender Options**: configures the options available in member forms.
