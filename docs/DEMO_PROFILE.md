# Acme Textiles — Synthetic Demo Profile

> **Synthetic demo data only.** Every value on this page is
> fictitious. The profile exists so reviewers can exercise the
> UrsBiz product end-to-end without touching real customer data.

This document describes the single synthetic business that the
H7.5 (Docx Prompt 5) demo seed installs into the database. The
shape is deliberately close to a real Tirupur-based garment
manufacturer so the deterministic engines, the schemes catalog,
and the AI Assistant all have meaningful inputs to render.

---

## 1. Identity

| Field | Value |
| --- | --- |
| Legal name | `Acme Textiles` |
| Trade name | `Acme Textiles (Demo)` |
| Industry | `Textile Manufacturing` |
| Sub-industry | `Knitted garments` |
| Business type | `Private Limited` |
| Established | `2014` |
| Country / State / City | `India` / `Tamil Nadu` / `Tirupur` |

## 2. Operating profile

| Field | Value |
| --- | --- |
| Employees | `12` |
| Annual revenue (current) | `₹1.8 Crore` (18,000,000 INR) |
| Target revenue | `₹3 Crore` (30,000,000 INR) |
| Production capacity | `~18,000 garments / month` |
| Capacity utilisation | `68%` |
| Monthly production | `12,000 units` |

## 3. Digital presence

| Field | Value |
| --- | --- |
| Website | `https://acme-textiles.example.com` |
| LinkedIn | `https://www.linkedin.com/company/acme-textiles-demo` |
| e-commerce enabled | **No** (per docx Part 1) |
| Digital marketing | **No** |
| Cloud systems | **No** |

## 4. Products

| Name | Category | HS Code | Price | Monthly volume | Exported |
| --- | --- | --- | --- | --- | --- |
| Cotton Crew-Neck T-Shirt | Apparel | 6109.10 | ₹180 | 6,500 | No |
| Polyester Blend Track Pants | Apparel | 6103.43 | ₹320 | 3,500 | No |
| Organic Cotton Romper (Export Sample) | Apparel | 6111.20 | ₹540 | 2,000 | Yes |

## 5. Certifications

| Name | Issuer | Certificate # | Issued |
| --- | --- | --- | --- |
| Udyam Registration (MSME) | Ministry of MSME, Government of India | UDYAM-TN-33-0012345 | 2018-04-12 |
| GST Registration | Government of India | 33ABCDE1234F1Z5 | 2018-05-01 |

## 6. Export history

| Destination | Category | First export | Annual value | IEC # |
| --- | --- | --- | --- | --- |
| Germany | Apparel | 2024-09-15 | ₹45 Lakh (4,500,000 INR) | 0399DEMO0001 |

## 7. Goals

1. **Grow annual revenue to ₹3 Cr** — 12m, high priority. "Reach
   the next revenue band without increasing supplier dependency
   beyond 2 vendors."
2. **Add an export customer in the EU** — 9m, high priority.
   "Convert the German sample order into a standing customer."
3. **Launch D2C ecommerce for repeat domestic buyers** — 6m,
   medium priority. "Open a Shopify storefront for direct B2C
   sales."

## 8. Challenges

1. **High supplier dependency** (critical, supply chain). "Two
   yarn vendors supply 78% of raw material; any disruption will
   halt production within 3 weeks."
2. **Limited digital presence** (high, digital). "No ecommerce
   and no digital marketing means new buyer discovery is slow and
   reliant on trade shows."
3. **Single export customer** (high, export). "All export
   revenue is from one German buyer; loss of that customer would
   cut revenue by 25%."

## 9. Action board (seeded for the demo owner)

| Title | Category | Priority | Due |
| --- | --- | --- | --- |
| Identify and onboard 2 backup yarn vendors | Operations | High | 2026-09-15 |
| Set up Shopify D2C storefront | Digital | High | 2026-10-30 |
| Apply for ZED certification subsidy | Compliance | Medium | 2026-11-30 |
| Pitch the organic-cotton romper to 3 EU buyers | Sales | Medium | 2026-12-15 |

---

## 10. How the seed/reset pair operates

### `scripts/demo/seed_demo_business.py`

* Idempotent — re-running it updates the existing demo user /
  business rather than creating duplicates.
* Reads `DEMO_USER_EMAIL`, `DEMO_USER_PASSWORD`,
  `DEMO_USER_FULL_NAME`, `DEMO_BUSINESS_NAME`,
  `DEMO_CURRENT_REVENUE`, `DEMO_TARGET_REVENUE`,
  `DEMO_CURRENCY`, `DEMO_ESTABLISHED_YEAR`,
  `DEMO_EMPLOYEE_COUNT`, `DEMO_INDUSTRY`, `DEMO_SUB_INDUSTRY`,
  `DEMO_CITY`, `DEMO_STATE`, `DEMO_COUNTRY` from the environment.
  Defaults match this profile.
* The password hash is refreshed on every run so a fresh
  deployment starts from the documented credential.
* The script **never** logs the password or the password hash.
  The output is limited to `[DEMO-SYNTHETIC]` lines reporting
  the synthetic user id, business id, revenue, employee count,
  and location.
* No other user / business row is ever read or touched.

### `scripts/demo/reset_demo_business.py`

* The only path in the repo that drops the demo user / business.
* Refuses to run without `--yes`; prints a `no-op` line when the
  demo rows are already absent.
* Deletes only rows whose email or legal_name matches the
  synthetic demo identifiers. Cascade removes the demo's action
  items and child rows (products, certifications, digital
  presence, export history, goals, challenges).
* The script **never** logs the password or the password hash.

### Demo credentials

The default credentials — **for demo use only** — are:

```
email    = acme.textiles@example.com
password = AcmeDemoPass1
```

Both can be overridden via environment variables for a fresh
deployment. Production deployments must rotate these and never
ship the defaults.

---

## 11. What the demo exercises

| Surface | Why this profile shows meaningful data |
| --- | --- |
| Dashboard | Health score, KPIs, AI summary all key off a complete business row. |
| Digital Twin | Multiple certifications + IEC number push the archetype engine into "Compliance Leader / Export-Ready". |
| Predictive Analytics | Forecast engine has revenue + capacity utilisation + monthly production to model from. |
| Recommendations | Challenge rows (supplier dependency, digital gap, single buyer) drive actionable suggestions. |
| Government Schemes | Textile + Tirupur + MSME band returns the 7 curated scheme and registration programs — CGTMSE, ZED, PMEGP, MAI, MUDRA Shishu, NSIC, Udyam — each with match %, official authority, last-verified date, and disclaimer. |
| Action Board | Seeded with 4 demo items so the board is non-empty on first login. |
| Reports (CSV/PDF/unified) | Profile + products + certifications + export history produce a multi-page business snapshot. |
| AI Assistant | Has products, goals, challenges, and schemes to ground every response. |