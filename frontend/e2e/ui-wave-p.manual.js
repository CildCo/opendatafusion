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

function field(dialog, label) {
  return dialog.locator(".el-form-item").filter({ hasText: label });
}

test("wave P: domains and glossary are created from the console",
     async ({ page }) => {
  test.setTimeout(180000);
  await login(page);
  await page.goto("/ui/#/governance");
  const domainName = `UI Domain ${STAMP}`;
  await page.getByRole("button", { name: "新建业务域" }).click();
  const dd = page.locator(".el-dialog:visible");
  await field(dd, "名称").locator("input").fill(domainName);
  await field(dd, "负责人").locator("input").fill("alice");
  await field(dd, "说明").locator("textarea").fill("UI governance domain");
  await dd.getByRole("button", { name: "保存" }).click();
  await expect(page.locator("tr", { hasText: domainName }))
    .toBeVisible({ timeout: 10000 });

  await page.getByRole("tab", { name: "术语表" }).click();
  const termName = `UI Term ${STAMP}`;
  await page.getByRole("button", { name: "新建术语" }).click();
  const td = page.locator(".el-dialog:visible");
  await field(td, "术语").locator("input").fill(termName);
  await field(td, "业务域").locator(".el-select").click();
  await page.locator(".el-select-dropdown__item:visible")
    .filter({ hasText: domainName }).first().click();
  await field(td, "定义").locator("textarea").fill("UI term definition");
  await td.getByRole("button", { name: "保存" }).click();
  await expect(page.locator("tr", { hasText: termName }))
    .toBeVisible({ timeout: 10000 });

  // Clean up the term and domain created by this wave.
  const termRow = page.locator("tr", { hasText: termName });
  await termRow.getByRole("button", { name: "删除" }).click();
  await page.locator(".el-message-box").getByRole("button", { name: "确定" })
    .click();
  await page.getByRole("tab", { name: "业务域" }).click();
  const domainRow = page.locator("tr", { hasText: domainName });
  await domainRow.getByRole("button", { name: "删除" }).click();
  await page.locator(".el-message-box").getByRole("button", { name: "确定" })
    .click();
  await expect(page.locator("tr", { hasText: domainName })).toHaveCount(0,
    { timeout: 10000 });
});

test("wave P: a SQL dataset previews rows and carries governance",
     async ({ page }) => {
  test.setTimeout(240000);
  await login(page);
  await page.goto("/ui/#/datasets");
  const name = `UI SQL ${STAMP}`;
  await page.getByRole("button", { name: "新建逻辑数据集" }).click();
  const prompt = page.locator(".el-message-box:visible");
  await prompt.locator("input").fill(name);
  await prompt.getByRole("button", { name: "确定" }).click();
  await expect(page).toHaveURL(/datasets\/\d+/, { timeout: 15000 });
  await page.locator(".el-radio-button", { hasText: "SQL" }).click();
  const bar = page.locator(".sql-bar");
  await bar.locator(".el-select").click();
  await page.locator(".el-select-dropdown__item:visible")
    .filter({ hasText: "pg-demo" }).first().click();
  const editor = page.locator(".cm-content").first();
  await editor.fill("select * from demo_src");
  await page.getByRole("button", { name: "保存" }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 15000 });
  await page.getByRole("button", { name: "校验" }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 15000 });
  await page.getByRole("button", { name: "预览" }).click();
  await expect(page.locator(".el-table__body tbody tr").first())
    .toBeVisible({ timeout: 20000 });

  // Governance drawer on a logical asset.
  await page.getByRole("button", { name: "治理" }).click();
  const drawer = page.locator(".el-drawer:visible");
  await expect(drawer).toContainText("资产治理", { timeout: 10000 });
  await drawer.locator(".el-form-item").filter({ hasText: "数据负责人" })
    .locator("input").fill("alice");
  await drawer.getByRole("button", { name: "保存治理信息" }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 10000 });
  await drawer.locator(".el-drawer__close-btn").click();

  // Remove the test dataset.
  await page.goto("/ui/#/datasets");
  const row = page.locator("tr", { hasText: name });
  await row.getByRole("button", { name: "删除" }).click();
  await page.locator(".el-message-box").getByRole("button", { name: "确定" })
    .click();
  await expect(page.locator("tr", { hasText: name })).toHaveCount(0,
    { timeout: 10000 });
});
