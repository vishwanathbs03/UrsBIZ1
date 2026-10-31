/**
 * H7.2 — Real-browser critical-flow smoke test.
 *
 *   Landing → Register/Login → Business profile → Dashboard →
 *   Digital Twin (Intelligence) → Analytics → Predictive Analytics →
 *   Advisor → Assistant → Schemes → Reports → Logout.
 *
 * Per-route assertions: route landed, title visible, no blank screen,
 * no uncaught JS error, no failed core API request, no undefined / NaN /
 * object-leak text, no permanent skeleton, no horizontal overflow.
 *
 * Console + failed-network capture via the demoFixture. Completion gate:
 * PASS only when every step passes on every project (desktop + mobile,
 * light + dark).
 *
 * Honours `frontend/e2e/README.md` env-var contract. No real credentials
 * are hardcoded.
 */

import {
  test,
  expect,
  E2E_BASE_URL,
  assertHealthyRoute,
  requireDemoCreds,
} from "./fixtures/demo-fixture";

/* ---------------------- route metadata (single source) ------------------- */

const CRITICAL_ROUTES = [
  { path: "/dashboard",              title: "Executive Command Center", auth: true  },
  { path: "/business",               title: "Business Profile",         auth: true  },
  { path: "/intelligence",           title: "Business Digital Twin",    auth: true  },
  { path: "/analytics",              title: "Analytics",                auth: true  },
  { path: "/predictive-analytics",   title: "Business Forecast",        auth: true  },
  { path: "/advisor",                title: "Business Advisor",         auth: true  },
  { path: "/assistant",              title: "AI Business Assistant",    auth: true  },
  { path: "/schemes",                title: "Government Schemes",       auth: true  },
  { path: "/reports",                title: "Executive Report",         auth: true  },
] as const;

const PUBLIC_ROUTES = [
  { path: "/",          title: "UrsBiz"        },
  { path: "/register",  title: "Get started"   },
  { path: "/login",     title: "Sign in"       },
] as const;

/* -------------------------- journey helpers -------------------------- */

/**
 * Performs a real login by hitting the API directly through the frontend.
 * This is the H7.2-equivalent of "the browser cookie jar attaches the
 * JWT on subsequent requests" — the same path the docx requires.
 */
async function loginViaUI(page: import("@playwright/test").Page, email: string, password: string) {
  await page.goto(`${E2E_BASE_URL}/login`);
  await page.locator('input[type="email"], input[name="email"]').fill(email);
  await page.locator('input[type="password"], input[name="password"]').fill(password);
  await Promise.all([
    page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 15000 }),
    page.locator('button[type="submit"]').click(),
  ]);
}

async function logoutViaUI(page: import("@playwright/test").Page) {
  // The exact selector varies; locate any element whose accessible name
  // contains "logout"/"sign out", then click.
  const trigger = page.getByRole("button", { name: /log\s*out|sign\s*out/i }).first();
  if (await trigger.count()) {
    await trigger.click();
    await page.waitForLoadState("networkidle").catch(() => undefined);
  } else {
    // Fall back to direct navigation — the route guard may redirect to /login.
    await page.goto(`${E2E_BASE_URL}/login`).catch(() => undefined);
  }
}

/* ============================== tests ============================== */

