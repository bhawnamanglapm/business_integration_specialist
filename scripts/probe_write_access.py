r"""Phase 3 probe: answers design questions that the API docs leave open.

Run from the repo root:
    .\.venv\Scripts\python.exe scripts\probe_write_access.py

HubSpot (WRITES to your dev portal, then cleans up):
  1. Read the deal pipelines and stages.
  2. Create a test contact and a test deal, both named "PROBE delete-me".
  3. Associate the deal with the contact (open question Q1: is a separate scope needed?).
  4. Try to create a test custom deal property (decision D2), then delete it.
  5. Archive the test deal and contact, even if an earlier step failed.

Zoho Books (READ-ONLY):
  6. List the organisation's taxes (are CGST+SGST and IGST set up?).
  7. Read the organisation's GST registration flags and state.

Prints PASS / FAIL per step. Never prints tokens, keys or secrets, or the GSTIN.
"""

from __future__ import annotations

import sys
import time

import httpx
from dotenv import dotenv_values

from check_connectivity import ENV_PATH, TIMEOUT, CheckSkipped, require, short_error

PROBE_PROPERTY = "probe_delete_me"


def report(step: str, ok: bool, detail: str) -> bool:
    print(f"[{'PASS' if ok else 'FAIL'}] {step}: {detail}")
    return ok


def hubspot_scopes_hint(resp: httpx.Response) -> str:
    """On 403 HubSpot names the scopes it wanted; those names are not secret."""
    try:
        ctx = resp.json().get("context", {}) or {}
    except ValueError:
        return ""
    wanted = ctx.get("requiredGranularScopes") or ctx.get("requiredScopes") or []
    return f" | HubSpot asks for: {', '.join(wanted)}" if wanted else ""


# ---------------------------------------------------------------- HubSpot
def probe_hubspot(env: dict, client: httpx.Client) -> list[bool]:
    require(env, "HUBSPOT_BASE_URL", "HUBSPOT_SERVICE_KEY")
    base = env["HUBSPOT_BASE_URL"]
    h = {"Authorization": f"Bearer {env['HUBSPOT_SERVICE_KEY']}"}
    results: list[bool] = []
    contact_id = deal_id = None
    won_stage = None  # stage ids differ per portal, so look up the "won" stage by label
    stamp = time.strftime("%Y%m%d%H%M%S")

    try:
        # 1. Pipelines and stages
        r = client.get(f"{base}/crm/v3/pipelines/deals", headers=h)
        if r.status_code == 200:
            lines = []
            for p in r.json().get("results", []):
                stages = ", ".join(f"{s['label']}={s['id']}" for s in p.get("stages", []))
                lines.append(f"pipeline '{p['label']}' id={p['id']}: {stages}")
                if p["id"] == "default":
                    won_stage = next((s["id"] for s in p.get("stages", []) if "won" in s["label"].lower()), None)
            lines.append(f"won stage used for the test deal: {won_stage}")
            results.append(report("HubSpot pipelines", True, "\n      ".join(lines) or "none"))
        else:
            results.append(report("HubSpot pipelines", False, short_error(r) + hubspot_scopes_hint(r)))

        # 2a. Test contact (example.com is reserved for examples; never a real person)
        r = client.post(
            f"{base}/crm/v3/objects/contacts",
            headers=h,
            json={"properties": {"email": f"probe-{stamp}@example.com", "firstname": "PROBE", "lastname": "delete-me"}},
        )
        ok = r.status_code == 201
        contact_id = r.json().get("id") if ok else None
        results.append(report("HubSpot create contact", ok, f"id={contact_id}" if ok else short_error(r) + hubspot_scopes_hint(r)))

        # 2b. Test deal
        r = client.post(
            f"{base}/crm/v3/objects/deals",
            headers=h,
            json={"properties": {"dealname": f"PROBE delete-me {stamp}", "amount": "1", "pipeline": "default", "dealstage": won_stage or "closedwon"}},
        )
        ok = r.status_code == 201
        deal_id = r.json().get("id") if ok else None
        results.append(report("HubSpot create deal", ok, f"id={deal_id}" if ok else short_error(r) + hubspot_scopes_hint(r)))

        # 3. Association (Q1)
        if contact_id and deal_id:
            r = client.put(f"{base}/crm/v4/objects/deals/{deal_id}/associations/default/contacts/{contact_id}", headers=h)
            ok = r.status_code in (200, 201)
            results.append(report("HubSpot associate deal->contact", ok,
                                  f"HTTP {r.status_code} with existing contacts/deals write scopes" if ok
                                  else short_error(r) + hubspot_scopes_hint(r)))
        else:
            results.append(report("HubSpot associate deal->contact", False, "skipped: contact or deal not created"))

        # 4. Custom deal property (D2), created then deleted
        r = client.post(
            f"{base}/crm/v3/properties/deals",
            headers=h,
            json={"name": PROBE_PROPERTY, "label": "PROBE delete-me", "type": "string",
                  "fieldType": "text", "groupName": "dealinformation"},
        )
        ok = r.status_code == 201
        results.append(report("HubSpot create custom deal property", ok,
                              "allowed" if ok else short_error(r) + (hubspot_scopes_hint(r) or
                              (" | add scope crm.schemas.deals.write to the service key" if r.status_code == 403 else ""))))
        if ok:
            d = client.delete(f"{base}/crm/v3/properties/deals/{PROBE_PROPERTY}", headers=h)
            report("HubSpot delete test property", d.status_code == 204, f"HTTP {d.status_code}")
    finally:
        # 5. Clean up whatever was created
        for kind, oid in (("deals", deal_id), ("contacts", contact_id)):
            if oid:
                d = client.delete(f"{base}/crm/v3/objects/{kind}/{oid}", headers=h)
                report(f"HubSpot archive test {kind[:-1]}", d.status_code == 204, f"HTTP {d.status_code}")
    return results


