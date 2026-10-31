import {
  test,
  expect,
  E2E_BASE_URL,
  requireDemoCreds,
} from "./fixtures/demo-fixture";

test("debug: see assistant page", async ({ page }) => {
  const creds = requireDemoCreds();
  await page.goto(`${E2E_BASE_URL}/login`);
  await page.getByLabel(/email/i).fill(creds.email);
  await page.getByRole("textbox", { name: /password/i }).fill(creds.password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForURL(/^(?!.*\/(login|register)$).*/, { timeout: 15_000 });
  console.log("URL after login:", page.url());
  await page.goto(`${E2E_BASE_URL}/assistant`);
  await page.waitForTimeout(8000);
  await page.screenshot({ path: "debug_assistant.png", fullPage: true });
  console.log("URL at assistant:", page.url());
  await page.waitForTimeout(3000);
  const html = await page.content();
  const idx = html.indexOf("provider-status-pill");
  console.log("---provider-status-pill snippet---");
  console.log(idx >= 0 ? html.substring(Math.max(0, idx - 200), idx + 800) : "(NOT FOUND in HTML)");
  await page.screenshot({ path: "debug_assistant.png", fullPage: true });
  const mainText = await page.locator("main").innerText().catch(() => "(no main)");
  console.log("---MAIN TEXT---");
  console.log(mainText.substring(0, 1500));
});