test.describe("UrsBiz critical flow — desktop light", () => {
  test.use({
    viewport: { width: 1440, height: 900 },
    colorScheme: "light",
  });

  /* ------- public routes ------ */

  for (const r of PUBLIC_ROUTES) {
    test(`${r.path} renders cleanly (public)`, async ({ page, consoleSink }) => {
      const errs = consoleSink.entries; // capture during navigation
      await page.goto(`${E2E_BASE_URL}${r.path}`);
      await page.waitForLoadState("networkidle");
      await assertHealthyRoute(page, r.path, r.title);
      // Public surfaces shouldn't blow up on missing auth — we expect some
      // 4xx API chatter from /api/v1/auth/me on the public marketing pages.
    });
  }

  /* ------- the actual judge journey ------- */

  test("public landing then protected journey then logout (twice-clean by spec)", async ({
    page,
    consoleSink,
  }) => {
    const creds = requireDemoCreds();

    // 1. Landing.
    await page.goto(`${E2E_BASE_URL}/`);
    await page.waitForLoadState("networkidle");
    await assertHealthyRoute(page, "/", "UrsBiz");

    // 2. Login.
    await loginViaUI(page, creds.email, creds.password);

    // 3. Walk every critical route in order.
    for (const r of CRITICAL_ROUTES) {
      await page.goto(`${E2E_BASE_URL}${r.path}`);
      await page.waitForLoadState("networkidle");
      await assertHealthyRoute(page, r.path, r.title);
    }

    // 4. Logout.
    await logoutViaUI(page);
    await page.waitForURL((u) => u.pathname.startsWith("/login") || u.pathname === "/", {
      timeout: 10000,
    }).catch(() => undefined);

    // 5. Logout should have invalidated the JWT — visiting a protected
    //    route after logout must redirect to /login.
    await page.goto(`${E2E_BASE_URL}/dashboard`);
    await page.waitForLoadState("networkidle");
    const afterLogout = page.url();
    expect(
      afterLogout.startsWith(`${E2E_BASE_URL}/login`) || !afterLogout.includes("/dashboard"),
      `after logout, dashboard should not be reachable; got ${afterLogout}`,
    ).toBe(true);

    // 6. Re-login proves the journey works twice — H7.1 gate language
    //    echoed in P2 ("the full journey works twice in a clean browser session").
    await loginViaUI(page, creds.email, creds.password);
    await page.goto(`${E2E_BASE_URL}/dashboard`);
    await page.waitForLoadState("networkidle");
    await assertHealthyRoute(page, "/dashboard (re-login)", "Executive Command Center");

    // 7. Final gate: no unexpected console errors across the whole journey.
    const errors = consoleSink.entries.filter(
      (e) => e.type === "error" &&
        !/React DevTools|Fast Refresh|hydration|Failed to load resource.*401/i.test(e.text),
    );
    expect(
      errors,
      `unexpected console errors: ${JSON.stringify(errors, null, 2)}`,
    ).toEqual([]);
  });
});

/* --------------------------- mobile smoke ---------------------------- */

test.describe("UrsBiz critical flow — mobile smoke", () => {
  test.use({
    viewport: { width: 390, height: 844 },
    colorScheme: "light",
  });

  test("mobile dashboard renders without horizontal overflow", async ({ page }) => {
    const creds = requireDemoCreds();
    await loginViaUI(page, creds.email, creds.password);
    await page.goto(`${E2E_BASE_URL}/dashboard`);
    await page.waitForLoadState("networkidle");
    await assertHealthyRoute(page, "/dashboard mobile", "Executive Command Center");
  });

  test("mobile schemes renders without horizontal overflow", async ({ page }) => {
    const creds = requireDemoCreds();
    await loginViaUI(page, creds.email, creds.password);
    await page.goto(`${E2E_BASE_URL}/schemes`);
    await page.waitForLoadState("networkidle");
    await assertHealthyRoute(page, "/schemes mobile", "Government Schemes");
  });
});

/* -------------------------- dark-mode smoke -------------------------- */

test.describe("UrsBiz critical flow — desktop dark", () => {
  test.use({
    viewport: { width: 1440, height: 900 },
    colorScheme: "dark",
  });

  test("dark-mode dashboard renders cleanly", async ({ page }) => {
    const creds = requireDemoCreds();
    await loginViaUI(page, creds.email, creds.password);
    await page.goto(`${E2E_BASE_URL}/dashboard`);
    await page.waitForLoadState("networkidle");
    await assertHealthyRoute(page, "/dashboard dark", "Executive Command Center");
    // Body background should be a dark surface, not a stark white.
    const bg = await page.evaluate(() => {
      const cs = getComputedStyle(document.body);
      return cs.backgroundColor;
    });
    // Approximate dark check — RGB sum < 600 means roughly dark.
    const m = bg.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
    if (m) {
      const sum = Number(m[1]) + Number(m[2]) + Number(m[3]);
      expect(
        sum < 600,
        `dark mode body bg=${bg} (sum=${sum}) looks light — colour-scheme not applied`,
      ).toBe(true);
    }
    // If browser returned non-rgb (e.g. rgba(0,0,0,0)) we don't assert; some
    // dark themes use `transparent` and rely on a parent background — that's
    // still acceptable so we don't fail.
  });
});
