# Integrations — Setup Guide

**Who this is for:** the person who runs a memship installation for their club or association (the **superadmin**).
**What it covers:** everything under **Settings → Integrations** — signing in with Google / Apple (**Single Sign-On**) and sending email (**Mailing**) — plus the registration options that go with them.

You do not need to edit any file or restart anything. Every credential in this guide is entered in the web interface and takes effect on the next request.

---

## Table of contents

1. [Before you start](#1-before-you-start)
2. [How secrets are protected](#2-how-secrets-are-protected)
3. [Single Sign-On (SSO)](#3-single-sign-on-sso)
   - [How it works for a member](#31-how-it-works-for-a-member)
   - [Common step: your public URL and redirect URIs](#32-common-step-your-public-url-and-redirect-uris)
   - [Google: obtaining the credentials](#33-google-obtaining-the-credentials)
   - [Apple: obtaining the credentials](#34-apple-obtaining-the-credentials)
   - [Filling in the screen](#35-filling-in-the-screen)
   - [SSO troubleshooting](#36-sso-troubleshooting)
4. [Mailing](#4-mailing)
   - [How it works](#41-how-it-works)
   - [Resend: obtaining the credentials](#42-resend-obtaining-the-credentials)
   - [Gmail: obtaining the credentials](#43-gmail-obtaining-the-credentials)
   - [Filling in the screen, testing and activating](#44-filling-in-the-screen-testing-and-activating)
   - [Mailing troubleshooting](#45-mailing-troubleshooting)
5. [Registration options that go with these integrations](#5-registration-options-that-go-with-these-integrations)
6. [Configuration file fallback (`.env`)](#6-configuration-file-fallback-env)
7. [Field reference](#7-field-reference)

---

## 1. Before you start

**Access.** Integrations is visible only to users with the **superadmin** role. A plain admin does not see the tab. Go to **Settings → Integrations**; inside it there are two sub-tabs: **Single Sign-On** and **Mailing**.

**A public address.** Both integrations assume your installation is reachable at a real address (for example `https://socios.myclub.org`), configured once at install time in `BACKEND_PUBLIC_URL` and `FRONTEND_URL`. The Integrations screen shows the backend URL read-only, with a copy button.

**HTTPS.** Google works over `http://localhost` for testing, but **Apple does not** — it refuses `localhost` and plain HTTP, and requires a real domain with a valid certificate. Plan on configuring Apple only on your live installation.

**Accounts you may need to create:**

| Integration | You need | Cost |
| ----------- | -------- | ---- |
| Google sign-in | A Google account (Google Cloud Console) | Free |
| Apple sign-in | An **Apple Developer Program** membership | Paid annual fee |
| Resend mail | A Resend account + a domain you control | Free tier available |
| Gmail mail | A Google account with 2-Step Verification on | Free |

You do not have to configure everything. Sign-in providers are optional (members can always use email + password). Mail is effectively required — without it, verification, approval and receipt emails are not delivered.

---

## 2. How secrets are protected

Some of the values you type here are real secrets: a Google client secret, an Apple private key, a Resend API key, a Gmail app password.

- They are **encrypted before being stored** in the database.
- They are **never sent back to the browser**. After saving, the field shows only `•••• ` plus the last four characters. This is expected — it is not a bug and there is no way to read a stored secret back out of the interface.
- The encryption key is **generated automatically** by the server on first use and written to a key file on the storage volume (never into the database). You do not have to create it.

At the top of each Integrations screen you will see one of two banners:

- 🟢 **"Encryption active"** — normal state. Nothing to do.
- 🟠 **"The server could not initialise its encryption key — check that the storage volume is writable."** — the server could neither read nor create its key file. Until this is fixed, secret fields cannot be saved (non-secret fields still can). Fix the permissions on the storage volume mounted into the backend container, then reload the page.

> **Back up the key file together with your database.** If you restore a database dump on a machine that has a *different* key file, the stored secrets can no longer be decrypted. Nothing crashes — memship falls back to whatever is in `.env`, and the affected fields simply behave as if empty — but you will have to re-enter every secret. The key file lives on the storage volume; its path is `SECRETS_KEY_FILE`, by default `<storage>/secret.key`.

**Editing rules for every secret field** (same in both sub-tabs):

- Leave it **blank** → the stored value is kept unchanged.
- Type a **new value** → it replaces the stored one.
- Click **Clear** → the stored value is wiped on save (click **Undo** to cancel before saving).

---

## 3. Single Sign-On (SSO)

**Settings → Integrations → Single Sign-On**

### 3.1 How it works for a member

Once you enable a provider, a **"Continue with Google"** / **"Continue with Apple"** button appears on both the login and the registration page. Buttons only appear for providers that are switched on and fully configured — nobody sees a button that would fail.

What happens when a person uses it:

1. They are sent to Google / Apple, sign in there, and are returned to memship.
2. **If they already have a memship account with the same, provider-verified email address**, the provider is linked to that existing account. From then on they can sign in either way — password or provider.
3. **If they are new**, an account and a member record are created for them with status **pending**, and the normal onboarding rules apply: they land on the *awaiting approval* screen until an admin approves them from **Members → pending registrations**. Approval is when the member number is allocated.
4. Their email counts as already verified (the provider vouched for it), so they receive no verification email.

Notes worth knowing:

- Accounts created through a provider **have no password**. If the person later wants to sign in with a password, they use the "forgot password" flow to set one.
- A single person can have password + Google + Apple all pointing at the same account.
- Public registration must be enabled for *new* people to sign up this way — see [section 5](#5-registration-options-that-go-with-these-integrations).

### 3.2 Common step: your public URL and redirect URIs

At the top of the SSO screen there is a card showing your **Backend URL**, and each provider card shows its **Redirect URI**. Both have a copy button. These are the values the provider consoles ask for. They look like:

```
Backend URL   https://socios.myclub.org
Google        https://socios.myclub.org/api/v1/auth/oauth/google/callback
Apple         https://socios.myclub.org/api/v1/auth/oauth/apple/callback
```

Copy them from the screen rather than typing them — they must match **character for character** on both sides, including `https://` and the absence of a trailing slash. A mismatch is the single most common cause of a failed sign-in.

If the backend URL shown is wrong (for example `http://localhost:8003` on a live server), it must be corrected in the installation's `BACKEND_PUBLIC_URL` variable; it is deliberately not editable from the screen, because it describes how your server is published, not how a provider is configured.

### 3.3 Google: obtaining the credentials

You need two values: a **Client ID** and a **Client secret**.

1. Go to **[Google Cloud Console](https://console.cloud.google.com/)** and sign in.
2. Create a project (top bar → project selector → **New project**), name it something like `Memship – My Club`, and select it.
3. In the left menu open **APIs & Services → OAuth consent screen**.
   - User type: **External** (unless every member has an account in your Google Workspace organisation — then Internal is fine).
   - App name: your club's name, as members will see it on Google's consent screen.
   - User support email and developer contact email: your address.
   - Scopes: the defaults `email`, `profile`, `openid` are all that is needed. Do not add anything else — extra scopes trigger Google's verification review.
   - Add your logo and a link to your site if you want the consent screen to look like you. Optional.
   - **Publish the app** (button **Publish app** → *In production*). While it is in *Testing* only the email addresses you list as test users can sign in.
4. Open **APIs & Services → Credentials → Create credentials → OAuth client ID**.
   - Application type: **Web application**.
   - Name: anything, e.g. `memship web`.
   - **Authorised redirect URIs → Add URI**: paste the Google redirect URI copied from the memship screen.
   - (Authorised JavaScript origins can be left empty — memship does the exchange server-side.)
   - **Create**.
5. Google shows the **Client ID** (ends in `.apps.googleusercontent.com`) and the **Client secret** (starts with `GOCSPX-`). Copy both now; the secret can be re-copied later from the same page.

### 3.4 Apple: obtaining the credentials

Apple needs **four** values: a Client ID (Services ID), a Team ID, a Key ID and a private key file. This is more work than Google — budget 20 minutes.

Requirements: a paid **Apple Developer Program** membership, and a live HTTPS domain (Apple rejects `localhost` and self-signed certificates).

1. Go to **[developer.apple.com/account](https://developer.apple.com/account)** → **Certificates, Identifiers & Profiles**.
2. **Create an App ID** — *Identifiers* → **+** → **App IDs** → **App**.
   - Description: your club's name. Bundle ID: e.g. `org.myclub.memship`.
   - In the capabilities list, tick **Sign in with Apple**. Register.
3. **Create a Services ID** — *Identifiers* → **+** → **Services IDs**.
   - Description: e.g. `Memship Web`. Identifier: e.g. `org.myclub.memship.web`.
   - ⚠️ **This identifier is the value memship calls Client ID.** It is *not* the App ID from step 2, and confusing them is the classic Apple setup mistake.
   - Register, then **open the Services ID again** and tick **Sign in with Apple → Configure**:
     - Primary App ID: the App ID from step 2.
     - **Domains and Subdomains**: your domain without the scheme — `socios.myclub.org`.
     - **Return URLs**: paste the Apple redirect URI copied from the memship screen (with `https://`).
     - Save, then **Continue / Save** on the Services ID itself.
4. **Create a key** — *Keys* → **+**.
   - Key name: e.g. `Memship Sign in with Apple`.
   - Tick **Sign in with Apple** → **Configure** → select the primary App ID → Save → Continue → Register.
   - **Download the `.p8` file.** ⚠️ Apple lets you download it **once**. If you lose it, revoke the key and create a new one.
   - Note the **Key ID** shown on that page (10 characters, e.g. `A1B2C3D4E5`).
5. **Find your Team ID** — top right of the Apple Developer account page, under your name / in **Membership details**. 10 characters, e.g. `9XYZ8ABCDE`.

You now have:

| memship field | Apple value | Example |
| ------------- | ----------- | ------- |
| Client ID | the **Services ID** identifier | `org.myclub.memship.web` |
| Team ID | Membership details → Team ID | `9XYZ8ABCDE` |
| Key ID | the key you created | `A1B2C3D4E5` |
| Private key (.p8) | the **whole contents** of the downloaded file | `-----BEGIN PRIVATE KEY-----…` |

For the private key, open the `.p8` file in a plain-text editor and copy everything, including the `-----BEGIN PRIVATE KEY-----` and `-----END PRIVATE KEY-----` lines.

### 3.5 Filling in the screen

For each provider card:

1. Paste the non-secret fields (Client ID, and for Apple also Team ID and Key ID).
2. Paste the secret field (Google client secret / Apple private key). It is a password-style input; it stays masked.
3. Press **Save**.
4. Flip the provider's **switch on**. The switch is disabled until all of that provider's fields are filled — saving credentials never turns a provider on by itself, so you decide when it goes live.
5. Press **Save** again. The badge on the card changes to **Live**.

Open the login page in a private window and confirm the button is there and completes a sign-in.

Extra markers you may see:

- **"from environment"** next to a label — that value is currently coming from the installation's `.env` file, not from what you typed here. Typing a value in the screen overrides it for that field. See [section 6](#6-configuration-file-fallback-env).
- **"stored"** next to a secret label — a secret is on file for that field.

### 3.6 SSO troubleshooting

| Symptom | Cause and fix |
| ------- | ------------- |
| Google: `Error 400: redirect_uri_mismatch` | The redirect URI in the Google console differs from the one on the memship screen. Copy it again with the copy button; check `https` vs `http`, `www`, and trailing slash. |
| Google: "Access blocked: this app has not completed the verification process" | The consent screen is still in *Testing*. Publish it, or add the person as a test user. |
| Google: `invalid_client` | Client ID and client secret do not belong to the same OAuth client, or the secret was truncated on paste. Re-copy both. |
| Apple: `invalid_client` | Almost always one of: the App ID was used instead of the **Services ID**; a wrong Team ID or Key ID; a `.p8` that was partially pasted. Re-check all four values. |
| Apple: "Invalid redirect_uri" / cannot save the Services ID | The Return URL must be `https`, on the exact domain listed in *Domains and Subdomains*, and cannot be an IP address or `localhost`. |
| Apple sign-in returns to the login page with an error | The callback from Apple is a cross-site POST and requires the site to be served over HTTPS. Apple does not work against a development install. |
| A member's name is blank after signing in with Apple | Apple sends the name **only the very first time** the person authorises your app. If you were testing, remove your app from *Apple ID → Sign in with Apple* on the account and try again — this is normal behaviour and harmless. |
| An Apple user has an address like `abc123@privaterelay.appleid.com` | The person chose "Hide My Email". Mail sent to that address is forwarded to them by Apple. Store it as is. |
| Provider button does not appear on the login page | Provider not switched on, a required field empty, or the credentials were saved but the toggle was never enabled. The card badge shows **Off** in that case. |
| A person signs in with a provider and lands on a *pending approval* screen | Expected for new registrations. Approve them from the members' pending-registrations list. |
| Someone with an existing password account signed in with Google and got a **new** account instead of their old one | The provider reported the email as unverified, so memship refused to link it (linking an unverified address would let anyone take over an account). Have them verify the address with the provider. |

---

## 4. Mailing

**Settings → Integrations → Mailing**

### 4.1 How it works

memship sends email for registration verification, approval/rejection notices, password resets, receipts, payment reminders and member communications. All of it goes through **one** provider, which you choose here.

Two providers are supported:

- **Resend** — a managed sending service, used through its API. Better deliverability, higher volume, needs a domain you control.
- **Gmail** — a normal Gmail (or Google Workspace) account used over SMTP. Quickest to set up, low daily limits.

**Exactly one provider is active at a time.** The screen has a single *Active provider* selector with three positions — **None / Resend / Gmail**. There are no per-provider on/off switches, so the "both enabled" state cannot happen. You can keep credentials for both on file and switch between them at any moment.

With the active provider set to **None**, memship sends nothing at all. Emails are silently skipped (they are logged, not queued for later). Members will not receive verification links, approval notices or receipts, so treat *None* as a temporary state.

### 4.2 Resend: obtaining the credentials

You need an **API key**, and ideally a **From address** on a domain you have verified.

1. Create an account at **[resend.com](https://resend.com)**.
2. **Domains → Add domain** — enter the domain you send from (e.g. `myclub.org`). Resend shows a set of DNS records (typically DKIM plus an SPF/MX entry for a `send.` subdomain).
3. Add those records at your DNS provider (whoever manages your domain), then press **Verify**. Propagation is usually minutes, occasionally hours.
4. **API Keys → Create API Key**.
   - Name: `memship`.
   - Permission: **Sending access** is enough.
   - Domain: the one you just verified (or *All domains*).
   - Copy the key — it starts with `re_` and is shown **only once**.
5. Decide your **From address**, e.g. `no-reply@myclub.org`. It must be on a verified domain; Resend rejects anything else.

> Just testing? Resend lets you send from `onboarding@resend.dev` without any domain, but only to the email address that owns the Resend account. Fine for a test send, not for real use.

### 4.3 Gmail: obtaining the credentials

You need the **Gmail address** and a Google **app password** — a 16-character password generated for one application. Your normal account password will not work; Google blocks it.

1. The account must have **2-Step Verification enabled**: [myaccount.google.com/security](https://myaccount.google.com/security) → *2-Step Verification*. App passwords do not exist without it.
2. Go to **[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)**.
3. Give the app a name (e.g. `memship`) and create it.
4. Google shows a 16-character password such as `abcd efgh ijkl mnop`. Copy it — like every secret here, it is displayed once. Spaces are cosmetic; with or without them works.

Things to know about the Gmail route:

- The server, port and encryption are fixed (`smtp.gmail.com`, port `587`, TLS). You do not enter them, and they cannot be changed from this screen.
- **Sending limits:** roughly 500 messages per day for a free Gmail account, ~2,000 for Google Workspace. Exceeding them gets the account temporarily blocked for sending. A club with a few hundred members doing a mass communication can hit this.
- Gmail **rewrites the From address** to the account's own address unless the alternative address is registered in that Gmail account ("Send mail as"). So the *From address* field is best left blank, in which case the Gmail address is used.
- If a Workspace administrator has disabled app passwords for the organisation, this route is not available.

### 4.4 Filling in the screen, testing and activating

Recommended order — configure, **test**, then activate:

1. Fill in the provider card:
   - **Resend**: *API key* (secret) and *From address*.
   - **Gmail**: *Gmail address*, *App password* (secret), and optionally *From address* (leave blank to send as the Gmail address).
2. Press **Save**. The card badge becomes **Ready**.
3. Press **Send test** on that card. A test message is sent **through that provider specifically**, even if it is not the active one — that is the whole point of the button: verify credentials before switching real traffic to them. It goes to your own address (the signed-in superadmin's email).
   - Success → a "Test email sent" confirmation. Check your inbox, and your spam folder.
   - Failure → the provider's error is shown in the message (an SMTP authentication failure, a Resend rejection, etc.).
   - The button is disabled while you have unsaved changes ("Save your changes before sending the test") or while required fields are missing.
4. Once the test arrives, set the **Active provider** selector to that provider and press **Save**. The badge becomes **Active**.

A provider that is missing required fields cannot be selected as active — the option is greyed out with a "Fill in the credentials before activating it" hint.

Switching providers later is a two-click operation: select the other provider, save. The credentials of the one you left are kept, so you can switch back.

### 4.5 Mailing troubleshooting

| Symptom | Cause and fix |
| ------- | ------------- |
| Test fails with an SMTP authentication error (`535`, "Username and Password not accepted") | The Gmail app password is wrong, or was revoked, or 2-Step Verification was turned off (which invalidates all app passwords). Generate a new one. |
| Test fails: Resend "domain is not verified" / 403 | The From address is not on a domain verified in Resend, or the DNS records have not propagated. Check *Domains* in Resend. |
| Test fails: Resend 401 / "API key is invalid" | Key mistyped, revoked, or created without sending permission. Create a new key. |
| Test reports success but nothing arrives | Check spam. For Resend, check the *Emails* log in its dashboard for a bounce. For Gmail, check the sending account's *Sent* folder. |
| Nothing is being sent at all, no errors anywhere | Active provider is **None**. Select a provider and save. |
| Members stop receiving mail after a working period | Gmail daily limit reached, or the app password was revoked; on Resend, a suspended domain. Use **Send test** to get the actual error. |
| The label says "from environment" | That value comes from the installation's `.env` file. It works, but anything you type in the screen takes precedence for that field. |
| Emails arrive from an address you did not configure | Gmail rewrote the From to the account address (expected), or an env-file value is still supplying it. |

---

## 5. Registration options that go with these integrations

Two organisation-level options govern the sign-up flow that SSO feeds into. They are **not on the Integrations screen** — there is no interface for them yet — and they live in the organisation settings' `features` object. Both default to **true**, which is the normal configuration:

| Option | Default | Effect |
| ------ | ------- | ------ |
| `public_registration` | `true` | Whether anyone can register at all, by form or by provider. Set to `false` for a closed club whose members are created by an admin. With it off, the register page and the provider buttons for *new* people are refused. |
| `registration_requires_approval` | `true` | Whether a new registration waits in *pending* for an admin. Set to `false` and a new registration becomes an active member immediately (member number allocated on the spot), skipping the approval queue. |

Changing them requires a call to the settings API (`PUT /api/v1/settings/`, superadmin) with the `features` object, or a direct update of the `organization_settings` row. Ask whoever administers your installation if you need one of them changed.

Related and independent of the above: email **verification** links are always sent, and they point at `FRONTEND_URL`. If verification links in your emails are wrong (e.g. `localhost`), that variable is misconfigured for your installation.

---

## 6. Configuration file fallback (`.env`)

Everything on the Integrations screen can also be supplied through the installation's `.env` file. This exists for two reasons: installations configured before these screens existed keep working untouched, and an operator can preseed credentials at deploy time.

**Precedence is per field: what you save in the screen wins; if a field is empty there, the environment variable is used.** The **"from environment"** badge tells you exactly which fields are currently coming from the file. Clearing a field in the screen makes it fall back to the environment value again, if there is one.

| Screen field | Environment variable |
| ------------ | -------------------- |
| Google → Client ID | `GOOGLE_CLIENT_ID` |
| Google → Client secret | `GOOGLE_CLIENT_SECRET` |
| Apple → Client ID (Services ID) | `APPLE_CLIENT_ID` |
| Apple → Team ID | `APPLE_TEAM_ID` |
| Apple → Key ID | `APPLE_KEY_ID` |
| Apple → Private key (.p8) | `APPLE_PRIVATE_KEY` |
| Resend → API key | `RESEND_API_KEY` |
| Resend → From address | `RESEND_FROM_EMAIL`, then `SMTP_FROM` |
| Gmail → Gmail address | `SMTP_USER` |
| Gmail → App password | `SMTP_PASSWORD` |
| Gmail → From address | `SMTP_FROM` |
| Backend URL (read-only) | `BACKEND_PUBLIC_URL` |
| — (secret encryption key) | `MEMSHIP_SECRET_KEY`, `SECRETS_KEY_FILE` |

Notes:

- `BACKEND_PUBLIC_URL` is **environment-only** by design — it describes how your server is published. It must be correct, because the redirect URIs are derived from it.
- `MEMSHIP_SECRET_KEY` only needs to be set if you want to supply the encryption key yourself instead of letting the server generate one. `SECRETS_KEY_FILE` chooses where the generated key is written — it must be on a **persistent** volume.
- On an installation that has never used these screens, mail keeps behaving exactly as before: Resend if `RESEND_API_KEY` is set, otherwise SMTP if `SMTP_HOST` is set. As soon as you save anything in the Mailing screen, the explicit *Active provider* selection takes over.

---

## 7. Field reference

### Single Sign-On

| Provider | Field | Secret | Where it comes from | Example |
| -------- | ----- | ------ | ------------------- | ------- |
| Google | Client ID | no | Cloud Console → Credentials → OAuth client | `1234-abc.apps.googleusercontent.com` |
| Google | Client secret | **yes** | same screen | `GOCSPX-…` |
| Apple | Client ID | no | Developer → Identifiers → **Services ID** | `org.myclub.memship.web` |
| Apple | Team ID | no | Developer → Membership details | `9XYZ8ABCDE` |
| Apple | Key ID | no | Developer → Keys → your key | `A1B2C3D4E5` |
| Apple | Private key (.p8) | **yes** | the downloaded key file's contents | `-----BEGIN PRIVATE KEY-----…` |

All fields of a provider are required before it can be switched on.

### Mailing

| Provider | Field | Secret | Required | Notes |
| -------- | ----- | ------ | -------- | ----- |
| Resend | API key | **yes** | yes | Starts with `re_`; shown once at creation. |
| Resend | From address | no | no | Must be on a domain verified in Resend. |
| Gmail | Gmail address | no | yes | The full address, e.g. `club@gmail.com`. |
| Gmail | App password | **yes** | yes | 16 characters, from Google app passwords. Not the account password. |
| Gmail | From address | no | no | Leave blank to send as the Gmail address. |

Server, port and encryption for Gmail are fixed at `smtp.gmail.com:587` with TLS and are not configurable.

---

## Quick checklist

**Sign-in with Google**
- [ ] Backend URL on the screen is your real public address
- [ ] Redirect URI copied from memship into the Google console, exactly
- [ ] Consent screen published
- [ ] Client ID + secret saved, switch on, badge says **Live**
- [ ] Button appears on the login page and a sign-in completes

**Sign-in with Apple**
- [ ] Live HTTPS domain (not localhost)
- [ ] App ID with *Sign in with Apple* enabled
- [ ] Services ID created, domain + return URL configured — **Services ID is the Client ID**
- [ ] Key created, `.p8` downloaded and stored safely, Key ID noted
- [ ] Team ID noted; all four fields saved, switch on, badge says **Live**

**Mail**
- [ ] Provider credentials saved, badge says **Ready**
- [ ] **Send test** succeeded and the message actually arrived
- [ ] Active provider selector set to that provider and saved, badge says **Active**
- [ ] Encryption banner is green
- [ ] Key file and database are backed up together