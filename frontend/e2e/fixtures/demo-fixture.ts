/**
 * H7.2 — minimal Playwright fixtures.
 *
 * The Playwright run reads every secret and the public URL from environment
 * variables. The repo intentionally NEVER carries hardcoded test credentials
 * — see `e2e/README.md` for the list.
 */

import { test as base, expect, type Page, type ConsoleMessage } from "@playwright/test";

/* --------------------------- env contract ---------------------------- */

function requireEnv(name: string): string {
  const v = process.env[name];
  if (!v || v.trim().length === 0) {
    throw new Error(
      `[e2e] missing required env var: ${name}. ` +
        `Set it before running (see e2e/README.md).`,
    );
  }
  return v;
}

export const E2E_BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:3000";
export const E2E_DEMO_EMAIL = process.env.E2E_DEMO_EMAIL ?? "";
export const E2E_DEMO_PASSWORD = process.env.E2E_DEMO_PASSWORD ?? "";
export const E2E_DEMO_FULL_NAME = process.env.E2E_DEMO_FULL_NAME ?? "H7.2 Demo User";

/* ----------------------- console + network traps ----------------------- */

/**
 * Attached to every page via fixture. Collects:
 *   - all console messages (filterable by level)
 *   - all failed network requests
 *
 * The H7.2 completion gate requires "no unexpected console errors". The
 * test harness intentionally allows 401s on /api/v1/auth/* pages during
 * the unauthenticated starting leg of the journey, then asserts zero
 * errors on the protected routes.
 */
export type FailedRequest = {
  url: string;
  failure: string | null;
  method: string;
};
export type ConsoleEntry = {
  type: string;
  text: string;
};

export type DemoFixtures = {
  consoleSink: { entries: ConsoleEntry[]; failed: FailedRequest[] };
  demoLogin: () => Promise<void>;
};

/* --------------------------- test extension --------------------------- */

export const test = base.extend<DemoFixtures>({
  consoleSink: async ({ page }, use) => {
    const sink: { entries: ConsoleEntry[]; failed: FailedRequest[] } = {
      entries: [],
      failed: [],
    };

    const onConsole = (m: ConsoleMessage) => {
      sink.entries.push({ type: m.type(), text: m.text() });
    };
    const onRequestFailed = (req: import("@playwright/test").Request) => {
      sink.failed.push({
        url: req.url(),
        failure: req.failure()?.errorText ?? null,
        method: req.method(),
      });
    };

    page.on("console", onConsole);
    page.on("requestfailed", onRequestFailed);

    await use(sink);

    page.off("console", onConsole);
    page.off("requestfailed", onRequestFailed);
  },

  demoLogin: async ({ page }, use) => {
    const fn = async () => {
      const { email, password } = requireDemoCreds();
      await page.goto(`${E2E_BASE_URL}/login`);
      await page.fill('input[type="email"]', email);
      await page.fill('input[type="password"]', password);
      await page.click('button[type="submit"]');
      await page.waitForURL((url) => !url.pathname.includes("/login"));
    };
    await use(fn);
  },
});

export { expect };

/* ----------------------------- assertions ----------------------------- */

/**
 * Core per-route assertion: title visible, no blank, no unexpected errors,
 * no NaN, no horizontal overflow. Used by both the critical-flow spec
 * and the accessibility spec.
 */
export async function assertHealthyRoute(
  page: Page,
  label: string,
  expectedTitleIncludes: string,
): Promise<void> {
  // 1. Title is present and non-empty.
  const title = await page.title();
  expect(
    title.length,
    `[${label}] page title is empty`,
  ).toBeGreaterThan(0);

  // 2. Title contains the expected keyword.
  expect(
    title.toLowerCase().includes(expectedTitleIncludes.toLowerCase()),
    `[${label}] title '${title}' does not contain '${expectedTitleIncludes}'`,
  ).toBe(true);

  // 3. Visible page heading is rendered (not blank).
  const visibleText = (await page.locator("body").innerText()).trim();
  expect(
    visibleText.length,
    `[${label}] page body has no visible text`,
  ).toBeGreaterThan(20);

  // 4. No rendered "undefined" / "NaN" / "[object Object]" tokens (data correctness).
  expect(
    /\bundefined\b/.test(visibleText),
    `[${label}] body contains the literal 'undefined' — likely a serializer bug`,
  ).toBe(false);
  expect(
    /\bNaN\b/.test(visibleText),
    `[${label}] body contains 'NaN' — a computation likely failed silently`,
  ).toBe(false);
  expect(
    /\[object Object\]/.test(visibleText),
    `[${label}] body contains '[object Object]' — an object was stringified`,
  ).toBe(false);

  // 5. No horizontal overflow on desktop.
  const docW = await page.evaluate(() => document.documentElement.scrollWidth);
  const winW = await page.evaluate(() => window.innerWidth);
  expect(
    docW <= winW + 2,
    `[${label}] horizontal overflow: scrollWidth=${docW}, viewport=${winW}`,
  ).toBe(true);
}

/**
 * Filter for *unexpected* console errors. /api/v1/auth/* 401s are expected
 * on the public pages during the unauthenticated start of the journey;
 * we permit them but capture them.
 */
export function unexpectedErrors(
  sink: ConsoleEntry[],
): ConsoleEntry[] {
  return sink.filter(
    (e) => e.type === "error" && !isAllowedDevError(e.text),
  );
}

function isAllowedDevError(text: string): boolean {
  // Some React DevTools / Next dev warnings are noise, not failures.
  const allowed = [
    "Download the React DevTools",
    "Fast Refresh",
  ];
  return allowed.some((needle) => text.includes(needle));
}

/** Env-var gate. Throws if the test was launched without credentials. */
export function requireDemoCreds(): { email: string; password: string } {
  return {
    email: requireEnv("E2E_DEMO_EMAIL"),
    password: requireEnv("E2E_DEMO_PASSWORD"),
  };
}
