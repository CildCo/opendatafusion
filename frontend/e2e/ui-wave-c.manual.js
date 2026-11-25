import fs from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";

// Wave C: asset surfaces driven only through the console.
// Datasource create/test/sync/delete, file upload/download/delete,
// workbench query, catalog search and dataset detail tabs with tags.

const USER = process.env.ODF_SWEEP_USER || "admin";
const PASS = process.env.ODF_SWEEP_PASSWORD || "";
const STAMP = `ui${Date.now().toString(36)}`;

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

async function pick(page, selectLabel, optionText) {
  await page.locator(".el-form-item").filter({ hasText: selectLabel })
    .locator(".el-select").first().click();
  const dropdown = page.locator(".el-select-dropdown:visible").last();
  await dropdown.waitFor({ state: "visible", timeout: 5000 });
  await dropdown.locator(".el-select-dropdown__item")
    .filter({ hasText: optionText }).first().click();
}

test("wave C: datasource lifecycle", async ({ page }) => {
  test.setTimeout(120000);
  await login(page);
  await page.goto("/ui/#/datasources");
  for (let guard = 0; guard < 10; guard += 1) {
    const stale = page.locator("tr", { hasText: "UI Source " }).first();
    if (!(await stale.count())) break;
    await stale.getByRole("button", { name: "删除" }).click();
    await page.locator(".el-message-box").getByRole("button", { name: "确定" })
      .click();
    await page.waitForTimeout(600);
    if (await page.locator(".el-message-box").count()) {
      await page.locator(".el-message-box").getByRole(
        "button", { name: "确定" }).click();
    }
    await page.waitForTimeout(400);
  }
  const name = `UI Source ${STAMP}`;
  await page.getByRole("button", { name: "新建数据源" }).click();
  const dialog = page.locator(".el-dialog:visible");
  await dialog.locator(".el-form-item").filter({ hasText: "名称" })
    .locator("input").fill(name);
  await pick(page, "类型", "SQLite");
  await dialog.locator(".el-form-item").filter({ hasText: "文件路径" })
    .locator("input").fill(`sqlite:////tmp/${STAMP}.db`);
  await dialog.getByRole("button", { name: "测试连接" }).click();
  await expect(dialog.locator(".el-tag").filter({ hasText: "连接正常" }))
    .toBeVisible({ timeout: 15000 });
  await dialog.getByRole("button", { name: "保存" }).click();
  await expect(page.getByText(name)).toBeVisible({ timeout: 10000 });

  const row = page.locator("tr", { hasText: name });
  await row.getByRole("button", { name: "测试" }).click();
  await expect(page.locator(".el-message--success")
    .filter({ hasText: "连接正常" })).toBeVisible({ timeout: 15000 });
  await row.getByRole("button", { name: "同步元数据" }).click();
  await expect(page.locator(".el-message--success")
    .filter({ hasText: "已同步" })).toBeVisible({ timeout: 20000 });
  await row.getByRole("button", { name: "表", exact: true }).click();
  await expect(page.locator(".el-drawer:visible")).toContainText("表 ·",
    { timeout: 10000 });
  await page.locator(".el-drawer:visible .el-drawer__close-btn").click();

  await row.getByRole("button", { name: "删除" }).click();
  await page.locator(".el-message-box").getByRole("button", { name: "确定" })
    .click();
  await expect(page.locator("tr", { hasText: name })).toHaveCount(0,
    { timeout: 10000 });
});

test("wave C: file upload and delete", async ({ page }) => {
  test.setTimeout(120000);
  await login(page);
  await page.goto("/ui/#/files");
  const file = path.resolve("test-results", `ui-file-${STAMP}.csv`);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, "id,name\n1,alpha\n2,beta\n");
  await page.locator("input[type=file]").setInputFiles(file);
  await expect(page.getByText(`ui-file-${STAMP}.csv`))
    .toBeVisible({ timeout: 15000 });

  const row = page.locator("tr", { hasText: `ui-file-${STAMP}.csv` });
  await row.getByRole("button", { name: "删除" }).click();
  await page.locator(".el-message-box").getByRole("button", { name: "确定" })
    .click();
  await expect(page.getByText(`ui-file-${STAMP}.csv`)).toHaveCount(0,
    { timeout: 10000 });
});

test("wave C: workbench single query", async ({ page }) => {
  test.setTimeout(120000);
  await login(page);
  await page.goto("/ui/#/workbench");
  await page.locator(".el-select").first().click();
  await page.locator(".el-select-dropdown__item").first().click();
  const editor = page.locator(".cm-content").first();
  await editor.click();
  await page.keyboard.press("Control+A");
  await page.keyboard.type("select 1 as ui_check");
  await page.getByRole("button", { name: "执行", exact: true })
    .first().click();
  await expect(page.locator(".el-table:visible").first())
    .toContainText("ui_check", { timeout: 20000 });
});

test("wave C: catalog detail tabs, sample, profile and tags", async ({ page }) => {
  test.setTimeout(180000);
  await login(page);
  await page.goto("/ui/#/catalog");
  await page.getByPlaceholder("搜索表、字段或标签").fill("demo");
  const first = page.locator(".search-row").first();
  await expect(first).toBeVisible({ timeout: 15000 });
  await first.click();
  await expect(page).toHaveURL(/catalog\/\d+/, { timeout: 10000 });

  await page.getByRole("tab", { name: "数据预览" }).click();
  await page.getByRole("button", { name: "加载样例" }).click();
  await expect(page.locator(".el-table:visible").first()).toContainText(/\d/,
    { timeout: 20000 });

  await page.getByRole("tab", { name: "数据探查" }).click();
  await page.getByRole("button", { name: "生成探查" }).click();
  await expect(page.getByText(/采样|样本/).first()).toBeVisible(
    { timeout: 40000 });

  const tag = `ui-tag-${STAMP}`;
  await page.getByRole("tab", { name: "概览" }).click();
  await page.getByRole("button", { name: "打标签" }).click();
  await page.locator(".el-dialog:visible input").fill(tag);
  await page.locator(".el-dialog:visible").getByRole("button", { name: "保存" })
    .click();
  await expect(page.getByText(tag).first()).toBeVisible({ timeout: 10000 });
  await page.locator(`.el-tag:has-text("${tag}") .el-tag__close`).first().click();
  await expect(page.getByText(tag)).toHaveCount(0, { timeout: 10000 });

  for (const tab of ["质量规则", "依赖与影响", "操作历史"]) {
    await page.getByRole("tab", { name: tab }).click();
    await expect(page.locator(".el-tab-pane:visible")).not.toBeEmpty();
  }
});
