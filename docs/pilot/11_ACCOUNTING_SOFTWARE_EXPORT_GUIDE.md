# UrsBiz MSME Pilot — Accounting Software Export Guide

**Document ID:** `URSBIZ-PILOT-GD-011`  
**Target Audience:** MSME Owners, Accountants, Pilot Coordinators  
**Scope:** Tally Prime, Vyapar, Zoho Books to UrsBiz CSV/XLSX Conversion  
**Effective Date:** May 2026  

---

## 1. Purpose

During initial pilot onboarding, participant feedback identified that manual reformatting of sales registers into the UrsBiz sales template took 30–45 minutes per business.

This guide provides step-by-step instructions to export sales registers directly from popular Indian MSME accounting platforms—**Tally Prime**, **Vyapar**, and **Zoho Books**—and align them with UrsBiz requirements in under 5 minutes.

---

## 2. UrsBiz Target Column Schema

Before exporting, note the target columns UrsBiz requires (or optionally consumes):

| Field Name | Header in UrsBiz | Mandatory? | Expected Format / Notes |
| :--- | :--- | :--- | :--- |
| **Transaction Date** | `date` | **Yes** | `YYYY-MM-DD`, `DD/MM/YYYY`, or `DD-MM-YYYY` |
| **Product Name** | `product_name` | **Yes** | Clean item title (e.g., `Organic Mustard Oil 1L`) |
| **Quantity Sold** | `quantity` | **Yes** | Positive number (`> 0`). Do not enter returns as negative numbers |
| **Unit Price** | `unit_price` | **Yes** | Net selling price per unit in INR |
| **Total Revenue** | `revenue` | No | Auto-calculated as `quantity * unit_price` if omitted |
| **Product Category** | `category` | No | Grouping (e.g., `Oils`, `Ghee`, `Sweeteners`) |
| **Customer Identifier** | `customer_id` | No | Phone number, GSTIN, or customer code |
| **Customer Name** | `customer_name` | No | Business or buyer name (e.g., `Green Valley Organics`) |
| **Invoice / Order ID** | `order_id` | No | Bill or invoice number (e.g., `INV-2026-089`) |

> [!IMPORTANT]
> **Returns and Exchanges:** Do not record sales returns as negative quantities in the sales file. Negative quantities are rejected by the UrsBiz data quality engine to prevent skewing velocity and forecasting models. Track returns separately via Credit Notes.

---

## 3. Tally Prime Export Instructions

### Step 3.1: Navigate to the Sales Register
1. Open Tally Prime with your active company.
2. From the **Gateway of Tally**, press `D` (Display More Reports) &rarr; `A` (Account Books) &rarr; `S` (Sales Register).
3. Select the desired month or press `Alt + F2` to set the full date period (e.g., `01-01-2026` to `30-04-2026`).
4. Press `Enter` to open the list of vouchers.

### Step 3.2: Configure Columnar Details
1. Press `F8` (Columnar) or `F12` (Configure).
2. Set the following configuration options:
   - **Show Voucher Type:** `Yes`
   - **Show Voucher Number:** `Yes`
   - **Show Buyer/Party Name:** `Yes`
   - **Show Item Name / Stock Item Details:** `Yes`
   - **Show Quantity Details:** `Yes`
   - **Show Rate / Unit Price:** `Yes`
   - **Show Gross Value:** `Yes`
3. Press `Ctrl + A` to accept and render the detailed item-level sales register.

### Step 3.3: Export to Excel / CSV
1. Press `Ctrl + E` (Export).
2. Press `C` (Configure):
   - **File Format:** Select `Excel (Spreadsheet)` or `CSV (Comma Delimited)`.
   - **Folder Path:** Choose your local desktop or downloads folder.
   - **File Name:** e.g., `Tally_Sales_Register_2026.xlsx`.
3. Press `Esc`, then press `E` (Send / Export).

