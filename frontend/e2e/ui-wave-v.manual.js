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

async function typeSql(page, sql) {
  const editor = page.locator(".cm-content").first();
  await editor.click();
  await page.keyboard.press("Control+A");
  await page.keyboard.type(sql);
}

async function pickOption(page, root, label, option) {
  await root.locator(".el-form-item").filter({ hasText: label })
    .locator(".el-select").click();
  const dropdown = page.locator(".el-select-dropdown:visible").last();
  await expect(dropdown).toBeVisible({ timeout: 10000 });
  await dropdown.locator(".el-select-dropdown__item")
    .filter({ hasText: option }).first().click({ force: true });
  await page.waitForTimeout(250);
}

test("wave V1: workbench history and execution plan", async ({ page }) => {
  test.setTimeout(120000);
  await login(page);
  await page.goto("/ui/#/workbench");
  await page.locator(".toolbar .el-select").first().click();
  const sourceDropdown = page.locator(".el-select-dropdown:visible").last();
  await expect(sourceDropdown).toBeVisible({ timeout: 10000 });
  await sourceDropdown.locator(".el-select-dropdown__item")
    .filter({ hasText: "orders sqlite" }).first().click({ force: true });
  await page.waitForTimeout(250);
  await typeSql(page, "select city, sum(amount) as total from orders "
                      + "group by city");
  await page.getByRole("button", { name: "执行", exact: true }).click();
  await expect(page.locator(".result-head")).toContainText("2", {
    timeout: 20000,
  });

  await page.getByRole("button", { name: "查询历史" }).click();
  await expect(page.locator(".hist-row").first()).toBeVisible({
    timeout: 10000,
  });
  await page.locator(".hist-row").first().click();
  await expect(page.locator(".el-drawer:visible")).toHaveCount(0,
    { timeout: 10000 });
  await expect(page.locator(".cm-content").first())
    .toContainText("group by", { timeout: 10000 });

  await page.getByRole("button", { name: "执行计划" }).click();
  await expect(page.locator(".el-dialog:visible .el-table__row").first())
    .toBeVisible({ timeout: 20000 });
  await page.locator(".el-dialog:visible")
    .getByRole("button", { name: "关闭", exact: true }).click();
});

test("wave V2: query performance console", async ({ page }) => {
  test.setTimeout(60000);
  await login(page);
  await page.goto("/ui/#/ops");
  await page.getByRole("tab", { name: "查询性能" }).click();
  await expect(page.locator(".perf-cards")).toContainText("查询次数", {
    timeout: 15000,
  });
  await expect(page.locator(".perf-cards")).not.toContainText("0\n查询次数");
  await expect(page.locator(".section-title").filter({ hasText: "最慢查询" }))
    .toBeVisible();
  await expect(page.locator("table", { hasText: "workbench" }).first())
    .toBeVisible({ timeout: 15000 });
});

test("wave V3: model template, columns, publish and run",
     async ({ page }) => {
  test.setTimeout(180000);
  await login(page);
  await page.goto("/ui/#/models");
  await page.getByRole("button", { name: "模板" }).click();
  const dialog = page.locator(".el-dialog:visible");
  await dialog.locator(".tpl-card")
    .filter({ hasText: "标准 staging 模型" }).click();
  const form = dialog.locator(".tpl-form");
  await pickOption(page, form, "数据源", "orders sqlite");
  await form.locator(".el-form-item").filter({ hasText: "源表" })
    .locator("input").fill("orders");
  await dialog.getByRole("button", { name: "创建草稿" }).click();
  await expect(page).toHaveURL(/models\/\d+/, { timeout: 20000 });

  await page.getByRole("button", { name: "预览", exact: true }).click();
  await expect(page.locator(".stats")).toContainText("3", { timeout: 20000 });
  await page.getByRole("button", { name: "从预览填充" }).click();
  await expect(page.locator(".col-row")).toHaveCount(3);
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 10000 });
  await page.getByRole("button", { name: "校验", exact: true }).click();
  await expect(page.locator(".el-message--success").last())
    .toContainText("校验", { timeout: 10000 });
  await page.getByRole("button", { name: "发布" }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 20000 });
  await page.getByRole("button", { name: "运行", exact: true }).click();
  await expect(page.locator(".el-message--success").last())
    .toContainText("运行任务", { timeout: 15000 });
  await page.getByRole("button", { name: "血缘", exact: true }).click();
  await expect(page.locator(".el-drawer:visible")
    .filter({ hasText: "资产血缘" })).toBeVisible({ timeout: 10000 });
  await page.keyboard.press("Escape");
});

