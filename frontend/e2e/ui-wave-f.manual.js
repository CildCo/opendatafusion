import { expect, test } from "@playwright/test";

const USER = process.env.ODF_SWEEP_USER || "admin";
const PASS = process.env.ODF_SWEEP_PASSWORD || "";
const STAMP = Date.now().toString(36).slice(-5);

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

test("wave F: create a user, change role and deactivate",
     async ({ page }) => {
  test.setTimeout(120000);
  await login(page);
  await page.goto("/ui/#/users");
  const name = `ui_user_${STAMP}`;
  await page.getByRole("button", { name: "新建用户" }).first().click();
  const dialog = page.locator(".el-dialog:visible");
  const items = dialog.locator(".el-form-item");
  await items.nth(0).locator("input").fill(name);
  await items.nth(1).locator("input").fill("UiPassw0rd!");
  await dialog.getByRole("button", { name: "保存" }).click();
  await expect(page.locator(".el-message--success")
    .filter({ hasText: "已创建" })).toBeVisible({ timeout: 10000 });

  const row = page.locator("tr", { hasText: name });
  await expect(row).toBeVisible();
  await row.locator(".el-select").click();
  await page.locator(".el-select-dropdown:visible").last()
    .locator(".el-select-dropdown__item").filter({ hasText: "editor" })
    .first().click();
  await page.locator(".el-message-box").getByRole("button", { name: "确定" })
    .click();
  await expect(page.locator(".el-message--success").last()).toBeVisible(
    { timeout: 10000 });

  await row.locator(".el-switch").first().click();
  await expect(row.locator(".el-switch.is-checked")).toHaveCount(0,
    { timeout: 10000 });
});

test("wave F: hide a menu in workspace settings and restore it",
     async ({ page }) => {
  test.setTimeout(120000);
  await login(page);
  await page.goto("/ui/#/workspace");
  const box = page.locator(".el-checkbox").filter({ hasText: "AI 工具" })
    .first();
  await box.click();
  await page.getByRole("button", { name: "保存" }).first().click();
  await expect(page.locator(".el-message--success")).toBeVisible(
    { timeout: 10000 });
  await page.reload();
  await page.waitForTimeout(1500);
  await expect(page.locator("nav a", { hasText: "AI 工具" }))
    .toHaveCount(0);

  await page.goto("/ui/#/workspace");
  await page.locator(".el-checkbox").filter({ hasText: "AI 工具" })
    .first().click();
  await page.getByRole("button", { name: "保存" }).first().click();
  await expect(page.locator(".el-message--success")).toBeVisible(
    { timeout: 10000 });
  await page.reload();
  await page.waitForTimeout(1500);
  await expect(page.locator("nav a", { hasText: "AI 工具" }))
    .toHaveCount(1);
});

test("wave F: audit filters and CSV export", async ({ page }) => {
  test.setTimeout(120000);
  await login(page);
  await page.goto("/ui/#/audit");
  await page.getByPlaceholder("按动作过滤").fill("delete_flow");
  await page.getByRole("button", { name: "查询" }).click();
  await page.waitForTimeout(800);
  const rows = page.locator(".el-table-v2__row, .el-table__body tbody tr");
  await expect(rows.first()).toBeVisible({ timeout: 10000 });
  const first = await rows.first().innerText();
  expect(first).toContain("delete_flow");

  const download = page.waitForEvent("download", { timeout: 15000 });
  await page.getByRole("button", { name: "导出 CSV" }).click();
  const file = await download;
  expect(file.suggestedFilename()).toBe("audit.csv");
});

test("wave F: security page validates a password change", async ({ page }) => {
  test.setTimeout(120000);
  await login(page);
  await page.goto("/ui/#/security");
  const inputs = page.locator("input[type=password]");
  await inputs.nth(0).fill("wrong-current");
  await inputs.nth(1).fill("NewPassw0rd!");
  await inputs.nth(2).fill("DifferentPass!");
  await page.getByRole("button", { name: "更新密码" }).click();
  await expect(page.locator(".el-message--error").last()).toBeVisible(
    { timeout: 10000 });
});
