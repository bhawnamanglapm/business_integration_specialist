r"""Phase 0 connectivity check: one read-only API call per system.

Run from the repo root:
    .\.venv\Scripts\python.exe scripts\check_connectivity.py

Reads credentials from .env and prints PASS / FAIL / SKIP per system.
It never prints tokens, keys or secrets, and it never writes to any system.
Exit code is 0 only if every check passes.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx
from dotenv import dotenv_values

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
TIMEOUT = httpx.Timeout(15.0)


class CheckSkipped(Exception):
    """Raised when a check can't run because settings are missing."""


def require(env: dict, *keys: str) -> None:
    missing = [k for k in keys if not env.get(k)]
    if missing:
        raise CheckSkipped(f"missing in .env: {', '.join(missing)}")


def short_error(resp: httpx.Response) -> str:
    """Status code plus a short, non-secret error hint from the body."""
    try:
        body = resp.json()
    except ValueError:
        # Shopify's OAuth errors come back as an HTML page; the <title> names the error
        title = re.search(r"<title>(.*?)</title>", resp.text, re.IGNORECASE | re.DOTALL)
        return f"HTTP {resp.status_code}: {title.group(1).strip()[:150]}" if title else f"HTTP {resp.status_code}"
    if isinstance(body, dict):
        for key in ("error", "message", "errors", "category"):
            if key in body:
                return f"HTTP {resp.status_code}: {str(body[key])[:150]}"
    return f"HTTP {resp.status_code}"


# ---------------------------------------------------------------- Shopify
def check_shopify(env: dict, client: httpx.Client) -> str:
    require(env, "SHOPIFY_STORE", "SHOPIFY_API_VERSION", "SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET")
    base = f"https://{env['SHOPIFY_STORE']}.myshopify.com"

    # 1. Client credentials grant -> 24-hour access token (kept in memory only)
    resp = client.post(
        f"{base}/admin/oauth/access_token",
        data={
            "grant_type": "client_credentials",
            "client_id": env["SHOPIFY_CLIENT_ID"],
            "client_secret": env["SHOPIFY_CLIENT_SECRET"],
        },
    )
    if resp.status_code != 200 or "access_token" not in resp.json():
        raise RuntimeError(f"token request failed ({short_error(resp)})")
    token = resp.json()["access_token"]

    # 2. GraphQL Admin API: read shop name and currency
    resp = client.post(
        f"{base}/admin/api/{env['SHOPIFY_API_VERSION']}/graphql.json",
        headers={"X-Shopify-Access-Token": token},
        json={"query": "{ shop { name myshopifyDomain currencyCode } productsCount { count } }"},
    )
    body = resp.json() if resp.status_code == 200 else {}
    if resp.status_code != 200 or body.get("errors") or not body.get("data", {}).get("shop"):
        raise RuntimeError(f"shop query failed ({short_error(resp)})")

    shop = body["data"]["shop"]
    products = (body["data"].get("productsCount") or {}).get("count", "?")
    note = "" if shop["currencyCode"] == "INR" else "  <-- expected INR (setup guide Step 2a)"
    return f"store '{shop['name']}' ({shop['myshopifyDomain']}), currency {shop['currencyCode']}, products {products}{note}"


# ---------------------------------------------------------------- HubSpot
def check_hubspot(env: dict, client: httpx.Client) -> str:
    require(env, "HUBSPOT_BASE_URL", "HUBSPOT_SERVICE_KEY")
    resp = client.get(
        f"{env['HUBSPOT_BASE_URL']}/crm/v3/objects/contacts",
        params={"limit": 1, "archived": "false"},
        headers={"Authorization": f"Bearer {env['HUBSPOT_SERVICE_KEY']}"},
    )
    if resp.status_code == 401:
        raise RuntimeError("HTTP 401: key rejected (wrong or revoked key)")
    if resp.status_code == 403:
        raise RuntimeError("HTTP 403: key lacks scope crm.objects.contacts.read")
    if resp.status_code != 200:
        raise RuntimeError(f"contacts request failed ({short_error(resp)})")
    count = len(resp.json().get("results", []))
    return f"contacts endpoint OK (returned {count} of limit 1)"


# ---------------------------------------------------------------- Zoho Books
def check_zoho(env: dict, client: httpx.Client) -> str:
    require(env, "ZOHO_ACCOUNTS_URL", "ZOHO_API_BASE", "ZOHO_CLIENT_ID", "ZOHO_CLIENT_SECRET", "ZOHO_REFRESH_TOKEN")

    # 1. Refresh token -> 1-hour access token (kept in memory only)
    resp = client.post(
        f"{env['ZOHO_ACCOUNTS_URL']}/oauth/v2/token",
        data={
            "grant_type": "refresh_token",
            "client_id": env["ZOHO_CLIENT_ID"],
            "client_secret": env["ZOHO_CLIENT_SECRET"],
            "refresh_token": env["ZOHO_REFRESH_TOKEN"],
        },
    )
    body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    if resp.status_code != 200 or "access_token" not in body:
        raise RuntimeError(f"token refresh failed ({short_error(resp)})")
    token = body["access_token"]

    # 2. List organisations
    resp = client.get(
        f"{env['ZOHO_API_BASE']}/organizations",
        headers={"Authorization": f"Zoho-oauthtoken {token}"},
    )
    body = resp.json() if resp.status_code == 200 else {}
    if resp.status_code != 200 or body.get("code") != 0:
        raise RuntimeError(f"organizations request failed ({short_error(resp)})")

    orgs = body.get("organizations", [])
    lines = [f"{len(orgs)} organisation(s) found"]
    for org in orgs:
        lines.append(f"      - {org.get('name')}  id={org.get('organization_id')}  country={org.get('country')}")
    configured = env.get("ZOHO_ORGANIZATION_ID")
    if not configured:
        lines.append("      ZOHO_ORGANIZATION_ID is empty in .env: copy the id above into it")
    elif configured not in {str(o.get("organization_id")) for o in orgs}:
        lines.append("      ZOHO_ORGANIZATION_ID in .env does not match any organisation above")
    return "\n".join(lines)


# ---------------------------------------------------------------- main
def main() -> int:
    if not ENV_PATH.exists():
        print(f"No .env found at {ENV_PATH}. Copy .env.example to .env first.")
        return 1
    env = dotenv_values(ENV_PATH)

    checks = [("Shopify", check_shopify), ("HubSpot", check_hubspot), ("Zoho Books", check_zoho)]
    results = []
    with httpx.Client(timeout=TIMEOUT) as client:
        for name, fn in checks:
            try:
                detail = fn(env, client)
                status = "PASS"
            except CheckSkipped as exc:
                status, detail = "SKIP", str(exc)
            except httpx.HTTPError as exc:
                status, detail = "FAIL", f"network error: {type(exc).__name__}"
            except Exception as exc:  # noqa: BLE001 - report any failure, keep going
                status, detail = "FAIL", str(exc)
            results.append(status)
            print(f"[{status}] {name}: {detail}")

    passed = results.count("PASS")
    print(f"\n{passed}/{len(results)} systems passed.")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
