# UrsBiz Controlled MSME Pilot — Sales Data Template Guide

**Document ID**: `UB-PILOT-TEMPLATE-GUIDE-V1`  
**Associated File**: [`sales_upload_template.csv`](file:///d:/UrsBIZ2/docs/pilot/sales_upload_template.csv)

---

## 1. Overview

UrsBiz features an intelligent **Sales Ingestion Engine** that accepts standard spreadsheets (`.csv` or `.xlsx`) exported from your accounting or billing software. 

You do **not** need to change your existing internal systems. You can either:
- **Option A (Fastest)**: Copy and paste your data directly into the provided [`sales_upload_template.csv`](file:///d:/UrsBIZ2/docs/pilot/sales_upload_template.csv).
- **Option B**: Upload your existing billing export directly, and use UrsBiz's built-in **Column Mapping Tool** to match your headers.

---

## 2. Standard Column Specifications

The table below explains each column present in [`sales_upload_template.csv`](file:///d:/UrsBIZ2/docs/pilot/sales_upload_template.csv):

| Column Header | Requirement | Format / Type | Purpose in UrsBiz Analytics |
| :--- | :---: | :--- | :--- |
| `transaction_date` | **Mandatory** | `YYYY-MM-DD` (preferred) or `DD/MM/YYYY` | Powers daily/weekly/monthly revenue trends, seasonality detection, and forward demand projections. |
| `product_name` | **Mandatory** | Text string (max 255 chars) | Identifies individual items. Enables top-seller analysis, zero-sales SKU detection, and product-level forecasting. |
| `quantity` | **Mandatory** | Positive number ($> 0$) | Measures unit sales volume. Used in demand volume forecasting and product velocity calculations. |
| `unit_price` | **Mandatory** | Currency amount $\ge 0$ | Unit price in INR. Enables price elasticity checks, revenue computation, and average order value (AOV). |
| `total_amount` | *Optional* | Currency amount $\ge 0$ | Gross total for the line item. If left blank, UrsBiz automatically calculates `quantity * unit_price`. |
| `customer_name` | *Optional* | Text string | Enables customer concentration risk analysis (Herfindahl-Hirschman Index), repeat purchase frequency, and churn signals. |
| `product_id` | *Optional* | Alphanumeric SKU/Code | Prevents naming confusion if two products have similar descriptions. |
| `invoice_id` | *Optional* | Alphanumeric Bill No. | Groups multiple line items belonging to the same customer order or invoice. |

---

## 3. How the Upload Process Works in the App

1. **Step 1: Upload File**
   - In UrsBiz, click **Sales** in the left navigation sidebar.
   - Click the **Upload Sales Data** button.
   - Drag and drop your `.csv` or `.xlsx` file (maximum file size: 15 MB).

2. **Step 2: Preview & Column Mapping**
   - UrsBiz reads the first 10 rows and automatically suggests column matches based on fuzzy header matching.
   - For example, if your file has `Order Date` or `Bill Date`, UrsBiz automatically maps it to `transaction_date`.
   - If a suggested mapping is incorrect, click the dropdown and choose the correct column.

3. **Step 3: Automated Data Quality Audit**
   - UrsBiz evaluates every row before storing it in the database and produces a transparent **Data Quality Score** ($0-100\%$):
     - **Valid Rows**: Processed and stored immediately.
     - **Calculated Revenues**: If `total_amount` is blank, UrsBiz calculates it and flags as informative.
     - **Duplicate Rows**: Identical invoice-product-timestamp duplicates are detected.
     - **Invalid Rows**: Rows with blank dates or missing quantities are excluded and logged in the audit trail.

4. **Step 4: Confirmation & Instant Dashboard Refresh**
   - Click **Confirm & Ingest**.
   - Your **Sales Intelligence**, **Demand Forecasting**, and **AI Advisor** dashboards update immediately with fresh metrics.

---

## 4. Common Formatting Issues & How to Fix Them

| Issue Observed | What UrsBiz Detects | Simple Fix Before Upload |
| :--- | :--- | :--- |
| **Merged Cells or Multi-Line Headers** | Ingestion error: cannot find row 1 headers | Unmerge all cells in Excel. Ensure row 1 contains only simple column names. |
| **Summary / Total Rows at Bottom** | Invalid date error on the word "Total" | Delete summary rows like "Grand Total" or "Subtotal" at the bottom of the sheet. |
| **Negative Quantities (Returns)** | Quantity validation error | Separate return entries or convert to positive values with a distinct item name (e.g. "Return Credit"). |
| **Currency Symbols (`₹`, `$`, `,`)** | Text in numeric column | Format unit price and total columns as pure numbers in Excel without currency symbols. |
| **Inconsistent Product Names** | Split SKU analytics | Ensure consistent spelling (e.g. use "Mustard Oil 1L" consistently rather than "Mustard Oil - 1 Ltr"). |

---

## 5. Sample Data Included in Template

The file [`sales_upload_template.csv`](file:///d:/UrsBIZ2/docs/pilot/sales_upload_template.csv) includes 20 representative transactions from a retail/packaged goods MSME spanning two months. You can open it in Microsoft Excel, Google Sheets, or LibreOffice to examine the clean structure.
