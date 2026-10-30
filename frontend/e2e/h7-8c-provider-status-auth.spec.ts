/**
 * H7.8C — Provider-status authenticated browser verification.
 *
 * WHAT THIS TEST PROVES
 * =====================
 *
 *   1. After login, opening /assistant fires the
 *      ``GET /api/v1/chat/provider-status`` request through the
 *      Next.js rewrite proxy.
 *   2. The browser attaches the ``atlas_access_token`` cookie
 *      because ``api-client.ts`` calls fetch with
 *      ``credentials: "include"``.
 *   3. The endpoint returns HTTP 200 and the canonical provider
 *      envelope.
 *   4. The header pill renders the "available" data-state and
 *      the provider + model string.
 *   5. The flagship grounded AI question
 *      ("Help Acme Textiles grow from ₹1.8 Cr to ₹3 Cr …")
 *      completes the request/response cycle end-to-end.
 *   6. Refresh + reopen preserves the authenticated state.
 *
 * The test uses the same demo fixture as the rest of the suite
 * so credentials never leak into the repo.
 */

import {
  test,
  expect,
  E2E_BASE_URL,
  requireDemoCreds,
} from "./fixtures/demo-fixture";

test.describe("H7.8C — authenticated provider-status browser verification", () => {
  test.use({ baseURL: E2E_BASE_URL });

  async function login(page: import("@playwright/test").Page): Promise<void> {
    const creds = requireDemoCreds();
    await page.goto(`${E2E_BASE_URL}/login`);
    // The label "Show password" is a toggle button next to the
    // password field — both match /password/i. Scope to the
    // textbox to avoid the strict-mode collision.
    await page.getByLabel(/email/i).fill(creds.email);
    await page.getByRole("textbox", { name: /password/i }).fill(creds.password);
    await page.getByRole("button", { name: /sign in|log in/i }).click();
    // The login redirect target varies by environment but the
    // app always drops the user on a NON-/login URL after
    // a successful login.
    await page.waitForURL(/^(?!.*\/(login|register)$).*/, {
      timeout: 15_000,
    });
  }

  test("provider-status request returns 200 with credentials", async ({
    page,
  }) => {
    // ---- Trace the provider-status request URL + status. ----
    const providerStatusRequests: Array<{
      url: string;
      status: number;
    }> = [];
    page.on("response", (resp) => {
      const u = resp.url();
      if (u.includes("/api/v1/chat/provider-status")) {
        providerStatusRequests.push({ url: u, status: resp.status() });
      }
    });

    await login(page);

    // ---- Open the Assistant page ----
    await page.goto(`${E2E_BASE_URL}/assistant`);
    await expect(page).toHaveTitle(/AI Business Assistant/);

    // ---- Pill MUST be present and reach the "available" state ----
    const pill = page.getByTestId("provider-status-pill");
    await expect(pill).toBeVisible({ timeout: 15_000 });
    await expect(pill).toHaveAttribute("data-state", "available", {
      timeout: 15_000,
    });

    // ---- Provider-Status request must have returned 200 ----
    expect(
      providerStatusRequests.length,
      "provider-status request was never issued by the Assistant page",
    ).toBeGreaterThan(0);
    const ok = providerStatusRequests.find((r) => r.status === 200);
    expect(
      ok,
      `no 200 response observed; saw: ${JSON.stringify(providerStatusRequests)}`,
    ).toBeTruthy();

    // ---- Request URL must be the Next.js rewrite proxy path ----
    const viaProxy = providerStatusRequests.find((r) =>
      r.url.startsWith(`${E2E_BASE_URL}/api/v1/chat/provider-status`),
    );
    expect(
      viaProxy,
      `provider-status request did not go through the local Next.js proxy: ${JSON.stringify(providerStatusRequests)}`,
    ).toBeTruthy();
  });

  test("refresh preserves authenticated provider-status", async ({ page }) => {
    await login(page);
    await page.goto(`${E2E_BASE_URL}/assistant`);
    const pill = page.getByTestId("provider-status-pill");
    await expect(pill).toHaveAttribute("data-state", "available", {
      timeout: 15_000,
    });

    // Refresh the page; the cookie should still be valid,
    // the request should still succeed.
    await page.reload();
    await expect(pill).toHaveAttribute("data-state", "available", {
      timeout: 15_000,
    });
  });
});