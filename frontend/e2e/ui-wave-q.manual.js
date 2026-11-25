import fs from "node:fs";

import { expect, test } from "@playwright/test";

const USER = process.env.ODF_SWEEP_USER || "admin";
const PASS = process.env.ODF_SWEEP_PASSWORD || "";

async function login(page) {
  await page.addInitScript(() => localStorage.setItem("odf_locale", "zh"));
  await page.goto("/ui/#/login");
  await page.locator(".el-form-item").filter({ hasText: "用户名" })
    .locator("input").fill(USER);
  await page.locator(".el-form-item").filter({ hasText: "密码" })
    .locator("input").fill(PASS);
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page).toHaveURL(/dashboard/, { timeout: 15000 });
}

test("wave Q: a project environment and bundle are visible in admin",
     async ({ page }) => {
  test.setTimeout(180000);
  await login(page);
  await page.goto("/ui/#/admin/projects");
  const row = page.locator(".el-table__body tbody tr").first();
  await expect(row).toBeVisible({ timeout: 15000 });
  await expect(row.locator(".el-tag").first()).toContainText(/dev|staging|prod/);
  const download = page.waitForEvent("download", { timeout: 20000 });
  await row.getByRole("button", { name: "导出资产包" }).click();
  const file = await download;
  expect(file.suggestedFilename()).toContain("odf-bundle-");
  const path = await file.path();
  const payload = JSON.parse(fs.readFileSync(path, "utf8"));
  expect(payload.format).toBe("odf-bundle");
  expect(Array.isArray(payload.assets)).toBe(true);
  expect(JSON.stringify(payload)).not.toContain("dsn");
});
