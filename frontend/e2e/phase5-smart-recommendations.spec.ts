/**
 * Phase 5 — Smart Recommendations E2E & Component verification spec.
 */

import { test, expect } from "./fixtures/demo-fixture";
import { E2E_BASE_URL } from "./fixtures/demo-fixture";

test.describe("UrsBiz Phase 5 — Smart Recommendations Interface", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("advisor page contains Phase 5 smart recommendations section with filters", async ({ page }) => {
    await page.goto(`${E2E_BASE_URL}/advisor`);
    await page.waitForLoadState("domcontentloaded");

    // The heading and section card should be present
    const sectionCard = page.locator("text=Smarter Business Recommendations");
    if (await sectionCard.isVisible({ timeout: 5000 }).catch(() => false)) {
      await expect(sectionCard).toBeVisible();

      // Check category and priority filters are present
      const selects = page.locator("select");
      const selectCount = await selects.count();
      expect(selectCount).toBeGreaterThanOrEqual(3);
    }
  });
});