test("wave V4: data contract check and enforcement",
     async ({ page }) => {
  test.setTimeout(90000);
  await login(page);
  await page.goto("/ui/#/governance");
  await page.getByRole("tab", { name: "数据契约" }).click();
  const row = page.locator("tr", { hasText: "orders dataset" }).first();
  await expect(row).toContainText("3", { timeout: 15000 });
  await row.getByRole("button", { name: "校验" }).click();
  const dialog = page.locator(".el-dialog:visible");
  await expect(dialog).toContainText("结构与契约一致", { timeout: 15000 });
  await dialog.getByRole("button", { name: "关闭", exact: true }).click();
  await expect(page.locator(".el-dialog:visible")).toHaveCount(0,
    { timeout: 10000 });
  await row.locator(".el-switch").first().click();
  await expect(page.locator(".el-message--success").last())
    .toContainText("契约设置已更新", { timeout: 10000 });
});

test("wave V5: generate a pipeline from a CDC source",
     async ({ page }) => {
  test.setTimeout(90000);
  await login(page);
  await page.goto("/ui/#/cdc");
  const row = page.locator("tr", { hasText: "shop cdc" }).first();
  await row.getByRole("button", { name: "生成管道" }).click();
  const dialog = page.locator(".el-dialog:visible");
  await pickOption(page, dialog, "Kafka 数据源", "stream kafka");
  await pickOption(page, dialog, "目标数据源", "orders sqlite");
  await dialog.getByRole("button", { name: "创建管道" }).click();
  await expect(page).toHaveURL(/pipelines\/\d+/, { timeout: 20000 });
  await expect(page.locator("body")).toContainText(
    "CDC public.orders_copy", { timeout: 20000 });
});

test("wave V6: create a pipeline from a template", async ({ page }) => {
  test.setTimeout(90000);
  await login(page);
  await page.goto("/ui/#/pipelines");
  await page.getByRole("button", { name: "模板" }).click();
  const dialog = page.locator(".el-dialog:visible");
  await dialog.locator(".tpl-card")
    .filter({ hasText: "表同步管道" }).click();
  const form = dialog.locator(".tpl-form");
  await pickOption(page, form, "源数据源", "orders sqlite");
  await form.locator(".el-form-item").filter({ hasText: "源表" })
    .locator("input").fill("orders");
  await pickOption(page, form, "目标数据源", "orders sqlite");
  await form.locator(".el-form-item").filter({ hasText: "目标表" })
    .locator("input").fill("orders_copy");
  await dialog.getByRole("button", { name: "创建草稿" }).click();
  await expect(page).toHaveURL(/pipelines\/\d+/, { timeout: 20000 });
});

test("wave V7: model column lineage", async ({ page }) => {
  test.setTimeout(60000);
  await login(page);
  await page.goto("/ui/#/models");
  await page.locator("tr", { hasText: "city revenue" }).first()
    .getByRole("button", { name: "编辑" }).click();
  await expect(page).toHaveURL(/models\/\d+/, { timeout: 15000 });
  await page.getByRole("button", { name: "血缘", exact: true }).click();
  const drawer = page.locator(".el-drawer:visible")
    .filter({ hasText: "资产血缘" });
  await expect(drawer).toContainText("字段级血缘", { timeout: 15000 });
  await expect(drawer.locator(".el-table__row")).toHaveCount(2);
  await expect(drawer).toContainText("total");
});
