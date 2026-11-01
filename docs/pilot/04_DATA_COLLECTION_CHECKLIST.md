# UrsBiz Controlled MSME Pilot — Data Collection Checklist

**Purpose**: Guide pilot participants in extracting, reviewing, and sanitizing historical sales records from their billing or bookkeeping systems before uploading them to UrsBiz.

---

## 1. What Data is Needed?

To generate accurate sales analytics, demand estimates, and personalized business recommendations, UrsBiz requires historical transaction data.

### Minimum Recommended Data Volume:
- **Historical Period**: Minimum **3 months** of continuous sales data (6 to 12 months preferred for seasonal demand estimation).
- **Transaction Count**: At least **50 to 100 individual sales transactions**.
- **Product Variety**: At least **3 to 10 distinct products or services**.

---

## 2. Source Systems Supported

You can extract sales records from any of the following common MSME systems:
- [ ] **Accounting Software**: TallyPrime, Tally ERP 9, Busy, Zoho Books, Marg ERP (Export as Excel / CSV).
- [ ] **Point-of-Sale (POS) Systems**: Petpooja, Vyapar, myBillBook, POSist, Square, Pine Labs.
- [ ] **E-commerce & Marketplace Portals**: Amazon Seller Central, Flipkart Seller Hub, Shopify, WooCommerce (Orders CSV export).
- [ ] **Spreadsheet Ledgers**: Microsoft Excel (`.xlsx`) or Google Sheets (`.csv`).

---

## 3. Required & Optional Data Fields

| Field Name in UrsBiz | Required? | Description & Allowed Format | Examples |
| :--- | :---: | :--- | :--- |
| **Transaction Date** | **Mandatory** | The date the sale or order occurred.<br>Accepted formats: `YYYY-MM-DD`, `DD/MM/YYYY`, `MM/DD/YYYY`. | `2026-03-15`<br>`15/03/2026` |
| **Product / Item Name** | **Mandatory** | Plain-text name or description of the product or service sold. | `Cotton Kurti - M`<br>`Almond Cookies 250g`<br>`Oil Filter Type-A` |
| **Quantity** | **Mandatory** | Number of units sold. Must be a positive integer or decimal ($> 0$). | `1`, `5`, `2.5`, `100` |
| **Unit Price** | **Mandatory** | Price per individual unit in Indian Rupees (₹). Must be $\ge 0$. | `450.00`, `1200`, `25.50` |
| **Customer Name / Code** | *Optional* | Name, business entity name, or code of the buyer. Useful for customer concentration & retention metrics. | `Sharma General Store`<br>`Client-402`<br>`Walk-in Customer` |
| **Product SKU / Code** | *Optional* | Unique identifier or barcode for the item. Helps eliminate duplicate names. | `SKU-CTN-01`<br>`PRD-1092` |
| **Total Amount** | *Optional* | Gross transaction value. If omitted, UrsBiz automatically calculates: $\text{Quantity} \times \text{Unit Price}$. | `900.00`, `2400.00` |
| **Invoice / Order ID** | *Optional* | Bill or invoice number. Helps group multi-item transactions. | `INV-2026-0042`<br>`BILL-8821` |

---

## 4. What NOT to Collect (Strict Exclusions)

To protect your business and customer privacy, **do NOT include any of the following**:
- [x] **No Payment Details**: No credit card numbers, debit card numbers, CVVs, or UPI PINs.
- [x] **No Bank Account Numbers**: No IFSC codes, branch codes, or company bank account details.
- [x] **No Customer Government IDs**: No Aadhaar numbers, PAN numbers, or Passport details of individual consumers.
- [x] **No Passwords or Credentials**: No access keys, passwords, or system credentials.
- [x] **No Employee Compensation Data**: No payroll or individual salary data.

*(If your raw billing export contains columns for customer phone numbers or tax numbers, delete or mask those columns prior to upload).*

---

## 5. Pre-Upload Data Cleaning Checklist

Before uploading your file, perform this quick 5-minute sanity check:

- [ ] **Remove Header Footers & Summary Rows**: Ensure your spreadsheet has only column headers on row 1, followed directly by data rows. Delete any grand totals, page headers, or blank rows at the top or bottom.
- [ ] **Check for Blank Dates or Products**: Ensure every row has a valid date and product name. Rows with missing dates cannot be used for time-series forecasting.
- [ ] **Ensure Positive Quantities**: Check that return items or cancellations (negative quantities) are either removed or clearly identified.
- [ ] **Check for Consistent Product Names**: Avoid minor spelling variations for the exact same item (e.g. use "Almond Cookies 250g" consistently rather than mixing with "Alm Cookies 250gm").
- [ ] **Save as CSV or XLSX**: Save your prepared file as a standard `.csv` (Comma Separated Values) or `.xlsx` (Excel Workbook).

---

## 6. Assistance Available

If you need assistance exporting or cleaning your data:
- Your assigned pilot coordinator is available to assist you over a 15-minute video call or in-person session.
- You can use the provided pre-formatted template: [`sales_upload_template.csv`](file:///d:/UrsBIZ2/docs/pilot/sales_upload_template.csv).
