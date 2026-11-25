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

test("wave U: transform model editor and lakehouse page",
     async ({ page }) => {
  test.setTimeout(180000);
  await login(page);
  await page.goto("/ui/#/datasets");
  await page.getByRole("tab", { name: "转换模型" }).click();
  await page.getByRole("button", { name: "新建转换模型" }).click();
  const prompt = page.locator(".el-message-box:visible");
  await prompt.locator("input").fill(`UI model ${STAMP}`);
  await prompt.getByRole("button", { name: "确定" }).click();
  await expect(page).toHaveURL(/models\/\d+/, { timeout: 15000 });
  const form = page.locator(".form");
  await form.locator(".el-form-item").filter({ hasText: "数据源" })
    .locator(".el-select").click();
  await page.locator(".el-select-dropdown:visible")
    .locator(".el-select-dropdown__item")
    .filter({ hasText: "orders sqlite" }).first().click();
  const editor = page.locator(".cm-content").first();
  await editor.click();
  await page.keyboard.press("Control+A");
  await page.keyboard.type(
    "select city, sum(amount) as total from orders group by city");
  await form.locator(".el-form-item").filter({ hasText: "分层" })
    .locator(".el-select").click();
  await page.locator(".el-select-dropdown:visible")
    .locator(".el-select-dropdown__item")
    .filter({ hasText: "mart" }).first().click();
  await page.getByRole("button", { name: "预览" }).click();
  await expect(page.locator(".stats")).toContainText("2", { timeout: 20000 });
  await expect(page.locator(".mono").first()).toContainText("model_");

  await page.getByRole("button", { name: "+ 添加测试" }).click();
  const testRow = page.locator(".test-row").first();
  await testRow.locator(".el-select").nth(1).click();
  await page.locator(".el-select-dropdown:visible")
    .locator(".el-select-dropdown__item")
    .filter({ hasText: "total" }).first().click();
  await page.getByRole("button", { name: "保存" }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 10000 });
  await page.getByRole("button", { name: "校验" }).click();
  await expect(page.locator(".el-message--success").last())
    .toContainText("校验", { timeout: 10000 });
  await page.getByRole("button", { name: "发布" }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 20000 });
  await page.getByRole("button", { name: "运行" }).click();
  await expect(page.locator(".el-message--success").last())
    .toContainText("运行任务", { timeout: 15000 });

  await page.goto("/ui/#/models");
  const row = page.locator("tr", { hasText: `UI model ${STAMP}` });
  await expect(row).toContainText("已发布", { timeout: 15000 });
  await expect(row).toContainText("mart");

  await page.goto("/ui/#/lakehouse");
  await expect(page.locator(".page")).toContainText("湖仓表管理");
  await expect(page.locator(".page")).toContainText("暂无湖仓表");
});
