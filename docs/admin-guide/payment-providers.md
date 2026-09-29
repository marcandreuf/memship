# Payment providers — Setup Guide

**Who this is for:** the person who runs a memship installation for their club or association (the **superadmin**).
**What it covers:** everything under **Settings → Payments → Providers** — connecting **Stripe** for card payments, and **Redsys** for the Spanish bank gateway and **Bizum**.

You do not need to edit any file or restart anything. Every credential in this guide is entered in the web interface and takes effect on the next request.

---

## Table of contents

1. [Before you start](#1-before-you-start)
2. [How secrets are protected](#2-how-secrets-are-protected)
3. [How an online payment actually completes](#3-how-an-online-payment-actually-completes)
4. [Stripe](#4-stripe)
   - [What you need](#41-what-you-need)
   - [Obtaining the API keys](#42-obtaining-the-api-keys)
   - [Creating the webhook endpoint](#43-creating-the-webhook-endpoint)
   - [Filling in the screen](#44-filling-in-the-screen)
   - [Testing](#45-testing)
   - [Stripe troubleshooting](#46-stripe-troubleshooting)
5. [Redsys and Bizum](#5-redsys-and-bizum)
   - [What you need](#51-what-you-need)
   - [Obtaining the credentials from your bank](#52-obtaining-the-credentials-from-your-bank)
   - [Why there is no webhook to configure](#53-why-there-is-no-webhook-to-configure)
   - [Filling in the screen](#54-filling-in-the-screen)
   - [Testing](#55-testing)
   - [Redsys troubleshooting](#56-redsys-troubleshooting)
6. [Activation, test mode, and what members see](#6-activation-test-mode-and-what-members-see)
7. [Field reference](#7-field-reference)

---

## 1. Before you start

**Access.** Payments is visible only to users with the **superadmin** role. A plain admin does not see the tab. Go to **Settings → Payments**, then the **Providers** sub-tab.

**A public address.** Both providers need to reach your installation from the internet to confirm a payment. That address is configured once at install time in `BACKEND_PUBLIC_URL` and `FRONTEND_URL`. A provider configured on an installation that the internet cannot reach will take money and never mark the receipt paid.

**Direct debit is a different thing.** If your members pay by SEPA direct debit, none of this applies — see [SEPA](sepa.es.md). This guide is only about paying online by card or Bizum.

---

## 2. How secrets are protected

The same rules apply here as everywhere else in Settings, and they are described in full in [Integrations → How secrets are protected](integrations.md#2-how-secrets-are-protected). In short:

- Secret values are **encrypted before being stored** in the database.
- They are **never sent back to the browser**. After saving, the field shows `****` plus the last four characters. That is expected, not a bug.
- **Back up the encryption key file together with your database.** Restoring a dump on a machine with a different key file leaves the stored secrets undecryptable and you will have to re-enter them.

Which fields are treated as secret differs by provider, and it is not arbitrary — a publishable key is meant to be public, so it is stored in the clear and shown in full.

| Provider | Encrypted | Stored in the clear |
|---|---|---|
| Stripe | `secret_key`, `webhook_secret` | `publishable_key` |
| Redsys | `secret_key` | `merchant_code`, `terminal_id`, `environment`, `currency_code` |

---

## 3. How an online payment actually completes

This is worth understanding before configuring anything, because it explains what the credentials are *for* and why a misconfiguration is quiet rather than loud.

When a member pays, three things happen, and only one of them is authoritative:

1. **memship sends the member to the provider.** For Stripe this is a redirect to a Checkout session; for Redsys it is an auto-submitted signed form to the bank's TPV page.
2. **The member pays, and their browser comes back** to a memship page. **This return is not the confirmation.** The member can close the tab, lose signal, or hit back — and the browser is not a party memship can trust about whether money moved.
3. **The provider makes a server-to-server call to memship** confirming the outcome. **This is the source of truth**, and it is the only thing that marks a receipt paid.

Everything in this guide about webhooks, notification URLs and signing keys exists to make step 3 work and to prove the call really came from the provider.

**That is also why a broken configuration is quiet.** The receiving endpoint is unauthenticated by design — security comes from verifying the provider's signature, not from a login. If the signing secret is wrong, every confirmation fails verification and is discarded. From the member's side the payment succeeded; in memship the receipt simply stays unpaid, and no screen reports an error. **Always complete a real test payment end to end before announcing a payment method to members.**

---

## 4. Stripe

Stripe handles card payments through Stripe Checkout, a payment page hosted by Stripe. Card details never reach your server.

### 4.1 What you need

A Stripe account, and from it three values: a **secret key**, a **publishable key**, and a **webhook signing secret**. The first two come from the API keys page. The third does not exist yet — you create it in step 4.3.

### 4.2 Obtaining the API keys

1. Sign in at [dashboard.stripe.com](https://dashboard.stripe.com).
2. Go to **Developers → API keys** ([docs](https://docs.stripe.com/keys)).
3. Copy the **Publishable key** — it begins `pk_`.
4. Reveal and copy the **Secret key** — it begins `sk_`.

Stripe keeps separate keys for test mode and live mode, selected by the toggle in the dashboard. Test keys read `pk_test_` / `sk_test_`, live keys `pk_live_` / `sk_live_`. Use test keys until you have completed a test payment end to end.

> memship checks that the secret key starts with `sk_` and the publishable key with `pk_`, and refuses to save a value in the wrong field. It does **not** check which mode a key belongs to — pairing a live secret key with a test publishable key is accepted and will fail at payment time.

### 4.3 Creating the webhook endpoint

**This is the step people get stuck on, so read the next sentence carefully.** The webhook is something *you* create in Stripe, pointing at memship. memship does not create anything in your Stripe account. The secret you end up pasting into memship is issued by Stripe *after* the endpoint exists.

**The URL you need is:**

```
https://<your-memship-address>/api/v1/webhooks/stripe
```

Use the same address as `BACKEND_PUBLIC_URL`. The `/api/v1/` prefix matters: the bundled reverse-proxy configuration routes only `/api/v1/*` to the API and sends everything else to the web interface, so a URL without it reaches the wrong service and Stripe will report failures.

Then, in the Stripe dashboard ([webhook docs](https://docs.stripe.com/webhooks)):

1. Go to **Developers → Webhooks → Add endpoint**.
2. **Endpoint URL** — the URL above.
3. **Events from** — *Your account*.
4. **Payload style** — **Snapshot**. This matters: memship reads the full event object, and a *Thin* payload carries only identifiers, so confirmations would arrive with nothing to act on.
5. **API version** — the default is fine. memship pins no version and reads only long-stable Checkout Session fields.
6. **Select events** — choose exactly these two:
   - `checkout.session.completed`
   - `checkout.session.expired`
7. Create the endpoint, then **reveal the Signing secret**. It begins `whsec_`. This is the value memship calls **Webhook Secret**.

> **Subscribe to those two events only.** memship ignores every other event type, so subscribing to more does no harm beyond generating traffic and noise in your Stripe logs — but a dashboard full of deliveries memship deliberately discards makes a real problem harder to spot.

### 4.4 Filling in the screen

In **Settings → Payments → Providers**, add a Stripe provider and enter:

| Field | Value |
|---|---|
| Secret Key | the `sk_…` key from 4.2 |
| Publishable Key | the `pk_…` key from 4.2 |
| Webhook Secret | the `whsec_…` secret from 4.3 |

A newly created provider starts **disabled**. Configure it first, test it, then activate it.

> **The Webhook Secret is not format-checked.** Unlike the other two fields, memship accepts whatever you paste here. If you paste the wrong value — a secret key, an old secret from a deleted endpoint — nothing complains at save time and payments will silently fail to confirm. Check the value begins `whsec_` yourself.

### 4.5 Testing

**The Test button makes a real call to Stripe.** It retrieves your account and, on success, shows your account's display name or ID and its country. That proves the secret key works. It does **not** test the webhook secret, which cannot be verified without a real event.

To test the webhook, take a receipt through a real payment with Stripe in test mode and [a test card](https://docs.stripe.com/testing). Then confirm two things:

- the receipt in memship moved to **paid**
- the delivery in **Stripe → Developers → Webhooks** shows a `2xx` response

A delivery showing `400` with a signature error means the Webhook Secret is wrong.

### 4.6 Stripe troubleshooting

| Symptom | Cause |
|---|---|
| Test button reports an authentication error | The secret key is wrong, revoked, or belongs to the other mode |
| Payment completes at Stripe, receipt stays unpaid, Stripe shows `400` | Webhook Secret is wrong |
| Payment completes, receipt stays unpaid, Stripe shows no delivery at all | The endpoint URL is wrong or unreachable from the internet |
| Stripe shows `404` | The URL is missing the `/api/v1/` prefix, so it reached the web interface instead of the API |
| Receipt stays unpaid, everything else looks correct | See the amount-mismatch note below |

> **A payment for the wrong amount is refused on purpose.** memship compares the amount Stripe reports against the receipt total and, if they differ, **leaves the receipt unpaid** and logs an error for a person to review. A valid signature proves Stripe sent the message, not that the sum is the one you asked for. This looks exactly like a broken webhook, so check the backend log before concluding the configuration is wrong.

---

## 5. Redsys and Bizum

Redsys is the gateway used by most Spanish banks, operating the *TPV Virtual*. The same provider entry also serves **Bizum** — it is a payment method within Redsys, not a separate connection to configure.

### 5.1 What you need

Your bank must have issued you a TPV Virtual. From the contract or the bank's portal you need four values: the **merchant code (FUC)**, a **terminal number**, a **signing key**, and to know whether you are working against the test or production environment.

### 5.2 Obtaining the credentials from your bank

These do not come from a self-service dashboard the way Stripe's do — they are issued by whichever bank sold you the TPV, and the portal differs by bank. Redsys publishes the technical documentation at [pagosonline.redsys.es](https://pagosonline.redsys.es/).

- **Merchant Code (FUC)** — your merchant identifier, 7 to 9 digits.
- **Terminal ID** — numeric, usually `1` unless your bank issued several.
- **Signing Key** — the secret used to sign requests and verify notifications. In bank portals it is usually labelled *clave secreta de encriptación* or *clave de firma*. **The test and production environments have different keys.**
- **Currency Code** — ISO 4217 numeric. For euro this is **978**, which is the default.

### 5.3 Why there is no webhook to configure

Unlike Stripe, **you do not register a notification URL anywhere.** memship includes the callback address with every individual payment request, so the gateway is told where to reply each time. There is nothing to set up in the bank's portal and nothing to keep in sync.

For the same reason there is no separate webhook secret. The **Signing Key** does both jobs: memship signs outgoing requests with it and verifies incoming notifications against it. One value, entered once.

If you ever need to know the address memship sends, it is `https://<your-memship-address>/api/v1/webhooks/redsys` — but you should not have to configure it anywhere.

### 5.4 Filling in the screen

| Field | Value |
|---|---|
| Merchant Code (FUC) | 7–9 digits, from your bank |
| Terminal ID | numeric, from your bank |
| Signing Key | the signing key **for the environment you selected** |
| Environment | `test` while testing, `production` when live |
| Currency Code | `978` for euro |

> **Check the Environment field before every go-live.** memship falls back to the **test** gateway when the environment is anything it does not recognise. A typo does not raise an error — it quietly sends real members to the test TPV, where their payments do not exist.

### 5.5 Testing

**The Test button does not contact Redsys.** Redsys has no endpoint to ping, so the button validates your configuration locally. It is deliberately stricter than saving: it rejects a merchant code that is not 7 to 9 digits, which is the length a real TPV refuses outright.

Real testing means a payment against the test environment, with the test signing key and the card numbers your bank provides. Confirm the receipt moves to **paid** afterwards — the browser returning to a success page is not confirmation, as explained in section 3.

### 5.6 Redsys troubleshooting

| Symptom | Cause |
|---|---|
| Test button reports the merchant code must be 7–9 digits | The FUC is wrong, or has spaces or letters in it |
| Gateway rejects the payment immediately | The signing key does not match the environment |
| Payments succeed but land nowhere you can find | Environment is `test` (or a typo falling back to it) while you believed it was production |
| Receipt stays unpaid after a successful payment | The notification could not reach your installation — check that it is reachable from the internet |
| `SIS0051 — Pedido repetido` | A duplicate order number. memship generates a fresh random prefix per attempt, so this should be rare; retrying issues a new one |

---

## 6. Activation, test mode, and what members see

A provider has three states:

| Status | Meaning |
|---|---|
| **disabled** | Configured but not offered. Members see no button for it |
| **test** | Offered, for trying the flow end to end |
| **active** | Offered to members as a real payment method |

**memship refuses to activate a provider that could not take a payment.** Activation is the last moment an incomplete configuration is still a settings problem — past it, the missing field resurfaces as a failed payment on a member's screen. If activation is refused, the message names the fields at fault.

This check is local. It confirms your configuration is internally coherent; it cannot know that a key was revoked at the provider yesterday. That is one more reason to complete a real payment before relying on it.

---

## 7. Field reference

**Stripe**

| Field | Required | Secret | Format checked | Where it comes from |
|---|---|---|---|---|
| Secret Key | yes | yes | must start `sk_` | Stripe → Developers → API keys |
| Publishable Key | yes | no | must start `pk_` | Stripe → Developers → API keys |
| Webhook Secret | yes | yes | **no** | Stripe → Developers → Webhooks, after creating the endpoint |

**Redsys**

| Field | Required | Secret | Format checked | Where it comes from |
|---|---|---|---|---|
| Merchant Code (FUC) | yes | no | digits only; 7–9 on Test | your bank |
| Terminal ID | yes | no | digits only | your bank |
| Signing Key | yes | yes | no | your bank, per environment |
| Environment | yes | no | `test` or `production` | your choice |
| Currency Code | yes | no | exactly 3 digits | ISO 4217 — `978` for euro |

---

## Related

- [Payments](payments.es.md) — using payments day to day, in Spanish
- [SEPA](sepa.es.md) — direct debit, a separate mechanism
- [Integrations](integrations.md) — SSO and email, and the full description of secret storage
- [Configuration reference](../self-hosting/configuration.md) — `BACKEND_PUBLIC_URL` and `FRONTEND_URL`
