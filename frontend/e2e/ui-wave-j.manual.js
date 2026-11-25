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

async function choose(select, optionText) {
  const page = select.page();
  await select.click();
  await page.waitForTimeout(250);
  await page.locator(".el-select-dropdown__item:visible")
    .filter({ hasText: optionText }).first().click({ timeout: 8000 });
  await page.waitForTimeout(300);
}

test("wave J: quality actions leave a trace in the audit log",
     async ({ page }) => {
  test.setTimeout(240000);
  await login(page);

  const name = `UI Trace ${STAMP}`;
  await page.goto("/ui/#/quality");
  for (let index = 0; index < 10; index += 1) {
    const stale = page.locator("tr", { hasText: "UI Trace " }).first();
    if (!(await stale.count())) break;
    await stale.getByRole("button", { name: "删除" }).click();
    await page.locator(".el-message-box")
      .getByRole("button", { name: "确定" }).click();
    await page.waitForTimeout(800);
  }
  await page.getByRole("button", { name: "新建规则" }).first().click();
  const dialog = page.locator(".el-dialog:visible");
  const items = dialog.locator(".el-form-item");
  await items.nth(0).locator("input").fill(name);
  await choose(items.nth(1).locator(".el-select"), "demo_src");
  await choose(items.nth(2).locator(".el-select"), "非空");
  await choose(items.nth(3).locator(".el-select"), "id");
  await dialog.getByRole("button", { name: "保存" }).click();
  await expect(page.locator(".el-message--success")
    .filter({ hasText: "已创建" })).toBeVisible({ timeout: 10000 });

  const row = page.locator("tr", { hasText: name });
  await expect(row).toBeVisible();
  await row.getByRole("button", { name: "执行", exact: true }).click();
  await expect(page.locator(".el-message")
    .filter({ hasText: /校验通过|校验失败/ }).first())
    .toBeVisible({ timeout: 30000 });

  await page.goto("/ui/#/admin/audit");
  await page.getByRole("textbox", { name: "按动作过滤" }).fill(
    "quality_rule");
  await page.getByRole("button", { name: "查询" }).click();
  await page.waitForTimeout(1200);

  const auditRows = page.locator(".el-table-v2__row");
  await expect(auditRows.first()).toBeVisible({ timeout: 10000 });
  const tableText = await auditRows.first().innerText();
  expect(tableText).toContain("quality_rule");
  await auditRows.first().click();
  const drawer = page.locator(".el-drawer:visible");
  await expect(drawer).toBeVisible({ timeout: 10000 });
  const detail = await drawer.innerText();
  expect(detail).toContain("quality_rule");
  expect(detail).toMatch(/run_quality_rule|create_quality_rule/);
  await drawer.locator(".el-drawer__close-btn").click();

  await page.goto("/ui/#/quality");
  const rule = page.locator("tr", { hasText: name });
  await rule.getByRole("button", { name: "删除" }).click();
  await page.locator(".el-message-box")
    .getByRole("button", { name: "确定" }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 10000 });
});