# ---------------------------------------------------------------- Zoho Books
def zoho_token(env: dict, client: httpx.Client) -> str:
    r = client.post(
        f"{env['ZOHO_ACCOUNTS_URL']}/oauth/v2/token",
        data={"grant_type": "refresh_token", "client_id": env["ZOHO_CLIENT_ID"],
              "client_secret": env["ZOHO_CLIENT_SECRET"], "refresh_token": env["ZOHO_REFRESH_TOKEN"]},
    )
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code != 200 or "access_token" not in body:
        raise RuntimeError(f"token refresh failed ({short_error(r)})")
    return body["access_token"]


def probe_zoho(env: dict, client: httpx.Client) -> list[bool]:
    require(env, "ZOHO_ACCOUNTS_URL", "ZOHO_API_BASE", "ZOHO_CLIENT_ID", "ZOHO_CLIENT_SECRET",
            "ZOHO_REFRESH_TOKEN", "ZOHO_ORGANIZATION_ID")
    base, org = env["ZOHO_API_BASE"], env["ZOHO_ORGANIZATION_ID"]
    h = {"Authorization": f"Zoho-oauthtoken {zoho_token(env, client)}"}
    results: list[bool] = []

    # 6. Taxes
    r = client.get(f"{base}/settings/taxes", headers=h, params={"organization_id": org})
    body = r.json() if r.status_code == 200 else {}
    if r.status_code == 200 and body.get("code") == 0:
        taxes = body.get("taxes", [])
        lines = [f"{t.get('tax_name')} {t.get('tax_percentage')}% type={t.get('tax_type')} "
                 f"specific={t.get('tax_specific_type', '-')} id={t.get('tax_id')}" for t in taxes]
        results.append(report("Zoho taxes", True, f"{len(taxes)} found\n      " + "\n      ".join(lines)))
    else:
        results.append(report("Zoho taxes", False, short_error(r)))

    # 7. Organisation GST flags (GSTIN value deliberately not printed)
    r = client.get(f"{base}/organizations/{org}", headers=h, params={"organization_id": org})
    body = r.json() if r.status_code == 200 else {}
    if r.status_code == 200 and body.get("code") == 0:
        o = body.get("organization", {})
        addr = o.get("address") or {}
        keep = {k: v for k, v in o.items()
                if any(w in k.lower() for w in ("gst", "tax", "state", "place")) and isinstance(v, (bool, str, int))
                and "no" not in k.lower().split("_") and "gstin" not in k.lower()}
        keep["address.state"] = addr.get("state") if isinstance(addr, dict) else None
        detail = "; ".join(f"{k}={v}" for k, v in sorted(keep.items()))
        results.append(report("Zoho organisation GST settings", True, detail or "no GST-related fields returned"))
    else:
        results.append(report("Zoho organisation GST settings", False, short_error(r)))
    return results


# ---------------------------------------------------------------- main
def main() -> int:
    if not ENV_PATH.exists():
        print(f"No .env found at {ENV_PATH}.")
        return 1
    env = dotenv_values(ENV_PATH)
    all_results: list[bool] = []
    with httpx.Client(timeout=TIMEOUT) as client:
        for name, fn in (("HubSpot", probe_hubspot), ("Zoho Books", probe_zoho)):
            print(f"--- {name}")
            try:
                all_results += fn(env, client)
            except CheckSkipped as exc:
                print(f"[SKIP] {name}: {exc}")
            except httpx.HTTPError as exc:
                all_results.append(report(name, False, f"network error: {type(exc).__name__}"))
            except Exception as exc:  # noqa: BLE001 - report and keep going
                all_results.append(report(name, False, str(exc)))
    print(f"\n{all_results.count(True)}/{len(all_results)} probe steps passed.")
    return 0 if all(all_results) else 1


if __name__ == "__main__":
    sys.exit(main())
