import { expect, test } from "@playwright/test";

const STAMP = Date.now().toString(36).slice(-5);

async function login(page, user = "admin", password = "AdminPassw0rd!",
                     project = 1) {
  await page.addInitScript(() => localStorage.setItem("odf_locale", "zh"));
  await page.evaluate(() => localStorage.clear()).catch(() => {});
  await page.goto("/ui/#/login");
  await page.locator(".el-form-item").filter({ hasText: "用户名" })
    .locator("input").fill(user);
  await page.locator(".el-form-item").filter({ hasText: "密码" })
    .locator("input").fill(password);
  await page.locator(".el-form-item").filter({ hasText: "项目" })
    .locator("input").fill(String(project));
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page).toHaveURL(/dashboard/, { timeout: 15000 });
}

async function pickOption(page, root, label, option) {
  await root.locator(".el-form-item").filter({ hasText: label })
    .locator(".el-select").click();
  const dropdown = page.locator(".el-select-dropdown:visible").last();
  await expect(dropdown).toBeVisible({ timeout: 10000 });
  await dropdown.locator(".el-select-dropdown__item")
    .filter({ hasText: option }).first().click({ force: true });
  await page.waitForTimeout(200);
}

test("wave Y1: request, approve and preview a shared dataset",
     async ({ page }) => {
  test.setTimeout(180000);
  await login(page, "viewer", "ViewerPassw0rd!", 2);
  await page.goto("/ui/#/grants");
  const catalogRow = page.locator("tr", { hasText: "orders dataset" })
    .first();
  await expect(catalogRow).toContainText("数据集", { timeout: 15000 });
  await catalogRow.getByRole("button", { name: "申请访问" }).click();
  const request = page.locator(".el-dialog:visible");
  await request.locator("textarea").fill("need orders data");
  await request.getByRole("button", { name: "提交申请" }).click();
  await expect(page.locator(".el-message--success").last())
    .toContainText("申请", { timeout: 10000 });

  await page.evaluate(() => localStorage.clear());
  await login(page, "admin", "AdminPassw0rd!", 1);
  await page.goto("/ui/#/grants");
  await page.getByRole("tab", { name: "待审批" }).click();
  const incoming = page.locator(".el-tab-pane:visible tr",
                                { hasText: "orders dataset" }).first();
  await expect(incoming).toContainText("Marketing", { timeout: 15000 });
  await incoming.getByRole("button", { name: "通过" }).click();
  const confirm = page.locator(".el-message-box:visible");
  await confirm.getByRole("button", { name: "确定" }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 10000 });

  await page.evaluate(() => localStorage.clear());
  await login(page, "viewer", "ViewerPassw0rd!", 2);
  await page.goto("/ui/#/grants");
  await page.getByRole("tab", { name: "共享给我" }).click();
  const shared = page.locator(".el-tab-pane:visible tr",
                              { hasText: "orders dataset" }).first();
  await expect(shared).toContainText("Warehouse", { timeout: 15000 });
  await shared.getByRole("button", { name: "预览" }).click();
  const preview = page.locator(".el-dialog:visible");
  await expect(preview).toContainText("berlin", { timeout: 15000 });
  await preview.getByRole("button", { name: "关闭", exact: true }).click();
});

test("wave Y2: quality SLA and daily trend", async ({ page }) => {
  test.setTimeout(90000);
  await login(page);
  await page.goto("/ui/#/quality");
  const row = page.locator("tr", { hasText: "orders city not null" })
    .first();
  await expect(row).toContainText("%", { timeout: 15000 });
  await expect(row).toContainText("低于 SLA");
  await row.getByRole("button", { name: "调度" }).click();
  const dialog = page.locator(".el-dialog:visible");
  await dialog.locator(".el-input-number input").fill("80");
  await dialog.getByRole("button", { name: "保存" }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 10000 });
  await row.getByRole("button", { name: "结果" }).click();
  const drawer = page.locator(".el-drawer:visible")
    .filter({ hasText: "orders city not null" });
  await expect(drawer.locator(".trend-block")).toBeVisible({
    timeout: 15000,
  });
  await expect(drawer.locator(".trend-block .el-table__row"))
    .toHaveCount(2);
});

test("wave Y3: partition replace strategy is available",
     async ({ page }) => {
  test.setTimeout(60000);
  await login(page);
  await page.goto("/ui/#/models");
  await page.locator("tr", { hasText: "partition model" }).first()
    .getByRole("button", { name: "编辑" }).click();
  await expect(page).toHaveURL(/models\/\d+/, { timeout: 15000 });
  const form = page.locator(".form");
  await expect(form.locator(".el-form-item").filter({ hasText: "增量策略" })
    .locator(".el-select")).toContainText("按键分区替换", {
      timeout: 15000,
    });
  await expect(form.locator(".el-form-item").filter({ hasText: "分区列" }))
    .toBeVisible();
});
