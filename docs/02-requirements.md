# 02 — Requirements

> **Simulated engagement.** "Glow & Grace" is fictional. These requirements derive from the approved [discovery](01-discovery.md) (pain points **P1–P7**, assumptions **A1–A13**). New decisions made in this phase are marked **(S)** and listed in [§7](#7-new-decisions-for-approval-s).

| | |
|---|---|
| **Phase** | 2 — Requirements |
| **Date** | November 2026 |
| **Input** | [01-discovery.md](01-discovery.md) (approved 13 Nov 2026) |
| **Status** | Approved (simulated client sign-off, 13 Nov 2026) |

---

## 1. Purpose and conventions

This document says **what** the integration must do, in a form that can be tested. **How** it does it (webhook topics, field mapping, retry counts, database tables) is Phase 3 design.

- **IDs:** `FR-<area>-nn` for functional and `NFR-<area>-nn` for non-functional requirements. Areas: `OTC` order-to-cash, `RFD` refunds/returns/cancellations, `EXC` exceptions, `REC` reconciliation, `LTC` lead-to-customer, `MKE` Make demo.
- **Priority (MoSCoW):** **Must** (v1 fails without it), **Should** (expected; can slip with agreement), **Could** (stretch), **Won't** (agreed out of scope).
- **Acceptance criteria:** *Given / When / Then*. Phase 6 turns each into at least one test.
- **Traces to:** the pain point (P#), assumption (A#), decision (D#, [§7](#7-new-decisions-for-approval-s)) or open item (Q#) it comes from.
- **Scope of the two builds (A12):** the **FastAPI service** must meet every Must and Should. The **Make demo** must meet only `FR-MKE-01`.

---

## 2. Actors

| Actor | Type | Role in the flows |
|---|---|---|
| Customer | Person | Places, pays for and returns orders on Shopify |
| Shopify | System | Source of orders, payments, fulfilments, refunds, cancellations and tags |
| Integration service | System | The FastAPI service (production) or Make scenario (demo) |
| HubSpot | System | Receives contacts and deals |
| Zoho Books | System | Receives customers, GST invoices, payments and credit notes |
| Operations Executive | Person | Marks COD orders paid, tags RTO and B2B orders, handles alerts and re-processing |
| Chartered Accountant (CA) | Person | Uses Zoho Books and the reconciliation report |

---

## 3. Functional requirements

### 3.1 Order-to-cash (Flow 1)

**FR-OTC-01 — Receive Shopify order events** · Must · P1, P4
The service receives Shopify events for: order paid, order fulfilled, order cancelled, refund created, and order tags changed.
- *Given* a valid event from Shopify, *when* it arrives, *then* it is accepted and queued for processing.

**FR-OTC-02 — Classify payment method** · Must · A3, A4
Each order is classified as **prepaid** or **COD** from its Shopify payment details.
- *Given* an order paid through the payment gateway, *then* it is classified prepaid.
- *Given* an order placed with cash on delivery, *then* it is classified COD.

**FR-OTC-03 — Invoice trigger by payment method** · Must · A4, P4
- *Given* a **prepaid** order, *when* Shopify reports it **paid**, *then* the order-to-cash steps (FR-OTC-04 to 09) run.
- *Given* a **COD** order, *when* Shopify reports it **fulfilled** (dispatched), *then* the order-to-cash steps run.
- *Given* a COD order is marked paid **before** it is fulfilled, *then* the invoice is created at that point, as for a prepaid order.

**FR-OTC-04 — Find or create the HubSpot contact** · Must · A6, P3, D1, D9
- *Given* an order whose email matches an existing HubSpot contact (case-insensitive, trimmed), *then* that contact is used and no new contact is created.
- *Given* no match, *then* a contact is created with name, email and phone from the order.

**FR-OTC-05 — Create one HubSpot deal per order** · Must · P1, D2, Q1
- *When* the order-to-cash steps run, *then* one deal is created with the order number, amount (INR) and stage per D2, and is associated with the contact.
- *Given* a deal already exists for that order number, *then* no second deal is created.

**FR-OTC-06 — Find or create the Zoho Books customer** · Must · A6, P3, D9
- *Given* an existing Zoho customer with the same email, *then* it is used.
- *Given* no match, *then* a customer is created with name, email, phone and billing/shipping address from the order.

**FR-OTC-07 — Create the GST invoice** · Must · A1, A2, A10, A11, P2
- *Then* the invoice contains one line per order item with quantity and the GST-inclusive price (A2), plus discounts, plus a shipping line when shipping was charged (A11).
- *Given* the shipping address is in **Haryana**, *then* tax is split **CGST + SGST**; *given* any other state, *then* tax is **IGST** (A1).
- *Then* the place of supply on the invoice is the shipping state.
- *Then* the invoice total equals the Shopify order total. Any rounding difference is handled as designed in Phase 3 (Q5).

**FR-OTC-08 — One invoice per order, traceable** · Must · P7, D7
- *Then* the invoice carries the Shopify order number in its reference field; the invoice number comes from Zoho's auto-series (D7).
- *Given* an invoice already exists for that order number, *then* no second invoice is created.

**FR-OTC-09 — Record the payment** · Must · A3, A4, D3, P7
- *Given* a prepaid order, *when* its invoice is created, *then* the payment is recorded against it straight away.
- *Given* a COD order with an invoice, *when* Operations marks it paid in Shopify (D3), *then* the payment is recorded against the invoice.

**FR-OTC-10 — Update the HubSpot deal** · Should · P1, D2
- *When* the invoice is created or the payment recorded, *then* the deal shows the Zoho invoice number and the order status (D2).

**FR-OTC-11 — Hold B2B orders for manual handling** · Must · A8, D5
- *Given* an order tagged `B2B` (D5), *then* no invoice is created automatically, and the order appears in the exceptions list (FR-EXC-01) as "manual: B2B".

**FR-OTC-12 — Reject orders that cannot be matched** · Must · A6
- *Given* an order without an email address, *then* nothing is created in HubSpot or Zoho Books and a failed record is raised (FR-EXC-01).

### 3.2 Refunds, returns and cancellations (Flow 2)

**FR-RFD-01 — Full refund** · Must · A7, P6
- *Given* an invoiced order, *when* Shopify records a full refund, *then* a credit note for the full refunded amount is created against the invoice and the refund is recorded.

**FR-RFD-02 — Partial refund** · Must · A7, P6
- *Given* an invoiced order, *when* Shopify records a partial refund, *then* a credit note is created for the refunded items (or the refunded amount if no items are given), with GST calculated the same way as the invoice.

**FR-RFD-03 — Refund or cancellation before an invoice exists** · Must · A4
- *Given* a COD order cancelled before dispatch (so not invoiced), *then* no Zoho Books documents are created, and the HubSpot deal (if any) is marked Cancelled.

**FR-RFD-04 — Prepaid cancellation before dispatch** · Must · A4
- *Given* a prepaid order that was invoiced on payment, *when* it is cancelled and refunded before dispatch, *then* a credit note for the full amount is created and the refund recorded.

**FR-RFD-05 — Return to origin (RTO)** · Must · A5, D4
- *Given* an invoiced COD order, *when* Operations adds the tag `RTO` (D4), *then* a credit note for the full invoice amount is created. No refund is recorded, because no payment was received.

**FR-RFD-06 — HubSpot deal reflects refunds** · Should · P6, D2
- *When* a credit note is created, *then* the deal's order status becomes Partially refunded, Refunded, RTO or Cancelled as applicable (D2).

### 3.3 Exceptions and monitoring

**FR-EXC-01 — Failed-records list** · Must · P5
- *Given* any step fails after retries (NFR-REL-01), or an order is held for manual handling, *then* a record is stored with the Shopify order number, the step, the error reason and the time. It survives a restart.

**FR-EXC-02 — Alert on failure** · Must · P5, D6
- *When* a failed record is created, *then* an alert reaches the Slack channel (D6) within **5 minutes**, containing the order number, step and reason, and **no customer personal data** (NFR-SEC-04).

**FR-EXC-03 — Re-process a failed record** · Must · P5
- *Given* a failed record, *when* Operations re-processes it (one record, or all), *then* processing resumes and no record already created is duplicated (NFR-IDM-01).

**FR-EXC-04 — Daily summary** · Could · P5
- *Then* once a day, a Slack message shows counts of orders processed, invoices, credit notes and open failed records.

### 3.4 Reconciliation

**FR-REC-01 — Reconciliation report** · Must · P7
- *Given* a date range, *when* the reconciliation script runs, *then* it lists: Shopify orders that should have an invoice but don't; invoices whose total differs from the order; refunds without a credit note; and credit notes without a refund or RTO.

**FR-REC-02 — Export for the CA** · Should · P7
- *Then* the report can also be written as a CSV file.

### 3.5 Lead-to-customer (Flow 3, stretch)

**FR-LTC-01 — Website lead to HubSpot** · Could
- *When* a website enquiry form is submitted, *then* a HubSpot contact is created or updated as a lead.

**FR-LTC-02 — Won deal to Zoho customer** · Could
- *When* a HubSpot deal for a lead is moved to Closed won, *then* the matching Zoho Books customer is found or created.

### 3.6 Make demo

**FR-MKE-01 — Make demonstrates the prepaid happy path** · Should · A12, D10
- *Given* a prepaid test order, *when* Shopify reports it paid, *then* the Make scenario creates the HubSpot contact and deal, the Zoho customer, the GST invoice and the payment, meeting FR-OTC-04 to 09 for that case. Error handling, COD and refunds are not required in Make.

---

## 4. Non-functional requirements

| ID | Requirement | Priority | Traces to |
|---|---|---|---|
| **NFR-IDM-01** | **Idempotency.** Processing the same Shopify event twice, or re-processing a failed record, never creates a second contact, deal, customer, invoice, payment or credit note. Shopify can deliver the same webhook more than once. | Must | P3, FR-OTC-05/08 |
| **NFR-PERF-01** | **Latency.** Invoices and credit notes are created within **15 minutes** of the trigger event in normal operation. | Must | P4, P6 |
| **NFR-PERF-02** | **Fast acknowledgement.** Incoming Shopify webhooks are acknowledged quickly and processed afterwards, so Shopify's response timeout is never hit (exact timeout confirmed in Phase 3). | Must | FR-OTC-01 |
| **NFR-REL-01** | **Retries.** Temporary failures (timeouts, HTTP 429, HTTP 5xx) are retried with increasing delays; permanent errors (validation, HTTP 4xx other than 429) go straight to the failed-records list. Retry counts are set in Phase 3. | Must | P5 |
| **NFR-REL-02** | **Rate limits.** The service stays within HubSpot's 100 requests / 10 s, and within Zoho Books' limits once confirmed (Q3). | Must | Q3 |
| **NFR-REL-03** | **No lost events.** An accepted event is stored before it is acknowledged, so a crash or restart doesn't lose it. | Must | P5 |
| **NFR-CAP-01** | **Capacity.** Handles 200 orders on a peak day (A9), including a burst of **50 orders in 10 minutes** at a sale start (D8), within NFR-PERF-01. | Must | A9, D8 |
| **NFR-SEC-01** | **Webhook authenticity.** Every Shopify webhook's HMAC signature is verified with the app's client secret; invalid requests are rejected and logged. | Must | Security |
| **NFR-SEC-02** | **Secrets.** Credentials live only in `.env` / environment variables; never in code, logs, alerts or commits. | Must | Security |
| **NFR-SEC-03** | **Least privilege.** Shopify scopes stay read-only; HubSpot and Zoho scopes stay at the minimum listed in the [setup guide](00-setup-guide.md). | Must | Security |
| **NFR-SEC-04** | **Personal data minimisation.** Logs and alerts identify orders by order number only, with no names, emails, phone numbers or addresses. | Must | Security |
| **NFR-OBS-01** | **Traceability.** Every log line for an order carries its Shopify order number, so one order can be followed across all systems. | Must | P5, P7 |
| **NFR-OBS-02** | **Status at a glance.** Operations can see counts of processed and failed records without reading logs. | Should | P5 |
| **NFR-CFG-01** | **Configuration.** Store name, API versions, base URLs and organisation ID come from configuration, not code. | Must | Maintainability |
| **NFR-TST-01** | **Testable offline.** Automated tests run without live accounts, using mock HubSpot and Zoho Books servers; `scripts/check_connectivity.py` remains the live smoke test. | Must | Maintainability |
| **NFR-CMP-01** | **Audit trail.** Every Zoho Books document can be traced to its Shopify order (FR-OTC-08), and the GST treatment points marked *to verify* in discovery are confirmed with the CA before go-live (Q4). | Must | P2, Q4 |

---

## 5. Data requirements (summary)

Full field-level mapping is Phase 3 ([04 — Field mapping](README.md)). The minimum each record must carry:

| Target record | Must carry |
|---|---|
| HubSpot contact | Email (key), first and last name, phone |
| HubSpot deal | Shopify order number, amount (INR), stage and order status (D2), Zoho invoice number (once created) |
| Zoho Books customer | Name, email (key), phone, billing and shipping address with state |
| Zoho Books invoice | Shopify order number (reference), date, line items (GST-inclusive), discounts, shipping line, place of supply, tax split |
| Zoho Books payment | Invoice, amount, date, payment mode (prepaid gateway or COD) |
| Zoho Books credit note | Invoice it reduces, Shopify order number, refunded items or amount, reason (refund, RTO, cancellation) |
| Failed record | Shopify order number, step, error reason, time, retry count, status (open / resolved) |

---

## 6. Traceability matrix

Every approved pain point and assumption is covered by at least one requirement.

| From discovery | Covered by |
|---|---|
| P1 Manual re-typing | FR-OTC-01, 05, 10 |
| P2 Wrong GST split | FR-OTC-07, NFR-CMP-01 |
| P3 Duplicate customers | FR-OTC-04, 06, NFR-IDM-01 |
| P4 Late invoices | FR-OTC-01, 03, NFR-PERF-01 |
| P5 Invisible failures | FR-EXC-01 to 04, NFR-REL-01, 03, NFR-OBS-01, 02 |
| P6 Refunds not reflected | FR-RFD-01, 02, 06, NFR-PERF-01 |
| P7 Slow reconciliation | FR-OTC-08, 09, FR-REC-01, 02, NFR-OBS-01 |
| A1 Seller in Haryana | FR-OTC-07 |
| A2 GST-inclusive prices | FR-OTC-07 |
| A3 Prepaid / COD mix | FR-OTC-02, 09 |
| A4 Invoice on paid (prepaid) / fulfilled (COD) | FR-OTC-02, 03, 09, FR-RFD-03, 04 |
| A5 RTO credit notes | FR-RFD-05 |
| A6 Email as customer key | FR-OTC-04, 06, 12 |
| A7 Full / partial refunds | FR-RFD-01, 02 |
| A8 B2C only | FR-OTC-11 |
| A9 Volumes | NFR-CAP-01 |
| A10 Delivery-state mix | FR-OTC-07 (and Phase 6 test data) |
| A11 Shipping charge | FR-OTC-07 |
| A12 Make = demo, FastAPI = production | §1, FR-MKE-01 |
| A13 Baselines and targets | NFR-PERF-01, FR-EXC-02 (targets); Phase 8 before/after |

---

## 7. New decisions for approval (S)

Writing testable requirements needed these extra decisions. **All approved 13 Nov 2026 (simulated client sign-off).**

| ID | Decision (S) | Used by |
|---|---|---|
| D1 | The HubSpot contact and deal are created at the same trigger as the invoice (A4), not when the order is placed | FR-OTC-04, 05 |
| D2 | Deals use HubSpot's default pipeline at stage **Closed won** when invoiced; a custom deal property "Order status" holds Invoiced / Paid / Partially refunded / Refunded / RTO / Cancelled. Custom-property support on the free CRM **to verify** in Phase 3 | FR-OTC-05, 10, FR-RFD-03, 06 |
| D3 | For COD, Operations clicks **Mark as paid** in Shopify when the courier remits the cash | FR-OTC-09 |
| D4 | Operations signals an RTO by adding the order tag **`RTO`** in Shopify | FR-RFD-05 |
| D5 | Operations signals a B2B order by adding the order tag **`B2B`** in Shopify | FR-OTC-11 |
| D6 | Alerts go to one Slack channel via an incoming webhook (`SLACK_WEBHOOK_URL`, already in `.env.example`) | FR-EXC-02, 04 |
| D7 | Zoho Books numbers invoices and credit notes with its own auto-series; the Shopify order number goes in the reference field | FR-OTC-08 |
| D8 | Burst capacity target: 50 orders in 10 minutes at a sale start | NFR-CAP-01 |
| D9 | Email matching is case-insensitive and ignores leading/trailing spaces | FR-OTC-04, 06 |
| D10 | The Make demo covers only the prepaid happy path | FR-MKE-01 |

---

## 8. Open items carried forward

| # | Item (from discovery §11) | Blocks | Resolve in |
|---|---|---|---|
| Q1 | HubSpot deal-to-contact association scope | FR-OTC-05 | Phase 3 |
| Q2 | Make active-scenario limit and minimum interval | FR-MKE-01 | Phase 4 |
| Q3 | Zoho Books API rate limits and free-plan document limits | NFR-REL-02, NFR-CAP-01 | Phase 3 |
| Q4 | GST points to verify: invoice timing, shipping charge, e-invoicing | FR-OTC-03, 07, NFR-CMP-01 | Phase 3, with CA |
| Q5 | Rounding between back-calculated GST and Shopify totals | FR-OTC-07, FR-REC-01 | Phase 3 |
| Q6 | Shopify protected customer data review for a live store | NFR-SEC-04 | Phase 7 |
| Q7 | README Flow 1 trigger wording | — | **Closed in this phase** (README updated) |
