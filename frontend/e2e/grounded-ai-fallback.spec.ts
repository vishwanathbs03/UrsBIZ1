/**
 * H7.8C — Deterministic fallback browser verification.
 *
 * Unconditional: this spec must pass on every CI run, with
 * the backend in its default configuration (no real provider
 * available). It proves the system is honest when the
 * provider is unreachable:
 *
 *   - the trust badge reads "Calculated by UrsBiz rule engine"
 *   - the TrustMeta disclosure reveals the fallback reason
 *   - the page does not crash, no forbidden phrases appear
 *
 * Captures ``frontend/e2e/screenshots/h7-8c/grounded-ai-fallback.png``.
 */
import {
  test,
  expect,
  E2E_BASE_URL,
  requireDemoCreds,
} from "./fixtures/demo-fixture";

const FALLBACK_PROMPT =
  "What is my overall business health and why?";

test.describe("H7.8C — deterministic fallback path", () => {
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

  test("deterministic fallback surfaces a rule-engine badge", async ({
    page,
  }) => {
    await login(page);
    await page.goto(`${E2E_BASE_URL}/assistant`);
    await expect(page).toHaveTitle(/AI Business Assistant/);

    // Provider-status pill must be visible (state may be "unavailable"
    // or "available-fallback"; either is fine for this test).
    await expect(page.getByTestId("provider-status-pill")).toBeVisible({
      timeout: 15_000,
    });

    // Start a fresh server-side conversation.
    await page.getByRole("button", { name: /new conversation/i }).click();

    // Submit the prompt.
    const promptInput = page.getByRole("textbox", { name: /prompt/i }).first();
    await promptInput.fill(FALLBACK_PROMPT);
    await promptInput.press("Enter");

    // Wait for the badge to appear — must be the rule-engine variant.
    const fallbackBadge = page.getByText(/Calculated by UrsBiz rule engine/);
    await expect(fallbackBadge).toBeVisible({
      timeout: 30_000,
    });

    // The "Generated explanation" badge MUST NOT appear in the
    // fallback path — if it does, the backend is silently lying
    // about provenance.
    const generatedBadge = page.getByText(/Generated explanation/);
    expect(
      await generatedBadge.count(),
      "Generated explanation badge appeared in fallback path — provenance leak",
    ).toBe(0);

    // TrustMeta disclosure must show a fallback reason.
    const trustMeta = page.getByTestId("trust-meta").first();
    await trustMeta.click();
    await expect(trustMeta).toContainText(/Fallback reason:/i);

    // No forbidden hallucination phrases.
    const body = await page.locator("body").innerText();
    expect(/you are eligible/i.test(body)).toBe(false);
    expect(/guaranteed funding/i.test(body)).toBe(false);

    // Capture screenshot for the evidence report.
    await page.screenshot({
      path: "frontend/e2e/screenshots/h7-8c/grounded-ai-fallback.png",
      fullPage: true,
    });
  });
});
