# 00 — Environment setup guide

> **Simulated engagement.** "Glow & Grace" is a fictional client. All accounts below are free, trial or sandbox accounts owned by the consultant. No real customer data is used.

This guide sets up every account and tool the project needs and ends with one working API call to each system. You do every step yourself. **Never paste a secret (token, key, client secret, refresh token) into a chat, a document or a commit.** Secrets go in exactly two places:

1. Your local `.env` file (git ignores it).
2. The **Current value** column of your Postman environment (Postman keeps it on your machine; the *Initial value* column syncs to Postman's cloud, so leave that empty).

Estimated time: 2–3 hours, mostly waiting for sign-up emails.

---

## What changed recently (read this first)

Many tutorials online are out of date for this setup. As of November 2026, the official docs say:

| System | Old way (in most tutorials) | Current way (used in this guide) | Source |
|---|---|---|---|
| Shopify | Create a "custom app" in the store admin and copy the Admin API token | Admin-created custom apps can no longer be created. Create the app in the **Dev Dashboard** and exchange its Client ID + Client secret for a 24-hour token (client credentials grant) | [Get API access tokens for Dev Dashboard apps](https://shopify.dev/docs/apps/build/dev-dashboard/get-api-access-tokens) |
| Shopify | REST Admin API | **GraphQL Admin API** for calls we make. (The webhook payloads Shopify *sends us* are still plain JSON.) | [Admin API versioning](https://shopify.dev/docs/api/usage/versioning) |
| HubSpot | Private app access token | Creating legacy private apps was switched off on 26 Oct 2026 for existing accounts. The replacement for system-to-system REST calls is a **Service key** | [Legacy private app creation being disabled](https://developers.hubspot.com/changelog/legacy-private-app-creation-sunset) · [Service keys](https://developers.hubspot.com/docs/apps/developer-platform/build-apps/authentication/account-service-keys) |

If anything you see on screen differs from this guide, the platform has changed again. Stop, take a screenshot (with secrets hidden) and we'll adjust.

---

## Step 1 — Python environment (15 min)

You already have Python 3.14, which meets the 3.11+ requirement. In the VS Code terminal (PowerShell), from the repo root:

```powershell
py -3 -m venv .venv                      # create an isolated Python environment in .venv/
.\.venv\Scripts\Activate.ps1             # switch this terminal into it; the prompt shows (.venv)
python -m pip install -r requirements.txt
Copy-Item .env.example .env              # your private settings file; fill it in as you go
```

If activation fails with "running scripts is disabled on this system", run this once and retry:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

**Why a virtual environment?** It keeps this project's library versions separate from anything else on your machine, so "it works on my laptop" means the same thing on anyone else's.

---

## Step 2 — Shopify: development store and app (40 min)

The Shopify side has three parts: the **store** (where orders happen), the **app** (the identity our integration uses to read data) and the **install** (the store granting that app permission).

### 2a. Developer account and development store

1. Go to [shopify.dev](https://shopify.dev) and sign up or log in, then open the **Dev Dashboard**.
2. Create a development store from the Dev Dashboard's **Dev stores** page. **This matters:** a store created anywhere else (for example, from the normal Shopify admin) is not in your organization, and the token request in Step 7 will fail with `shop_not_permitted`.
3. Suggested store name: `glow-and-grace-dev`. The part before `.myshopify.com` is your `SHOPIFY_STORE` value.
4. In the store admin, go to **Settings → General** and set the store address to India and the currency to **INR**. GST logic in later phases depends on this.

### 2b. Create the app

Follow [Create apps using the Dev Dashboard](https://shopify.dev/docs/apps/build/dev-dashboard/create-apps-using-dev-dashboard):

1. **Apps → Create app → Start from Dev Dashboard**. Name it `o2c-integration-hub`.
2. On the app's **Versions** page, fill in:
   - **App URL:** leave the default `https://shopify.dev/apps/default-app-home` (our app has no screen inside Shopify).
   - **Webhooks API version:** `2026-10` (latest stable at time of writing).
   - **Scopes:** `read_orders`, `read_customers`, `read_products`. These are read-only because Shopify is the *source* of orders; we never write back to it. This is "least privilege": ask only for what you need.
3. Click **Release**.

### 2c. Protected customer data

Orders contain customer names, emails and addresses, which Shopify treats as **protected customer data**. For an app installed only on a development store, you must still fill in the access request (which data, and why), but you **don't** need to submit it for review. See [Work with protected customer data](https://shopify.dev/docs/apps/launch/protected-customer-data).

- Select: name, email, phone, address.
- Reason, in your own words: "Sync order customers to CRM and raise GST invoices in accounting."

### 2d. Install and copy credentials

1. In the app, use **Install app** and choose your `glow-and-grace-dev` store.
2. In the app's **Settings**, copy the **Client ID** and **Client secret** into `.env` (`SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`).

**Interview point:** the client secret has two jobs. It gets us an access token, and Shopify also uses it to sign every webhook it sends us. In Phase 5 our app recalculates that signature (HMAC) to prove a webhook really came from Shopify.

### 2e. Add a few test products

Create 3 products with INR prices, for example: "Vitamin C Face Serum 30ml" ₹899, "Hydrating Gel Moisturiser 50g" ₹649, "SPF 50 Sunscreen 50ml" ₹549. These are fictional; HSN codes and GST rates are decided in Phase 3.

---

## Step 3 — HubSpot: free CRM and service key (20 min)

1. Sign up for the free HubSpot CRM at [hubspot.com](https://www.hubspot.com). Use a portfolio account name such as "Glow & Grace (Simulated)".
2. Create a service key ([official steps](https://developers.hubspot.com/docs/apps/developer-platform/build-apps/authentication/account-service-keys)):
   1. Go to **Development**, then in the left sidebar **Keys → Service keys**.
   2. **Create service key**, name it `o2c-integration-hub`.
   3. **Add new scope**, tick these four and click **Update**:
      - `crm.objects.contacts.read`
      - `crm.objects.contacts.write`
      - `crm.objects.deals.read`
      - `crm.objects.deals.write`
   4. **Create**, confirm, then copy the key into `.env` as `HUBSPOT_SERVICE_KEY`.

**Open questions, and what Phase 0 found:**
- *Are service keys available on the free CRM tier?* **Yes (confirmed 13 Nov 2026).** A service key created on this project's free CRM account passed the contacts read check. Fallbacks, if a future account lacks **Keys → Service keys**: a HubSpot project-based app with a static token (needs the HubSpot CLI) or a documented mock.
- *Does linking a deal to a contact (an "association") need an extra scope?* Still open. We'll check the associations API reference in Phase 3 before writing that code.

Rate limits for privately distributed apps on free accounts (service keys follow the same limits): **100 requests per 10 seconds** and **250,000 per day**. We'll design the retry logic around these.

---

## Step 4 — Zoho Books (India edition) and API access (40 min)

### 4a. Create the organisation

1. Sign up at [zoho.com/in/books](https://www.zoho.com/in/books/). Zoho Books India lists a permanent **Free plan** ([pricing](https://www.zoho.com/in/books/pricing/pricing-comparison.html)). If sign-up puts you on a paid-plan trial, that is fine too; note which one you got.
2. Organisation name: `Glow & Grace (Simulated)`. Country: **India**. State: **Haryana** (a simulated choice, recorded in Discovery; it decides when we charge CGST+SGST vs IGST).
3. **Check your Zoho Books web address.** It should be `books.zoho.in`. That `.in` means your data lives in Zoho's India data centre, which is why `.env.example` uses `accounts.zoho.in` and `www.zohoapis.in`. If you see `.com`, tell me; the URLs change.
4. **Skip GST setup for now** if Zoho asks for a GSTIN. Don't enter any real business's GSTIN. We configure tax settings deliberately in Phase 3.

### 4b. Create API credentials (Self Client)

A **Self Client** is Zoho's option for a back-end program that only talks to *your own* organisation, with no login screen. It fits our server-to-server integration.

1. Open the Zoho API Console for India: `https://api-console.zoho.in`.
   *Confirmed 13 Nov 2026:* the `.in` console works for an India-edition organisation, and the resulting client is **not** recognised by `accounts.zoho.com` (`invalid_client`). Zoho's Books docs link to `api-console.zoho.com`, but tokens must be generated on the same data centre as your account. ([Zoho multi-DC docs](https://www.zoho.com/accounts/protocol/oauth/multi-dc.html))
2. **Add client → Self Client → Create Now.**
3. In the **Client Secret** tab, copy Client ID and Client Secret into `.env` and Postman.
4. Have Postman open and ready (Step 7) **before** the next part, because the code it gives you expires in minutes.
5. In the **Generate Code** tab:
   - **Scope** (one line, comma-separated, no spaces):
     `ZohoBooks.contacts.ALL,ZohoBooks.invoices.ALL,ZohoBooks.customerpayments.ALL,ZohoBooks.creditnotes.ALL,ZohoBooks.settings.READ`
   - **Time duration:** the longest option offered (you need time to paste it).
   - **Description:** `o2c-integration-hub phase 0`.
   - **Create**, and choose your Zoho Books organisation if asked.
6. Copy the code into Postman as `zoho_grant_code` and run **Zoho Books › 1. Exchange grant code** immediately (Step 7).
   **Quicker alternative (no Postman):** run `.\.venv\Scripts\python.exe scripts\zoho_exchange_grant_code.py` first, then generate the code and paste it at the hidden prompt. The script saves `ZOHO_REFRESH_TOKEN` and `ZOHO_ORGANIZATION_ID` into `.env` without displaying them.

**Common mistake:** a grant code, an access token and a refresh token all look alike (`1000.<hex>.<hex>`). If the connectivity check says `invalid_code` on token refresh, the value in `ZOHO_REFRESH_TOKEN` is not a valid refresh token; generate a new grant code and exchange it again.

**What these scopes mean:** customers (contacts), invoices, payments and credit notes are the four things our flows create, and `settings.READ` lets us read organisation details and, we expect, items and taxes. Scope names come from the [Zoho Books OAuth page](https://www.zoho.com/books/api/v3/oauth/). I found no single "full access" scope documented there, so we list each one; that is least privilege anyway. If Phase 3 shows we need to create items, we'll regenerate with `ZohoBooks.settings.ALL`, a 2-minute job.

**Token lifecycle (useful in interviews):**

| Token | Lifetime | Where it lives |
|---|---|---|
| Grant code | Minutes, single use | Nowhere; used once and thrown away |
| Refresh token | Until revoked | `.env` as `ZOHO_REFRESH_TOKEN` (treat it like a password) |
| Access token | 1 hour | In memory; the app asks for a new one using the refresh token |

---

## Step 5 — Make (free plan) (10 min)

1. Sign up at [make.com](https://www.make.com). Any hosting region is fine.
2. Note the free-plan limits on the [pricing page](https://www.make.com/en/pricing). It states **1,000 credits per month**, and the account's **Subscription** page confirms it (13 Nov 2026). The number of active scenarios and the minimum schedule interval are not shown there; confirm them in Phase 4 from the scenario schedule settings, because they affect the Make design.
3. Nothing to build yet. We connect Shopify, HubSpot and Zoho inside Make in Phase 4.

---

## Step 6 — ngrok (10 min)

Shopify must send webhooks to a public HTTPS address, but our FastAPI app runs on `localhost`. ngrok creates a temporary public URL that forwards to your laptop.

1. Create a free account at [ngrok.com](https://ngrok.com) and install it from [ngrok.com/download](https://ngrok.com/download) (or `winget install ngrok.ngrok`).
   **Then run `ngrok update`.** Free accounts require agent version 3.29.0 or newer (`ERR_NGROK_121`), and in Nov 2026 winget installed 3.3.1.
2. Copy your **authtoken** from [Your Authtoken](https://dashboard.ngrok.com/get-started/your-authtoken) in the ngrok dashboard. Don't confuse it with an API key or AI Gateway key, which start with `ng-` and give `ERR_NGROK_105` if used here. Then run:
   `ngrok config add-authtoken <your-token>`
   This saves the token in ngrok's own config file in your user profile, not in this repo.
3. Test: `ngrok http 8000`. You should see a `Forwarding https://….ngrok-free.app → http://localhost:8000` line. Press Ctrl+C to stop. (Nothing is listening on port 8000 yet; that comes in Phase 5.)

---

## Step 7 — Postman: one working call per system (20 min)

1. Install the [Postman desktop app](https://www.postman.com/downloads/) and create a workspace called `O2C Integration Hub`.
2. **Import** both files from `postman/`:
   - `o2c-integration-hub.postman_collection.json`
   - `o2c-local.postman_environment.template.json`
3. Select the environment **O2C — local** (top right). Fill in the **Current value** column only.
4. Run these in order. Each has automatic tests; green ticks in the **Test Results** tab mean success.

| # | Request | Success looks like | Common failure |
|---|---|---|---|
| 1 | Shopify › 1. Get access token | 200, `access_token`, `expires_in: 86399` | `shop_not_permitted`: store not created from Dev Dashboard (Step 2a) |
| 2 | Shopify › 2. Shop info | 200, your store name, `currencyCode: "INR"` | 401: run request 1 again (token expired after 24 h) |
| 3 | HubSpot › 1. List contacts | 200, `results` array | 401: wrong key · 403: missing scope |
| 4 | Zoho › 1. Exchange grant code | `access_token` and `refresh_token` returned | `invalid_code`: code expired or already used; generate a new one |
| 5 | Zoho › 3. List organizations | `code: 0`, your organisation listed | `invalid_oauthtoken`: run Zoho › 2. Refresh access token |

5. After request 4 succeeds, copy `zoho_refresh_token` from the Postman environment into `.env`. After request 5, copy `zoho_organization_id` too.

---

## Step 8 — Check everything from code (1 min)

```powershell
.\.venv\Scripts\python.exe scripts\check_connectivity.py
```

It makes one read-only call to each system using `.env` and prints `PASS` / `FAIL` / `SKIP` with a short reason (never a secret). This proves the *app's* configuration works, not just Postman's. Expected: `3/3 systems passed.`

---

## Done checklist

Status as of 13 Nov 2026:

- [x] `.venv` created, `pip install` finished without errors
- [x] `.env` exists, is filled in, and `git status` does **not** list it
- [x] Shopify dev store (INR) with products; app installed
- [x] HubSpot service key created (contacts read confirmed; other scopes exercised in Phase 3)
- [x] Zoho Books India org created; refresh token and organisation ID saved
- [x] Make account created; credits noted (scenario and interval limits: confirm in Phase 4)
- [x] ngrok installed, updated and authenticated; test tunnel came online
- [x] `scripts/check_connectivity.py` reports 3/3 passed (used in place of the Postman requests)

Outcome: all four systems are **live**; see *What is live vs mocked* in the [README](../README.md).
