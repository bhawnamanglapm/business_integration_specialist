r"""One-time Zoho setup: exchange a Self Client grant code for a refresh token.

Run from the repo root, in YOUR terminal (it asks for input):
    .\.venv\Scripts\python.exe scripts\zoho_exchange_grant_code.py

What it does:
  1. Asks you to paste the grant code (input is hidden, nothing shows as you paste).
  2. Exchanges it with Zoho for an access token + refresh token.
  3. Saves the refresh token into .env as ZOHO_REFRESH_TOKEN.
  4. Lists your Zoho Books organisations and, if there is exactly one,
     saves its id into .env as ZOHO_ORGANIZATION_ID.

It never prints the grant code, access token or refresh token.
"""

from __future__ import annotations

import sys
from getpass import getpass
from pathlib import Path

import httpx
from dotenv import dotenv_values, set_key

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def main() -> int:
    if not ENV_PATH.exists():
        print(f"No .env found at {ENV_PATH}. Copy .env.example to .env first.")
        return 1
    env = dotenv_values(ENV_PATH)
    missing = [k for k in ("ZOHO_ACCOUNTS_URL", "ZOHO_API_BASE", "ZOHO_CLIENT_ID", "ZOHO_CLIENT_SECRET") if not env.get(k)]
    if missing:
        print(f"Fill these in .env first: {', '.join(missing)}")
        return 1

    print("Paste the grant code from the Zoho API Console and press Enter.")
    print("(Nothing will appear while you paste; that's expected.)")
    code = getpass("Grant code: ").strip()
    if not code:
        print("No code entered. Nothing changed.")
        return 1
    if not code.startswith("1000."):
        print("Warning: Zoho codes usually start with '1000.'. Trying anyway.")

    # 1. Exchange the grant code (single use, expires in minutes)
    resp = httpx.post(
        f"{env['ZOHO_ACCOUNTS_URL']}/oauth/v2/token",
        data={
            "grant_type": "authorization_code",
            "client_id": env["ZOHO_CLIENT_ID"],
            "client_secret": env["ZOHO_CLIENT_SECRET"],
            "code": code,
        },
        timeout=15,
    )
    try:
        body = resp.json()
    except ValueError:
        print(f"Zoho returned HTTP {resp.status_code} with no JSON. Nothing changed.")
        return 1

    if "error" in body:
        print(f"Zoho said: {body['error']}. Nothing changed.")
        if body["error"] == "invalid_code":
            print("The code expired or was already used. Generate a new one and run this again straight away.")
        elif body["error"] == "invalid_client":
            print("Client ID/secret not recognised here. Check them in .env, and that you used api-console.zoho.in.")
        return 1
    if "refresh_token" not in body:
        print("Zoho returned an access token but no refresh token. Nothing changed.")
        print("Generate a fresh code from the Self Client 'Generate Code' tab and try again.")
        return 1

    # 2. Save the refresh token (only this line in .env changes)
    set_key(str(ENV_PATH), "ZOHO_REFRESH_TOKEN", body["refresh_token"], quote_mode="never")
    print("OK: refresh token saved to .env as ZOHO_REFRESH_TOKEN.")

    # 3. Look up the organisation id with the new access token
    resp = httpx.get(
        f"{env['ZOHO_API_BASE']}/organizations",
        headers={"Authorization": f"Zoho-oauthtoken {body['access_token']}"},
        timeout=15,
    )
    orgs = resp.json().get("organizations", []) if resp.status_code == 200 else []
    if not orgs:
        print(f"Could not list organisations (HTTP {resp.status_code}). Set ZOHO_ORGANIZATION_ID by hand.")
        return 0

    print("Organisations on this account:")
    for org in orgs:
        print(f"  - {org.get('name')}  id={org.get('organization_id')}  country={org.get('country')}")
    if len(orgs) == 1:
        set_key(str(ENV_PATH), "ZOHO_ORGANIZATION_ID", str(orgs[0]["organization_id"]), quote_mode="never")
        print("OK: organisation id saved to .env as ZOHO_ORGANIZATION_ID.")
    else:
        print("More than one organisation: copy the right id into ZOHO_ORGANIZATION_ID in .env yourself.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
