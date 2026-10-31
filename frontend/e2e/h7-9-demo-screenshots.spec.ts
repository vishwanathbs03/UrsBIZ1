/**
 * H7.9 — Demo Screenshot Capture Spec
 *
 * Captures 3 key screenshots for the Sprint H7.9 evidence report:
 * 1. Verified Business Analysis / Real Grounded AI mode (h7-9-real-grounded-gemini.png)
 * 2. Exploratory Business Advisor mode (h7-9-exploratory-business-advisor.png)
 * 3. Deterministic Fallback mode (h7-9-deterministic-fallback.png)
 */
import {
  test,
  expect,
  E2E_BASE_URL,
  requireDemoCreds,
} from "./fixtures/demo-fixture";

test.describe("H7.9 — Judge Ready Screenshots", () => {
  test.use({ baseURL: E2E_BASE_URL });

  async function login(page: import("@playwright/test").Page): Promise<void> {
    const creds = requireDemoCreds();
    await page.goto(`${E2E_BASE_URL}/login`);
    await page.getByLabel(/email/i).fill(creds.email);
    await page.getByRole("textbox", { name: /password/i }).fill(creds.password);
    await page.getByRole("button", { name: /sign in|log in/i }).click();
    await page.waitForURL(/^(?!.*\/(login|register)$).*/, {
      timeout: 15_000,
    });
  }

  test("Step 1: Grounded Business Analysis", async ({ page }) => {
    await login(page);
    await page.goto(`${E2E_BASE_URL}/assistant`);
    await expect(page).toHaveTitle(/AI Business Assistant/);

    const promptInput = page.getByRole("textbox", { name: /prompt/i }).first();
    await promptInput.fill("Help Acme Textiles grow from ₹1.8 Cr to ₹3 Cr without increasing supplier dependency.");
    await promptInput.press("Enter");

    await page.waitForTimeout(5000);
    await page.screenshot({
      path: "docs/submission/screenshots/h7-9-real-grounded-gemini.png",
      fullPage: true,
    });
  });

  test("Step 2: Exploratory Business Advisor Mode", async ({ page }) => {
    await login(page);
    await page.goto(`${E2E_BASE_URL}/assistant`);

    // Toggle to Open / Exploratory mode if available
    const modeToggle = page.getByRole("button", { name: /exploratory/i });
    if (await modeToggle.isVisible()) {
      await modeToggle.click();
    }

    const promptInput = page.getByRole("textbox", { name: /prompt/i }).first();
    await promptInput.fill("Analyze everything you know about Acme Textiles and propose five creative strategies to grow.");
    await promptInput.press("Enter");

    await page.waitForTimeout(5000);
    await page.screenshot({
      path: "docs/submission/screenshots/h7-9-exploratory-business-advisor.png",
      fullPage: true,
    });
  });

  test("Step 3: Deterministic Fallback Mode", async ({ page }) => {
    await login(page);
    await page.goto(`${E2E_BASE_URL}/assistant`);

    const promptInput = page.getByRole("textbox", { name: /prompt/i }).first();
    await promptInput.fill("What is my overall business health score and why?");
    await promptInput.press("Enter");

    await page.waitForTimeout(5000);
    await page.screenshot({
      path: "docs/submission/screenshots/h7-9-deterministic-fallback.png",
      fullPage: true,
    });
  });
});
