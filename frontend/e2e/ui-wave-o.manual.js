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

test("wave O: onboarding sample, notifications and convergence labels",
     async ({ page }) => {
  test.setTimeout(180000);
  await login(page);

  // Legacy entries are explicitly marked while the unified asset model is
  // the primary path.
  const nav = page.locator(".rail-nav");
  await expect(nav).toContainText("数据集成（旧版）");
  await expect(nav).toContainText("SQL 接口（旧版）");

  // One-click sample data creates a published delivery path.
  await page.goto("/ui/#/dashboard");
  const sample = page.getByRole("button", { name: "创建示例数据" });
  await expect(sample).toBeVisible({ timeout: 15000 });
  await sample.click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 30000 });
  await expect(page).toHaveURL(/dashboards\/\d+\/run/, { timeout: 30000 });
  await expect(page.locator(".run-page")).toBeVisible({ timeout: 15000 });
  await expect(page.locator(".canvas")).toBeVisible({ timeout: 15000 });

  // The notification centre receives the publish events and can mark them.
  await page.locator(".top-actions .el-badge").click();
  const drawer = page.locator(".el-drawer:visible");
  await expect(drawer).toContainText("通知", { timeout: 10000 });
  await expect(drawer.locator(".notif-item").first())
    .toBeVisible({ timeout: 10000 });
  const readAll = drawer.getByRole("button", { name: "全部标为已读" });
  if (await readAll.isEnabled()) await readAll.click();
  await page.waitForTimeout(400);
  await drawer.locator(".el-drawer__close-btn").click();

  // The onboarding checklist now reports a complete delivery loop.
  await page.goto("/ui/#/dashboard");
  await expect(page.locator(".onboard.complete")).toBeVisible(
    { timeout: 15000 });
});

test("wave O: asset lists paginate and search on the server",
     async ({ page }) => {
  test.setTimeout(120000);
  await login(page);
  await page.goto("/ui/#/pipelines");
  await expect(page.locator(".el-table__body tbody tr").first())
    .toBeVisible({ timeout: 15000 });
  const search = page.getByPlaceholder("搜索管道名称或 Key");
  await search.fill("示例");
  await search.press("Enter");
  await page.waitForTimeout(800);
  const rows = page.locator(".el-table__body tbody tr");
  await expect(rows.first()).toBeVisible({ timeout: 10000 });
  const text = await rows.first().innerText();
  expect(text).toContain("示例");
});

test("wave O: a dataset editor opens with draft safety controls",
     async ({ page }) => {
  test.setTimeout(120000);
  await login(page);
  await page.goto("/ui/#/datasets");
  await page.locator(".el-table__body tbody tr").first()
    .getByRole("button", { name: "编辑" }).click();
  await expect(page).toHaveURL(/datasets\/\d+/, { timeout: 10000 });
  await page.waitForTimeout(1200);
  // The editor exposes save and lineage controls without a render failure.
  await expect(page.getByRole("button", { name: "保存" })).toBeVisible();
  await expect(page.getByRole("button", { name: "血缘" })).toBeVisible();
  await expect(page.locator(".render-error")).toHaveCount(0);
});

test("wave O: workbench saves queries and dashboards export CSV",
     async ({ page }) => {
  test.setTimeout(180000);
  await login(page);
  await page.goto("/ui/#/workbench");
  await page.getByRole("button", { name: "保存查询", exact: true }).click();
  const prompt = page.locator(".el-message-box:visible");
  await prompt.locator("input").fill(`UI Saved ${Date.now().toString(36)}`);
  await prompt.getByRole("button", { name: "确定" }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 10000 });
  await page.getByRole("button", { name: "已保存查询" }).click();
  const drawer = page.locator(".el-drawer:visible");
  await expect(drawer).toContainText("UI Saved", { timeout: 10000 });
  await drawer.locator(".saved-main").first().click();
  await expect(drawer).toBeHidden();

  await page.goto("/ui/#/dashboards");
  await page.locator(".el-table__body tbody tr").first()
    .getByRole("button", { name: "运行" }).click();
  await expect(page.locator(".run-page")).toBeVisible({ timeout: 15000 });
  const download = page.waitForEvent("download", { timeout: 20000 });
  await page.getByRole("button", { name: "导出 CSV" }).click();
  const file = await download;
  expect(file.suggestedFilename()).toContain("dashboard-");
});
