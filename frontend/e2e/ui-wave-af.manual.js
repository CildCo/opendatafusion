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

test("wave AF1: workbench tabs, schema insert, format and inspector",
     async ({ page }) => {
  test.setTimeout(180000);
  await login(page);
  await page.goto("/ui/#/workbench");
  await expect(page.getByText("查询 1", { exact: true })).toBeVisible({
    timeout: 15000,
  });
  await page.getByRole("button", { name: "+ 新建查询" }).click();
  await expect(page.getByText("查询 2", { exact: true })).toBeVisible();

  const city = page.locator(".schema-panel .el-tree-node__content")
    .filter({ hasText: "city" }).first();
  await expect(city).toBeVisible({ timeout: 15000 });
  await city.click();

  const editor = page.locator(".cm-content").first();
  await editor.click();
  await page.keyboard.press("Control+A");
  await page.keyboard.type("select city,sum(amount) from events group by city");
  await page.getByRole("button", { name: "格式化" }).click();
  await expect(editor).toContainText("SELECT", { timeout: 15000 });

  await page.getByRole("button", { name: "执行", exact: true }).click();
  await expect(page.locator(".result")).toContainText("shanghai", {
    timeout: 20000,
  });
  await page.locator(".result-head .el-radio-button__inner")
    .filter({ hasText: "统计" }).click();
  await expect(page.locator(".result")).toContainText("行数");
  await expect(page.locator(".result")).toContainText("verify sqlite");
  await page.locator(".result-head .el-radio-button__inner")
    .filter({ hasText: "请求" }).click();
  await expect(page.locator(".inspector-pre")).toContainText("SELECT");
  await page.locator(".result-head .el-radio-button__inner")
    .filter({ hasText: "JSON" }).click();
  await expect(page.locator(".inspector-pre")).toContainText("shanghai");
});

test("wave AF2: dashboard style, click behavior and URL filters",
     async ({ page }) => {
  test.setTimeout(180000);
  await login(page);
  await page.goto("/ui/#/dashboards");
  await page.locator("tr", { hasText: "format dashboard" }).first()
    .getByRole("button", { name: "编辑" }).click();
  await expect(page).toHaveURL(/dashboards\/\d+/, { timeout: 15000 });
  const id = page.url().match(/dashboards\/(\d+)/)[1];

  const line = page.locator(".widget").filter({ hasText: "Sales trend" })
    .first();
  await line.click();
  await expect(page.locator(".config")).toContainText("图表样式");
  await expect(page.locator(".config")).toContainText("配色");
  const palette = page.locator(".config .el-form-item")
    .filter({ hasText: "配色" }).locator(".el-select").first();
  await palette.click();
  await page.getByRole("option", { name: "绿色" }).click();

  const table = page.locator(".widget").filter({ hasText: "Orders" }).first();
  await table.click();
  await expect(page.locator(".config")).toContainText("点击行为");
  await expect(page.locator(".config input[placeholder*='站内路径']"))
    .toHaveValue("/dashboards");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.locator(".el-message").last())
    .toContainText("已保存草稿", { timeout: 15000 });

  await page.goto(`/ui/#/dashboards/${id}/run`);
  const filter = page.locator(".param-bar input").first();
  await expect(filter).toBeVisible({ timeout: 15000 });
  await filter.fill("beijing");
  await page.getByRole("button", { name: "查询" }).click();
  await expect(page).toHaveURL(/city=beijing/, { timeout: 15000 });
  await page.getByRole("button", { name: "重置" }).click();
  await expect(page).not.toHaveURL(/city=beijing/, { timeout: 15000 });

  const row = page.locator(".widget").filter({ hasText: "Orders" })
    .locator(".el-table__row").first();
  await expect(row).toBeVisible({ timeout: 15000 });
  await row.click();
  await expect(page).toHaveURL(/dashboards$/, { timeout: 15000 });
});
