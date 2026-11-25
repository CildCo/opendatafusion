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

test("wave N: quick sync, health, quality schedule, governance and backup",
     async ({ page }) => {
  test.setTimeout(300000);
  await login(page);

  // Datasource health history
  await page.goto("/ui/#/datasources");
  const ds = page.locator("tr", { hasText: "pg-demo" });
  await ds.getByRole("button", { name: "测试" }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 20000 });
  await ds.getByRole("button", { name: "健康" }).click();
  const health = page.locator(".el-drawer:visible");
  await expect(health).toBeVisible();
  await expect(health.locator("tbody tr").first()).toBeVisible(
    { timeout: 10000 });
  await health.locator(".el-drawer__close-btn").click();

  // Quick sync creates a configured pipeline
  await page.getByRole("button", { name: "快速同步" }).click();
  const quick = page.locator(".el-dialog:visible");
  await expect(quick).toBeVisible();
  await quick.locator(".el-form-item").filter({ hasText: "任务名称" })
    .locator("input").fill(`UI Quick ${STAMP}`);
  await quick.locator(".el-form-item").filter({ hasText: "源数据源" })
    .locator(".el-select").click();
  await page.locator(".el-select-dropdown__item:visible")
    .filter({ hasText: "pg-demo" }).first().click();
  await page.waitForTimeout(800);
  await quick.locator(".el-form-item").filter({ hasText: "源表" })
    .locator(".el-select").click();
  await page.locator(".el-select-dropdown__item:visible")
    .filter({ hasText: "demo_src" }).first().click();
  await page.waitForTimeout(400);
  await quick.locator(".el-form-item").filter({ hasText: "目标数据源" })
    .locator(".el-select").click();
  await page.locator(".el-select-dropdown__item:visible")
    .filter({ hasText: "pg-demo" }).last().click();
  await page.waitForTimeout(800);
  await quick.locator(".el-form-item").filter({ hasText: "目标表" })
    .locator(".el-select").click();
  await page.locator(".el-select-dropdown__item:visible")
    .filter({ hasText: "demo_dst" }).first().click();
  await quick.getByRole("button", { name: "创建管道" }).click();
  await expect(page).toHaveURL(/pipelines\/\d+/, { timeout: 15000 });
  const pipelineId = (page.url().match(/pipelines\/(\d+)/) || [])[1];
  await page.waitForTimeout(1500);
  await expect(page.locator(".vue-flow__node")).toHaveCount(2,
    { timeout: 10000 });
  await page.goto("/ui/#/pipelines");
  await page.waitForTimeout(1000);
  const rows = page.locator(".el-table__body tbody tr");
  for (let i = 0; i < await rows.count(); i += 1) {
    const cells = await rows.nth(i).locator("td").allInnerTexts();
    if ((cells[1] || "").trim() === pipelineId) {
      await rows.nth(i).getByRole("button", { name: "删除" }).click();
      await page.locator(".el-message-box").getByRole("button",
        { name: "确定" }).click();
      await page.waitForTimeout(800);
      break;
    }
  }

  // Quality schedule and alert-on-failure
  const ruleName = `UI Sched ${STAMP}`;
  await page.goto("/ui/#/quality");
  await page.getByRole("button", { name: "新建规则" }).first().click();
  const qdlg = page.locator(".el-dialog:visible");
  const items = qdlg.locator(".el-form-item");
  await items.nth(0).locator("input").fill(ruleName);
  await items.nth(1).locator(".el-select").click();
  await page.locator(".el-select-dropdown__item:visible")
    .filter({ hasText: "demo_src" }).first().click();
  await page.waitForTimeout(400);
  await items.nth(2).locator(".el-select").click();
  await page.locator(".el-select-dropdown__item:visible")
    .filter({ hasText: "非空" }).first().click();
  await page.waitForTimeout(300);
  await items.nth(3).locator(".el-select").click();
  await page.locator(".el-select-dropdown__item:visible")
    .filter({ hasText: "id" }).first().click();
  await qdlg.getByPlaceholder("Cron，例如 0 2 * * *")
    .fill("0 2 * * *");
  await qdlg.locator(".el-form-item").filter({ hasText: "失败告警" })
    .locator(".el-switch").click();
  await qdlg.getByRole("button", { name: "保存" }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 10000 });
  const qrow = page.locator("tr", { hasText: ruleName });
  await expect(qrow).toContainText("0 2 * * *");
  await qrow.getByRole("button", { name: "删除" }).click();
  await page.locator(".el-message-box").getByRole("button",
    { name: "确定" }).click();
  await page.waitForTimeout(600);

  // PII scan from the catalog detail
  await page.goto("/ui/#/catalog");
  await page.getByPlaceholder("搜索表名").fill("demo");
  const hit = page.locator(".el-tag.hit").first();
  await expect(hit).toBeVisible({ timeout: 15000 });
  await hit.click();
  await expect(page).toHaveURL(/catalog\/\d+/, { timeout: 10000 });
  await page.getByRole("button", { name: "PII 扫描" }).click();
  await expect(page.locator(".el-dialog:visible"))
    .toContainText("敏感字段扫描", { timeout: 15000 });
  await page.locator(".el-dialog:visible").getByRole("button",
    { name: "取消" }).click();

  // Asset lineage in the studio editors
  for (const path of ["datasets", "apis", "dashboards", "metrics"]) {
    await page.goto(`/ui/#/${path}`);
    await page.waitForTimeout(800);
    const rows = page.locator(".el-table__body tbody tr");
    if (!(await rows.count())) continue;
    await rows.first().getByRole("button", { name: "编辑" }).click();
    await expect(page).toHaveURL(new RegExp(`${path}/\\d+`),
                                 { timeout: 10000 });
    await page.getByRole("button", { name: "血缘" }).click();
    const drawer = page.locator(".el-drawer:visible");
    await expect(drawer).toContainText("资产血缘", { timeout: 10000 });
    await drawer.locator(".el-drawer__close-btn").click();
    await page.waitForTimeout(300);
  }

  // Admin usage and runtime/backup
  await page.goto("/ui/#/admin/projects");
  await page.locator("tbody tr").first().getByRole("button",
    { name: "用量" }).click();
  await expect(page.locator(".el-drawer:visible")).toContainText("资产数",
    { timeout: 10000 });
  await page.locator(".el-drawer:visible .el-drawer__close-btn").click();

  await page.goto("/ui/#/admin/operations");
  await expect(page.locator(".admin-content")).toContainText("运行状态");
  await expect(page.locator(".admin-content")).toContainText("2.7.0");
  const download = page.waitForEvent("download", { timeout: 20000 });
  await page.getByRole("button", { name: "导出备份" }).click();
  const file = await download;
  expect(file.suggestedFilename()).toContain("odf-backup");

  await page.goto("/ui/#/admin/overview");
  await expect(page.locator(".admin-content")).toContainText("AI 工具调用");
});
