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

test("wave X1: retention and system check", async ({ page }) => {
  test.setTimeout(90000);
  await login(page);
  await page.goto("/ui/#/admin/operations");
  await expect(page.getByText("数据保留", { exact: true })).toBeVisible({
    timeout: 15000,
  });
  await expect(page.getByText("系统自检", { exact: true })).toBeVisible();
  await expect(page.locator("tr", { hasText: "query_run" })).toBeVisible();
  await page.getByRole("button", { name: "预览可清理" }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 10000 });
  await page.getByRole("button", { name: "重新检查" }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 10000 });
});

test("wave X2: datasource limits", async ({ page }) => {
  test.setTimeout(60000);
  await login(page);
  await page.goto("/ui/#/datasources");
  const row = page.locator("tr", { hasText: "orders sqlite" }).first();
  await row.getByRole("button", { name: "限流" }).click();
  const dialog = page.locator(".el-dialog:visible");
  const numbers = dialog.locator(".el-input-number input");
  await numbers.nth(0).fill("5");
  await numbers.nth(1).fill("2");
  await dialog.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.locator(".el-message--success").last())
    .toContainText("限流设置已保存", { timeout: 10000 });
  await row.getByRole("button", { name: "限流" }).click();
  const again = page.locator(".el-dialog:visible");
  await expect(again.locator(".el-input-number input").nth(0))
    .toHaveValue("5");
  await expect(again.locator(".el-input-number input").nth(1))
    .toHaveValue("2");
  await again.getByRole("button", { name: "取消" }).click();
});

test("wave X3: scheduled contract checks", async ({ page }) => {
  test.setTimeout(120000);
  await login(page);
  await page.goto("/ui/#/governance");
  await page.getByRole("tab", { name: "数据契约" }).click();
  const row = page.locator("tr", { hasText: "orders dataset" }).first();
  await row.getByRole("button", { name: "新鲜度" }).click();
  const dialog = page.locator(".el-dialog:visible");
  await dialog.locator(".el-form-item").filter({ hasText: "检查计划" })
    .locator("input").fill("* * * * * *");
  await dialog.getByRole("button", { name: "保存" }).click();
  await expect(page.locator(".el-message--success").last())
    .toContainText("契约设置已更新", { timeout: 10000 });
  await page.waitForTimeout(12000);
  await row.getByRole("button", { name: "检查历史" }).click();
  const history = page.locator(".el-dialog:visible");
  await expect(history.locator(".el-table__row").first())
    .toBeVisible({ timeout: 15000 });
});

test("wave X4: dead letter replay", async ({ page }) => {
  test.setTimeout(90000);
  await login(page);
  await page.goto("/ui/#/ops");
  await page.getByRole("tab", { name: "死信" }).click();
  const row = page.locator(".el-tab-pane:visible tr",
                           { hasText: "dead pipeline" }).first();
  await expect(row).toBeVisible({ timeout: 15000 });
  await row.locator(".el-checkbox").click();
  await page.getByRole("button", { name: /重放所选/ }).click();
  const confirm = page.locator(".el-message-box:visible");
  await confirm.getByRole("button", { name: "确定" }).click();
  await expect(page.locator(".el-message--success").last())
    .toContainText("已重放", { timeout: 15000 });
});
