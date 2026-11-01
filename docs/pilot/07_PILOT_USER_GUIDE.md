# UrsBiz Controlled MSME Pilot — User Guide

**Welcome to UrsBiz!**  
This guide walks you through every screen and feature of the UrsBiz platform during your 4-week pilot.

---

## 1. Getting Started: Login & Business Switching

1. Open your browser and navigate to: `https://ursbiz-frontend.onrender.com/`
2. Enter your registered email and password on the **Login** screen.
3. Once logged in, your active business appears in the top navigation bar. If you manage multiple business branches or entities, use the **Business Selector** dropdown to toggle between them.
4. The sidebar gives you instant access to:
   - **Dashboard**: Executive summary and overall business health score.
   - **Sales**: Sales transaction uploads and revenue analytics.
   - **Forecasting**: Demand projections, sales trends, and prediction ranges.
   - **AI Advisor**: Prioritized business recommendations, action plans, and outcome tracking.
   - **Profile**: Business metadata, MSME tier, and compliance status.

---

## 2. Business Dashboard & Health Score

The **Dashboard** is your daily executive summary:
- **Business Health Score (0–100)**: A composite measure reflecting your formalization readiness, digital channel presence, data completeness, and sales health.
- **Key Metric Cards**: Quick snapshot of total revenue, active product count, customer count, and pending recommendation actions.
- **Recent Signals**: Urgent business developments (e.g. rapid volume shifts or customer concentration changes).

---

## 3. Sales Intelligence: Uploads & Insights

The **Sales Intelligence** module helps you understand what is driving your cash flow:

### Uploading New Sales Records:
1. Navigate to **Sales** $\rightarrow$ click **Upload Sales Data**.
2. Drag and drop your `.csv` or `.xlsx` spreadsheet.
3. Review the **Column Mapping Preview**. Ensure your columns correspond to:
   - Transaction Date
   - Product / Item Name
   - Quantity Sold
   - Unit Price (₹)
   - (Optional) Customer Name, Product SKU, Invoice ID
4. Click **Confirm & Ingest**.

### What to Look For in Sales Analytics:
- **Revenue Trends**: Daily, weekly, or monthly gross revenue graphs.
- **Top 5 Performing Products**: Identify your highest-grossing products and products with zero sales in the last 30 days.
- **Customer Concentration**: Shows what percentage of your revenue depends on your top 3 customers. If concentration exceeds 40%, UrsBiz alerts you to customer dependence risk.
- **Repeat Purchase Rate**: Percentage of buyers who have purchased more than once.

---

## 4. Predictive Analytics & Demand Forecasting

The **Predictive Analytics** view generates forward-looking estimates of customer demand:

### How to Use the Forecast:
1. Select a specific product from the product dropdown.
2. Choose your forecast horizon (7 days, 30 days, or 90 days).
3. The graph displays:
   - **Historical Actual Demand**: Solid line showing observed past sales.
   - **Forecasted Demand (P50)**: Dashed line representing expected demand.
   - **Prediction Intervals (P10 to P90)**: Shaded band representing the range of likely outcomes based on historical volatility.
4. **Model Performance Card**: Displays the backtesting evaluation score (MAE, RMSE, WAPE) showing how accurately the model predicted historical holdout periods.

### Understanding Forecast Labels & Boundaries:
- **Forecasts are Estimates**: Statistical models project patterns from history. They cannot anticipate unexpected road closures, supplier strikes, or sudden price wars.
- **"Insufficient History" Status**: If a product has fewer than 14 observed periods, UrsBiz displays an honest banner explaining that data volume is insufficient for statistical modeling.
- **"Intermittent Demand" Status**: For products sold only sporadically, UrsBiz applies intermittent demand modeling to avoid misleading continuous curves.

---

## 5. AI Advisor: Recommendations & Action Plans

The **AI Advisor** is your core decision-support engine:

### Recommendation Categories:
- **GROWTH**: Opportunities to cross-sell, bundle popular items, or expand into adjacent customer segments.
- **OPERATIONAL EFFICIENCY**: Reducing fulfillment delays, optimizing low-velocity SKUs, or streamlining sales logging.
- **RISK MITIGATION**: Diversifying customer concentration, mitigating sudden revenue drops, or addressing overdue receivables.
- **REGULATORY COMPLIANCE**: MSME Udyam registration benefits, GSTIN threshold readiness, and government subsidy eligibility (CGTMSE).
- **FINANCIAL HEALTH**: Working capital buffer defense and margin protection.
- **DIGITAL ADOPTION**: Setting up digital payment methods, e-commerce cataloging, or WhatsApp Business channels.

### Prioritization Score ($0-100$):
Every recommendation is ranked by a transparent formula:
$$\text{Priority Score} = 30\% \text{ Impact} + 20\% \text{ Effort} + 25\% \text{ Urgency} + 15\% \text{ Confidence} + 10\% \text{ Alignment}$$

### Step-by-Step Action Plans:
Click **View Details** on any recommendation card to open the AI explanation modal:
- **Evidence Card**: Direct verifiable facts from your business data that triggered this recommendation.
- **Action Milestones**: Phased implementation roadmap broken down into:
  - *Immediate Actions (Day 1 to 7)*
  - *Short-Term Actions (Week 2 to 4)*
  - *Medium-Term Actions (Month 2+)*
- **Expected Outcome**: Measurable target metric (e.g. "Target: reduce top-customer concentration below 30%").
- **Human Review Reminder**: Please review action steps carefully to ensure they fit your specific operational capacity before implementing.

---

## 6. Managing the Recommendation Lifecycle

You have complete control over each recommendation:
1. **Accept**: Adds the item to your active execution list.
2. **Dismiss**: If an idea is irrelevant or not feasible, dismiss it with an optional reason (e.g. "Not applicable to our current market"). This helps UrsBiz learn what fits your business.
3. **Move to In Progress**: Mark recommendations as active while you implement the steps.
4. **Mark as Completed**: When finished, click **Record Outcome**.

---

## 7. Portfolio Optimization & Closed-Loop Learning

- **Portfolio View**: Click **Optimize Portfolio** on the Advisor dashboard to check for resource conflicts (e.g. trying to launch two capital-intensive marketing campaigns in the same week).
- **Outcome Tracking Modal**: When completing a recommendation, record:
  - Completion Date
  - Actual Implementation Effort (Low / Medium / High)
  - Owner Feedback & Observations
  - Before-and-After Business Change (e.g. Did sales of that product increase? Did customer retention improve?)
  - *Note*: UrsBiz compares data before and after implementation as heuristic feedback; it never claims to have proved causation or replaced human judgment.

---

## 8. Getting Help During the Pilot

If you encounter any questions or software issues:
- **Use the Issue Reporting Form**: [`08_ISSUE_REPORTING_FORM.md`](file:///d:/UrsBIZ2/docs/pilot/08_ISSUE_REPORTING_FORM.md)
- **Direct Coordinator Support**: Reach out directly via WhatsApp or email to your assigned coordinator.
- **Office Hours**: Weekly open Q&A sessions available every Thursday at 4:00 PM IST.