### Step 3.4: Quick Alignment in Excel
1. Open the exported spreadsheet.
2. Delete summary and blank header rows above the table headers.
3. Rename the relevant columns to:
   - Date column &rarr; `date`
   - Stock Item Name &rarr; `product_name`
   - Billed Quantity &rarr; `quantity`
   - Rate &rarr; `unit_price`
   - Party Name &rarr; `customer_name`
   - Voucher No &rarr; `order_id`
4. Save as CSV (`sales_data_ursbiz.csv`).

---

## 4. Vyapar Export Instructions

### Step 4.1: Open Reports in Vyapar
1. Open the Vyapar desktop or mobile application.
2. In the left navigation sidebar, click on **Reports**.
3. Under **Transaction Reports**, click on **Sale Report** or **Item Sales Report**.

### Step 4.2: Select Date Range and Item Details
1. Select the **Item Sales Report** (recommended, as it lists product-level lines).
2. Click on the Date filter dropdown:
   - Choose `Custom Date Range` (e.g., Last 3 Months or Current Financial Year).
3. Confirm that **All Items** and **All Parties** are selected.

### Step 4.3: Export to Excel
1. In the top-right corner of the report table, click the **Excel** icon (or **PDF/Excel Export**).
2. Save the file to your computer (e.g., `Vyapar_Item_Sales.xlsx`).

### Step 4.4: Quick Alignment in Excel
1. Open `Vyapar_Item_Sales.xlsx`.
2. Inspect the columns:
   - `Invoice Date` &rarr; rename to `date`
   - `Item Name` &rarr; rename to `product_name`
   - `Quantity` &rarr; rename to `quantity`
   - `Rate (Price/Unit)` &rarr; rename to `unit_price`
   - `Party Name` &rarr; rename to `customer_name`
   - `Invoice No` &rarr; rename to `order_id`
3. Check for any cancelled bills or return rows (remove or filter out rows with `0` or negative quantities).
4. Save as `.xlsx` or `.csv` and upload to UrsBiz.

---

## 5. Zoho Books Export Instructions

### Step 5.1: Open Sales by Item Report
1. Log in to your Zoho Books organization.
2. Navigate to **Reports** in the left sidebar.
3. Scroll to **Sales** and select **Sales by Item** (or **Invoice Details**).

### Step 5.2: Set Filters
1. In the report header, select the date range (e.g., `This Fiscal Year` or `Custom`).
2. Click **Customize Report**:
   - Ensure `Quantity Sold`, `Average Price`, and `Amount` are checked.
   - If using **Invoice Details**, include `Customer Name`, `Invoice#`, `Item Name`, `Quantity`, and `Rate`.
3. Click **Run Report**.

### Step 5.3: Export
1. Click **Export As** in the top right.
2. Select **CSV** or **XLSX**.
3. Rename headers according to the schema in Section 2.

---

## 6. Pre-Upload Checklist

Before uploading the prepared file to UrsBiz via the Sales Upload screen:

- [ ] **No Negative Quantities:** Filter column `quantity` for values $\le 0$. Remove or zero-out.
- [ ] **No Blank Product Names:** Every row must have a non-empty `product_name`.
- [ ] **Date Consistency:** Dates should be formatted identically (e.g., `YYYY-MM-DD` or `DD/MM/YYYY`).
- [ ] **Header Row:** Ensure row 1 contains the column headers, and there are no merged cells or title banners above row 1.
- [ ] **No Multi-Year File Mixing:** If uploading incrementally, verify that invoice dates do not overlap with already-uploaded periods to avoid duplicate warnings.

---

## 7. Pilot Support & Assistance

If you encounter formatting errors or unexpected column rejections during file upload:
- Contact your assigned Pilot Coordinator.
- Submit the error message via the [Issue Reporting Form](file:///d:/UrsBIZ2/docs/pilot/08_ISSUE_REPORTING_FORM.md).
- Refer to the full [Pilot User Guide](file:///d:/UrsBIZ2/docs/pilot/07_PILOT_USER_GUIDE.md).
