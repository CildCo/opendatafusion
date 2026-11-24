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

async function pickDatasource(page, name = "orders sqlite") {
  await page.locator(".form .el-form-item").filter({ hasText: "数据源" })
    .locator(".el-select").click();
  const dropdown = page.locator(".el-select-dropdown:visible").last();
  await expect(dropdown).toBeVisible({ timeout: 10000 });
  await dropdown.locator(".el-select-dropdown__item")
    .filter({ hasText: name }).first().click({ force: true });
  await page.waitForTimeout(200);
}

async function typeSql(page, sql) {
  const editor = page.locator(".cm-content").first();
  await editor.click();
  await page.keyboard.press("Control+A");
  await page.keyboard.type(sql);
}

async function newModel(page, name) {
  await page.goto("/ui/#/models");
  await page.getByRole("button", { name: "新建转换模型" }).click();
  const prompt = page.locator(".el-message-box:visible");
  await prompt.locator("input").fill(name);
  await prompt.getByRole("button", { name: "确定" }).click();
  await expect(page).toHaveURL(/models\/\d+/, { timeout: 15000 });
  await pickDatasource(page);
}

async function targetText(page) {
  return (await page.locator(".head .mono").first().innerText()).trim();
}

test("wave W1: contract freshness", async ({ page }) => {
  test.setTimeout(90000);
  await login(page);
  await page.goto("/ui/#/governance");
  await page.getByRole("tab", { name: "数据契约" }).click();
  const row = page.locator("tr", { hasText: "orders dataset" }).first();
  await row.getByRole("button", { name: "新鲜度" }).click();
  const dialog = page.locator(".el-dialog:visible");
  await dialog.locator(".el-form-item").filter({ hasText: "时间列" })
    .locator("input").fill("updated_at");
  await dialog.getByRole("button", { name: "保存" }).click();
  await expect(page.locator(".el-message--success").last())
    .toContainText("契约设置已更新", { timeout: 10000 });
  await row.getByRole("button", { name: "校验" }).click();
  const result = page.locator(".el-dialog:visible");
  await expect(result).toContainText("结构与契约不一致", { timeout: 15000 });
  await expect(result.locator(".el-table")).toContainText("stale");
  await expect(result.locator(".el-table")).toContainText("updated_at");
  await result.getByRole("button", { name: "关闭", exact: true }).click();
});

test("wave W2: infer columns from SQL and show lineage",
     async ({ page }) => {
  test.setTimeout(180000);
  await login(page);
  await newModel(page, `W base ${STAMP}`);
  await typeSql(page, "select city, sum(amount) as total from orders "
                      + "group by city");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 10000 });
  await page.getByRole("button", { name: "发布" }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 20000 });
  const target = await targetText(page);
  const key = (target.match(/model_[a-z0-9]+/) || [])[0];
  expect(key).toBeTruthy();

  await newModel(page, `W mart ${STAMP}`);
  await typeSql(page, `select city, total as revenue from {{ ref('${key}') }}`);
  await page.getByRole("button", { name: "从 SQL 推断" }).click();
  await expect(page.locator(".el-message--success").last())
    .toContainText("推断", { timeout: 15000 });
  await expect(page.locator(".col-row")).toHaveCount(2);
  const values = await page.locator(".col-row input").evaluateAll(
    (nodes) => nodes.map((node) => node.value));
  expect(values).toContain(`${key}.city`);
  expect(values).toContain(`${key}.total`);
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 10000 });
  await page.getByRole("button", { name: "发布" }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 20000 });
  await page.getByRole("button", { name: "血缘", exact: true }).click();
  const drawer = page.locator(".el-drawer:visible")
    .filter({ hasText: "资产血缘" });
  await expect(drawer).toContainText("字段级血缘", { timeout: 15000 });
  await expect(drawer.locator(".el-table__row")).toHaveCount(2);
});

