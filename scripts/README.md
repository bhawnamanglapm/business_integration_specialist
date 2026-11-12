# scripts/

Command-line utilities. Run from the repo root with the project's Python: `.\.venv\Scripts\python.exe scripts\<name>.py`

| Script | What it does |
|---|---|
| `check_connectivity.py` | One read-only call each to Shopify, HubSpot and Zoho Books using `.env`. Prints PASS / FAIL / SKIP; never prints secrets. |
| `zoho_exchange_grant_code.py` | One-time Zoho setup: exchanges a Self Client grant code (hidden input) for a refresh token and saves it, plus the organisation id, into `.env`. |

Planned: a reconciliation script that compares Shopify orders with Zoho Books invoices for a date range (Phase 5).
