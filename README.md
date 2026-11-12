# O2C Integration Hub — Shopify → HubSpot → Zoho Books

> **⚠️ Simulated engagement — portfolio project.**
> "Glow & Grace" is a **fictional** Indian D2C skincare brand. All data, stakeholders, discovery answers and figures in this repository are simulated for demonstration. No real client, customer or business result is represented.

## The problem (simulated)

Glow & Grace sells on Shopify. An operations executive re-types every order into Zoho Books to raise GST invoices, and copies customer details into HubSpot by hand. This causes typing errors, wrong GST splits, duplicate customers, invoices raised 1–3 days late, no visibility into failed entries and painful month-end reconciliation.

## The solution

Automate order-to-cash so that every paid Shopify order flows to the CRM and the accounting system **correctly, exactly once**, with failures caught and visible.

| Flow | Trigger | Outcome |
|---|---|---|
| 1. Order-to-cash (core) | Shopify order paid | HubSpot contact + deal → Zoho Books customer → GST invoice → payment recorded → alert |
| 2. Refunds | Shopify refund | Zoho Books credit note → HubSpot deal updated |
| 3. Lead-to-customer (stretch) | Website form | HubSpot lead → deal won → Zoho Books customer |

Built twice, on purpose:
1. **No-code layer:** Flow 1 in Make (iPaaS).
2. **Custom-code layer:** a Python FastAPI service with webhook signature verification, payload validation, idempotency, retries and a failed-records store with re-processing.

## Architecture

_Diagram added in Phase 3._

## What is live vs mocked

Confirmed by the Phase 0 connectivity check on 13 Nov 2026 (`scripts/check_connectivity.py`, 3/3 passed).

| System | Status | Notes |
|---|---|---|
| Shopify (dev store) | **Live** | Dev Dashboard app, client credentials grant, GraphQL Admin API `2026-10`. Store currency INR. |
| HubSpot (free CRM) | **Live** | Service key (Bearer token). Contacts read confirmed; write and deals scopes are exercised in Phase 3. |
| Zoho Books (India) | **Live** | Self Client OAuth on the India data centre (`accounts.zoho.in`, `www.zohoapis.in`). |
| Make (free plan) | **Live** | 1,000 credits/month. Active-scenario limit and minimum schedule interval to be confirmed in Phase 4. |

## How to run

_Added in Phase 5._ Environment setup: [docs/00-setup-guide.md](docs/00-setup-guide.md).

Check that your `.env` credentials work (read-only, prints no secrets):

```powershell
.\.venv\Scripts\python.exe scripts\check_connectivity.py
```

## Documents

| # | Document | Status |
|---|---|---|
| 00 | [Setup guide](docs/00-setup-guide.md) | Done |
| 01 | [Discovery](docs/01-discovery.md) | Done |
| 02 | Requirements | Phase 2 |
| 03 | Architecture | Phase 3 |
| 04 | Field mapping | Phase 3 |
| 05 | Error handling | Phase 3 |
| 06 | Test plan | Phase 6 |
| 07 | Runbook | Phase 7 |
| 08 | Security | Phase 7 |
| 09 | Client summary | Phase 8 |

## Repository layout

```
docs/      engagement documents (discovery → handover)
samples/   example JSON payloads for every API step
make/      Make scenario blueprint export
app/       FastAPI integration service
scripts/   reconciliation and utilities
mocks/     mock HubSpot / Zoho Books servers
tests/     pytest unit and integration tests
postman/   Postman collection + environment template
```

## Security

No secrets are committed. Configuration lives in a local `.env` file (see [.env.example](.env.example)), which git ignores. Full security notes in Phase 7.

## License

MIT — see [LICENSE](LICENSE).