test("wave W3: failed tests keep the previous table", async ({ page }) => {
  test.setTimeout(240000);
  await login(page);
  await newModel(page, `W atomic ${STAMP}`);
  await typeSql(page, "select city, sum(amount) as total from orders "
                      + "group by city");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 10000 });
  await page.getByRole("button", { name: "发布" }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 20000 });
  const target = await targetText(page);
  await page.getByRole("button", { name: "运行", exact: true }).click();
  await expect(page.locator(".el-message--success").last())
    .toContainText("运行任务", { timeout: 15000 });

  await page.goto("/ui/#/ops");
  await page.getByRole("tab", { name: "任务" }).click();
  const jobs = page.locator("table").first();
  await expect.poll(async () => {
    await page.getByRole("button", { name: "刷新", exact: true }).click();
    return page.locator("tr", { hasText: `W atomic ${STAMP}` })
      .filter({ hasText: "success" }).count();
  }, { timeout: 90000 }).toBeGreaterThan(0);

  await page.goto("/ui/#/models");
  await page.locator("tr", { hasText: `W atomic ${STAMP}` }).first()
    .getByRole("button", { name: "编辑" }).click();
  await expect(page).toHaveURL(/models\/\d+/, { timeout: 15000 });
  await page.getByRole("button", { name: "预览", exact: true }).click();
  await expect(page.locator(".stats")).toContainText("2", { timeout: 20000 });
  await page.getByRole("button", { name: "+ 添加测试" }).click();
  const testRow = page.locator(".test-row").first();
  await testRow.locator(".el-select").first().click();
  await page.locator(".el-select-dropdown:visible")
    .locator(".el-select-dropdown__item")
    .filter({ hasText: "accepted_values" }).first().click();
  await testRow.locator(".el-select").nth(1).click();
  await page.locator(".el-select-dropdown:visible")
    .locator(".el-select-dropdown__item")
    .filter({ hasText: "city" }).first().click();
  await testRow.locator("input").last().fill("berlin");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 10000 });
  await page.getByRole("button", { name: "发布" }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 20000 });
  await page.getByRole("button", { name: "运行", exact: true }).click();

  await page.goto("/ui/#/ops");
  await page.getByRole("tab", { name: "任务" }).click();
  await expect.poll(async () => {
    await page.getByRole("button", { name: "刷新", exact: true }).click();
    return page.locator("tr", { hasText: `W atomic ${STAMP}` })
      .filter({ hasText: "failed" }).count();
  }, { timeout: 120000 }).toBeGreaterThan(0);

  await page.goto("/ui/#/workbench");
  await page.locator(".toolbar .el-select").first().click();
  const targetDropdown = page.locator(".el-select-dropdown:visible").last();
  await expect(targetDropdown).toBeVisible({ timeout: 10000 });
  await targetDropdown.locator(".el-select-dropdown__item")
    .filter({ hasText: "orders sqlite" }).first().click({ force: true });
  await page.waitForTimeout(250);
  await typeSql(page, `select * from ${target}`);
  await page.getByRole("button", { name: "执行", exact: true }).click();
  await expect(page.locator(".result-head")).toContainText("2", {
    timeout: 20000,
  });
});

test("wave W4: performance templates and users", async ({ page }) => {
  test.setTimeout(90000);
  await login(page);
  await page.goto("/ui/#/workbench");
  await page.locator(".toolbar .el-select").first().click();
  const sourceDropdown = page.locator(".el-select-dropdown:visible").last();
  await expect(sourceDropdown).toBeVisible({ timeout: 10000 });
  await sourceDropdown.locator(".el-select-dropdown__item")
    .filter({ hasText: "orders sqlite" }).first().click({ force: true });
  await page.waitForTimeout(250);
  await typeSql(page, "select * from orders");
  await page.getByRole("button", { name: "执行", exact: true }).click();
  await expect(page.locator(".result-head")).toContainText("3", {
    timeout: 20000,
  });
  await page.goto("/ui/#/ops");
  await page.getByRole("tab", { name: "查询性能" }).click();
  await expect(page.locator(".section-title").filter({ hasText: "语句模板" }))
    .toBeVisible({ timeout: 15000 });
  await expect(page.locator(".section-title").filter({ hasText: "按用户" }))
    .toBeVisible();
  await expect(page.locator("table").filter({ hasText: "select" }).first())
    .toBeVisible({ timeout: 15000 });
});
