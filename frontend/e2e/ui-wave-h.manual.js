import { expect, test } from "@playwright/test";

const USER = process.env.ODF_SWEEP_USER || "admin";
const PASS = process.env.ODF_SWEEP_PASSWORD || "";
const PREFIXES = ["menu.", "catd.", "model.", "quality.",
                  "users.", "sec.", "audit.", "ops.", "eng.", "cdc.", "dep.",
                  "alerts.", "api.", "ds.", "i18n."];

test("console pages are fully translated in English", async ({ page }) => {
  test.setTimeout(180000);
  await page.addInitScript(() => localStorage.setItem("odf_locale", "zh"));
  await page.goto("/ui/#/login");
  await page.locator(".el-form-item").filter({ hasText: "用户名" })
    .locator("input").fill(USER);
  await page.locator(".el-form-item").filter({ hasText: "密码" })
    .locator("input").fill(PASS);
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page).toHaveURL(/dashboard/, { timeout: 15000 });

  await page.getByRole("button", { name: "English" }).click();
  await expect(page.getByRole("button", { name: "English" })).toHaveCount(0);

  for (const route of ["/dashboard", "/datasources", "/quality",
                       "/admin/users", "/ops"]) {
    await page.goto(`/ui/#${route}`);
    await page.waitForTimeout(800);
    const text = await page.locator("main, .admin-content").first().innerText();
    expect(text.length).toBeGreaterThan(0);
    for (const prefix of PREFIXES) {
      expect(text, `${route} shows raw key ${prefix}...`)
        .not.toContain(prefix);
    }
    expect(text).toMatch(/[A-Za-z]{3,}/);
  }

  await page.goto("/ui/#/dashboard");
  await page.getByRole("button", { name: "中文" }).click();
  await expect(page.getByRole("button", { name: "English" })).toBeVisible();
});
