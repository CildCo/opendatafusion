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

test("wave G: engine dialogs open and close", async ({ page }) => {
  test.setTimeout(120000);
  await login(page);
  await page.goto("/ui/#/engines");
  for (const label of ["提交作业", "运行 SQL", "引擎配置"]) {
    try {
      await page.getByRole("button", { name: label, exact: true }).click();
      const dialog = page.locator(".el-dialog:visible, .el-drawer:visible")
        .last();
      await expect(dialog).toBeVisible({ timeout: 10000 });
      await dialog.locator(".el-dialog__headerbtn, .el-drawer__close-btn")
        .first().click({ force: true });
      await expect(dialog).toBeHidden({ timeout: 5000 });
    } catch (error) {
      throw new Error(`${label}: ${error.message.split("\n")[0]}`);
    }
  }
});

test("wave G: metric drawer shows definition, lineage and usage",
     async ({ page }) => {
  test.setTimeout(120000);
  await login(page);
  await page.goto("/ui/#/metrics");
  await page.getByRole("tab", { name: "指标" }).click();
  const usage = page.locator(".el-table__body tbody tr").first()
    .locator("button").filter({ hasText: "处" }).first();
  await usage.click();
  const drawer = page.locator(".el-drawer:visible");
  await expect(drawer).toBeVisible({ timeout: 10000 });
  await expect(drawer).toContainText("指标详情");
  await expect(drawer).toContainText("血缘");
  await drawer.locator(".el-drawer__close-btn").click();
  await expect(drawer).toBeHidden();
});

test("wave G: pipeline editor opens from the list", async ({ page }) => {
  test.setTimeout(120000);
  await login(page);
  await page.goto("/ui/#/pipelines");
  const row = page.locator(".el-table__body tbody tr").first();
  await expect(row).toBeVisible({ timeout: 10000 });
  await row.click();
  await expect(page).toHaveURL(/pipelines\/\d+/, { timeout: 10000 });
  await expect(page.getByText(/节点|画布|发布|保存/).first()).toBeVisible(
    { timeout: 10000 });
});
