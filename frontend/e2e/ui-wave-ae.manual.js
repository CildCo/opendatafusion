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

test("wave AE1: schedules and run policies", async ({ page }) => {
  test.setTimeout(120000);
  await login(page);
  await page.goto("/ui/#/ops");

  await page.getByRole("tab", { name: "调度视图" }).click();
  const schedule = page.locator(".el-tab-pane:visible tr")
    .filter({ hasText: "matrix pipeline" }).first();
  await expect(schedule).toBeVisible({ timeout: 15000 });
  await expect(schedule).toContainText("0 0 2 * * *");
  await expect(schedule).toContainText("success");

  await page.getByRole("tab", { name: "运行策略" }).click();
  const policy = page.locator(".el-tab-pane:visible tr")
    .filter({ hasText: "matrix pipeline" }).first();
  await expect(policy).toBeVisible({ timeout: 15000 });
  const numbers = policy.locator(".el-input-number input");
  await numbers.nth(0).fill("6");
  await numbers.nth(1).fill("20");
  await policy.getByRole("button", { name: "保存" }).click();
  await expect(page.locator(".el-message").last())
    .toContainText("运行策略已保存", { timeout: 15000 });
});

test("wave AE2: job detail and previous run comparison",
     async ({ page }) => {
  test.setTimeout(120000);
  await login(page);
  await page.goto("/ui/#/ops");
  await page.getByRole("tab", { name: "任务" }).click();
  const row = page.locator(".el-tab-pane:visible .el-table__row")
    .filter({ hasText: "matrix pipeline" }).first();
  await expect(row).toBeVisible({ timeout: 15000 });
  await row.click();

  const drawer = page.locator(".el-drawer:visible");
  await expect(drawer).toContainText("Job #", { timeout: 15000 });
  await expect(drawer).toContainText("节点运行");
  await expect(drawer).toContainText("src");
  await expect(drawer).toContainText("输出行");
  await expect(drawer).toContainText("与上次运行对比");
  await expect(drawer).toContainText("上次作业 #1");
  await expect(drawer).toContainText("-20");
  await expect(drawer).toContainText("+40");
});
