/**
 * H7.2 — Playwright config.
 *
 *   - One baseURL, derived from E2E_BASE_URL (env var, never hardcoded).
 *   - 4 projects: desktop light, desktop dark, mobile light, mobile dark.
 *     Per docx P2: 1440x900 desktop, 390x844 mobile, light + dark.
 *   - Screenshots on failure (so the rerun can collect evidence) + on
 *     demand (collected by the capture-evidence spec when P6 lands).
 *   - Traces on retry so flaky journeys can be diagnosed without
 *     disabling the gate.
 *   - Workers: 1 in CI (so failures are reproducible); unlimited locally.
 *
 * NOTE: H7.2 only runs against a reachable frontend URL. The default
 * `E2E_BASE_URL` points at `http://localhost:3000`; once P6 deploys to
 * Render, set `E2E_BASE_URL` to the public URL.
 */

import { defineConfig, devices } from "@playwright/test";

const PORT = process.env.PORT ?? "3000";
const BASE_URL = process.env.E2E_BASE_URL ?? `http://localhost:${PORT}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false, // serialized against a shared backend
  workers: process.env.CI ? 1 : 1,
  reporter: process.env.CI ? [["list"], ["github"]] : "list",

  timeout: 30_000,
  expect: { timeout: 7_500 },

  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    // Keep the browser launched headless in CI; honour Playwright's env.
    headless: true,
  },

  /* ------------------- test-results / artefacts ------------------- */

  outputDir: "../../test-results/e2e",
  // Per the docx Master Operating Rules: test-results is a runtime
  // artefact, not a product artefact. The repo `.gitignore` already
  // covers `test-results` at the root.

  projects: [
    {
      name: "desktop-light",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 900 },
        colorScheme: "light",
      },
      testMatch: /.*\.spec\.ts/,
    },
    {
      name: "desktop-dark",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 900 },
        colorScheme: "dark",
      },
      testMatch: /.*\.spec\.ts/,
    },
    {
      name: "mobile-light",
      use: {
        ...devices["Pixel 7"],
        viewport: { width: 390, height: 844 },
        colorScheme: "light",
      },
      testMatch: /.*\.spec\.ts/,
    },
    {
      name: "mobile-dark",
      use: {
        ...devices["Pixel 7"],
        viewport: { width: 390, height: 844 },
        colorScheme: "dark",
      },
      testMatch: /.*\.spec\.ts/,
    },
  ],
});