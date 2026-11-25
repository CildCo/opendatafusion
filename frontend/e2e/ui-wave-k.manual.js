import { expect, test } from "@playwright/test";

const USER = process.env.ODF_SWEEP_USER || "admin";
const PASS = process.env.ODF_SWEEP_PASSWORD || "";
const STAMP = Date.now().toString(36).slice(-5);
const PASSWORD = "RolePassw0rd!";
const ADMIN = `ui_projadmin_${STAMP}`;
const TARGET = `ui_projtarget_${STAMP}`;

async function login(page, username = USER, password = PASS) {
  await page.addInitScript(() => localStorage.setItem("odf_locale", "zh"));
  await page.goto("/ui/#/login");
  await page.locator(".el-form-item").filter({ hasText: "用户名" })
    .locator("input").fill(username);
  await page.locator(".el-form-item").filter({ hasText: "密码" })
    .locator("input").fill(password);
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page).toHaveURL(/dashboard/, { timeout: 20000 });
}

async function choose(page, select, text) {
  await select.click();
  await page.waitForTimeout(250);
  await page.locator(".el-select-dropdown__item:visible")
    .filter({ hasText: text }).first().click();
  await page.waitForTimeout(300);
}

test("wave K: a project administrator manages their own members",
     async ({ page, browser }) => {
  test.setTimeout(300000);
  await login(page);

  await page.goto("/ui/#/admin/users");
  for (const name of [ADMIN, TARGET]) {
    await page.getByRole("button", { name: "新建用户" }).first().click();
    const dialog = page.locator(".el-dialog:visible");
    const items = dialog.locator(".el-form-item");
    await items.nth(0).locator("input").fill(name);
    await items.nth(1).locator("input").fill(PASSWORD);
    await dialog.getByRole("button", { name: "保存" }).click();
    await expect(page.locator(".el-message--success").last())
      .toBeVisible({ timeout: 10000 });
  }

  await page.getByRole("button", { name: "项目成员" }).first().click();
  const drawer = page.locator(".el-drawer:visible");
  await drawer.locator(".member-add .el-select").nth(0).click();
  await page.locator(".el-select-dropdown__item:visible")
    .filter({ hasText: ADMIN }).first().click();
  await page.waitForTimeout(300);
  await drawer.locator(".member-add .el-select").nth(1).click();
  await page.locator(".el-select-dropdown__item:visible")
    .filter({ hasText: "admin" }).last().click();
  await page.waitForTimeout(300);
  await drawer.getByRole("button", { name: "添加", exact: true }).click();
  await expect(drawer.locator("tr", { hasText: ADMIN }))
    .toBeVisible({ timeout: 10000 });
  await page.keyboard.press("Escape");

  const context = await browser.newContext();
  const view = await context.newPage();
  await login(view, ADMIN, PASSWORD);
  await view.waitForTimeout(800);
  const nav = await view.locator(".rail-nav").innerText();
  const foot = await view.locator(".rail-foot").innerText();
  expect(nav).not.toContain("系统管理");
  expect(foot).toContain("项目成员");
  await view.locator(".rail-admin").filter({ hasText: "项目成员" }).click();
  await expect(view).toHaveURL(/members/, { timeout: 15000 });
  await expect(view.locator("tr", { hasText: ADMIN })).toBeVisible(
    { timeout: 10000 });

  await view.getByPlaceholder("输入用户名后查找").fill(TARGET);
  await view.getByRole("button", { name: "查找", exact: true }).click();
  await expect(view.locator(".el-tag").filter({ hasText: "已找到" }))
    .toBeVisible({ timeout: 10000 });
  await choose(view, view.locator(".add-row .el-select"), "editor");
  await view.locator(".add-row").getByRole("button", { name: "添加" })
    .click();
  await expect(view.locator("tr", { hasText: TARGET })).toBeVisible(
    { timeout: 10000 });

  const targetRow = view.locator("tr", { hasText: TARGET });
  await targetRow.getByRole("button", { name: "移除" }).click();
  await view.locator(".el-message-box")
    .getByRole("button", { name: "确定" }).click();
  await expect(view.locator("tr", { hasText: TARGET })).toHaveCount(0,
    { timeout: 10000 });
  await view.screenshot({ path: "../.screens/project-members.png" });
  await context.close();

  try {
    await page.goto("/ui/#/members");
    const row = page.locator("tr", { hasText: ADMIN });
    if (await row.count()) {
      await row.getByRole("button", { name: "移除" }).click();
      await page.locator(".el-message-box")
        .getByRole("button", { name: "确定" }).click();
      await page.waitForTimeout(800);
    }
    await page.goto("/ui/#/admin/users");
    for (const name of [ADMIN, TARGET]) {
      const user = page.locator("tr", { hasText: name });
      if (await user.count()) {
        await user.locator(".el-switch").first().click({ timeout: 5000 });
        await page.waitForTimeout(500);
      }
    }
  } catch (error) {
    console.log("cleanup:", String(error).slice(0, 120));
  }
});
