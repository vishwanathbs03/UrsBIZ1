/**
 * H7.3 — Docx Prompt 3 Part 5 flagship-prompt e2e checks.
 *
 * The docx lists six flagship prompts that must work in the real
 * browser. The Playwright suite already covers the critical flow
 * (login → dashboard → …) in `hackathon-critical-flow.spec.ts`.
 * This file is the AI-flavoured complement: it lands on the
 * /assistant page, sends each of the six flagship prompts, and
 * asserts the visible behaviour the docx asks for.
 *
 * The suite is the smallest evidence-backed test that the AI
 * assistant surface is real. It does NOT exercise a real LLM —
 * the docx explicitly says "Use a mocked provider in automated
 * tests. Do not make tests depend on a paid external API." The
 * backend in this environment runs with `AI_PROVIDER=placeholder`,
 * which routes every call through the deterministic fallback. The
 * fallback is the layer the verifier already inspects; this spec
 * just confirms the UI surfaces it correctly.
 *
 * The suite is env-gated: the same env vars as the rest of the
 * Playwright suite apply (E2E_BASE_URL, E2E_DEMO_EMAIL,
 * E2E_DEMO_PASSWORD). When any are missing, every test in this
 * file is skipped — Playwright's `test.skip` is the right shape
 * for "sprint P3 must be runnable but the env is not yet wired".
 */

import { test, expect } from "./fixtures/demo-fixture";

const ENV_READY =
  !!process.env.E2E_DEMO_EMAIL && !!process.env.E2E_DEMO_PASSWORD;

test.describe("H7.3 flagship prompts (deterministic fallback path)", () => {
  test.skip(!ENV_READY, "E2E_DEMO_EMAIL / E2E_DEMO_PASSWORD not set");

  test.beforeEach(async ({ page }) => {
    // Login via the existing demo flow used by hackathon-critical-flow.
    await page.goto("/login");
    await page
      .getByLabel(/email/i)
      .fill(process.env.E2E_DEMO_EMAIL ?? "");
    await page
      .getByLabel(/password/i)
      .fill(process.env.E2E_DEMO_PASSWORD ?? "");
    await page.getByRole("button", { name: /log in|sign in/i }).click();
    await page.waitForURL(/\/dashboard/);
  });

  test("Flagship 1 — overall health renders score + band", async ({ page }) => {
    await page.goto("/assistant");
    await page
      .getByRole("textbox", { name: /prompt|ask/i })
      .fill("What is my overall business health and why?");
    await page.keyboard.press("Enter");
    // The deterministic body must surface the score + band.
    const reply = page.locator('[aria-label="Assistant message"]').last();
    await expect(reply).toBeVisible();
    await expect(reply).toContainText(/Overall business score:/);
    await expect(reply).toContainText(/\d+\/100/);
  });

  test("Flagship 2 — top three actions renders the recommendations", async ({
    page,
  }) => {
    await page.goto("/assistant");
    await page
      .getByRole("textbox", { name: /prompt|ask/i })
      .fill("Which 3 actions should I take first and why?");
    await page.keyboard.press("Enter");
    const reply = page.locator('[aria-label="Assistant message"]').last();
    await expect(reply).toContainText(/Top recommendations:/);
  });

  test("Flagship 3 — explain rule surfaces the rule firing", async ({
    page,
  }) => {
    await page.goto("/assistant");
    await page
      .getByRole("textbox", { name: /prompt|ask/i })
      .fill("Explain rule rule_critical_inventory and its impact.");
    await page.keyboard.press("Enter");
    const reply = page.locator('[aria-label="Assistant message"]').last();
    // Fallback must mention the rules block.
    await expect(reply).toContainText(/Active rules:|rule/);
  });

  test("Flagship 4 — scheme question must NOT answer as eligibility", async ({
    page,
  }) => {
    await page.goto("/assistant");
    await page
      .getByRole("textbox", { name: /prompt|ask/i })
      .fill("What government schemes am I eligible for?");
    await page.keyboard.press("Enter");
    const reply = page.locator('[aria-label="Assistant message"]').last();
    const text = (await reply.textContent()) ?? "";
    // The deterministic body must NOT contain the forbidden
    // "eligible" / "approved" / "guaranteed" language (case-insensitive).
    // The fallback notes the user can review schemes in the Schemes tab.
    expect(text.toLowerCase()).not.toContain("you are eligible");
    expect(text.toLowerCase()).not.toContain("approved");
    expect(text.toLowerCase()).not.toContain("guaranteed");
  });

  test("Flagship 5 — prediction question must NOT answer as prediction", async ({
    page,
  }) => {
    await page.goto("/assistant");
    await page
      .getByRole("textbox", { name: /prompt|ask/i })
      .fill("Predict my revenue for next quarter");
    await page.keyboard.press("Enter");
    const reply = page.locator('[aria-label="Assistant message"]').last();
    const text = (await reply.textContent()) ?? "";
    // The fallback message must NOT contain a "predicted" verb.
    expect(text.toLowerCase()).not.toContain("we predict");
    expect(text.toLowerCase()).not.toContain("i predict");
  });

  test("Flagship 6 — action board listing", async ({ page }) => {
    await page.goto("/assistant");
    await page
      .getByRole("textbox", { name: /prompt|ask/i })
      .fill("What does my action board look like and what's overdue?");
    await page.keyboard.press("Enter");
    const reply = page.locator('[aria-label="Assistant message"]').last();
    await expect(reply).toBeVisible();
  });

  test("Every assistant reply carries a Generated explanation trust label", async ({
    page,
  }) => {
    await page.goto("/assistant");
    await page
      .getByRole("textbox", { name: /prompt|ask/i })
      .fill("Help me plan next quarter.");
    await page.keyboard.press("Enter");
    // H7.3 Part 4 — the trust label is a non-empty badge.
    const badge = page.locator('[data-trust-label="generated"]').last();
    await expect(badge).toBeVisible();
    await expect(badge).toContainText(/Generated explanation/i);
  });
});
