import { expect, test } from "@playwright/test";

async function login(page) {
  await page.addInitScript(() => localStorage.setItem("odf_locale", "zh"));
  await page.goto("/ui/#/login");
  await page.locator(".el-form-item").filter({ hasText: "用户名" })
    .locator("input").fill("admin");
  await page.locator(".el-form-item").filter({ hasText: "密码" })
    .locator("input").fill(process.env.ODF_SWEEP_PASSWORD || "");
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page).toHaveURL(/dashboard/, { timeout: 15000 });
}

test("wave Z1: contract quality checks", async ({ page }) => {
  test.setTimeout(90000);
  await login(page);
  await page.goto("/ui/#/governance");
  await page.getByRole("tab", { name: "数据契约" }).click();
  const row = page.locator("tr", { hasText: "orders dataset" }).first();
  await row.getByRole("button", { name: "新鲜度" }).click();
  const dialog = page.locator(".el-dialog:visible");
  await dialog.getByRole("button", { name: "添加检查" }).click();
  const check = dialog.locator(".quality-row").last();
  await check.locator("input").nth(1).fill("city");
  await dialog.getByRole("button", { name: "保存" }).click();
  await expect(page.locator(".el-message--success").last())
    .toContainText("契约设置已更新", { timeout: 10000 });
  await row.getByRole("button", { name: "校验" }).click();
  const result = page.locator(".el-dialog:visible")
    .filter({ hasText: "结构与契约" });
  await expect(result).toContainText("quality", { timeout: 15000 });
  await expect(result).toContainText("city");
});

test("wave Z2: SLA breach raises an alert", async ({ page }) => {
  test.setTimeout(90000);
  await login(page);
  await page.goto("/ui/#/quality");
  const row = page.locator("tr", { hasText: "orders city not null" })
    .first();
  await row.getByRole("button", { name: "执行" }).click();
  await expect(page.locator(".el-message").last()).toBeVisible({
    timeout: 20000,
  });
  await page.goto("/ui/#/alerts");
  await expect(page.locator("tr", { hasText: "quality SLA breach" }).first())
    .toBeVisible({ timeout: 15000 });
});

test("wave Z3: archive and prune", async ({ page }) => {
  test.setTimeout(90000);
  await login(page);
  await page.goto("/ui/#/admin/operations");
  await page.getByRole("button", { name: "归档并清理" }).click();
  const confirm = page.locator(".el-message-box:visible");
  await confirm.getByRole("button", { name: "确定" }).click();
  await expect(page.locator(".el-message--success").last())
    .toContainText("清理完成", { timeout: 15000 });
});
