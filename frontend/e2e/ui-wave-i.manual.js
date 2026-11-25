import { expect, test } from "@playwright/test";

const USER = process.env.ODF_SWEEP_USER || "admin";
const PASS = process.env.ODF_SWEEP_PASSWORD || "";
const STAMP = Date.now().toString(36).slice(-5);
const PASSWORD = "RolePassw0rd!";
const ROLES = [
  { globalRole: "viewer", memberRole: "viewer", label: "查看者",
    write: false, name: `ui_viewer_${STAMP}` },
  { globalRole: "editor", memberRole: "editor", label: "编辑者",
    write: true, name: `ui_editor_${STAMP}` },
  { globalRole: "approver", memberRole: "approver", label: "审批者",
    write: true, name: `ui_approver_${STAMP}` },
  { globalRole: "viewer", memberRole: "editor", label: "编辑者",
    write: true, name: `ui_mixed_in_${STAMP}` },
  { globalRole: "editor", memberRole: "viewer", label: "查看者",
    write: false, name: `ui_mixed_out_${STAMP}` },
];

async function login(page, username, password) {
  await page.addInitScript(() => localStorage.setItem("odf_locale", "zh"));
  await page.goto("/ui/#/login");
  await page.locator(".el-form-item").filter({ hasText: "用户名" })
    .locator("input").fill(username);
  await page.locator(".el-form-item").filter({ hasText: "密码" })
    .locator("input").fill(password);
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page).toHaveURL(/dashboard/, { timeout: 20000 });
}

async function openSelect(page, select, label) {
  await select.click();
  const item = page.locator(".el-select-dropdown__item:visible")
    .filter({ hasText: label }).first();
  await item.click();
  await page.waitForTimeout(300);
}

test("wave I: each role sees its effective project controls",
     async ({ page, browser }) => {
  test.setTimeout(600000);
  await login(page, USER, PASS);

  await page.goto("/ui/#/admin/users");
  for (const entry of ROLES) {
    await page.getByRole("button", { name: "新建用户" }).first().click();
    const dialog = page.locator(".el-dialog:visible");
    const items = dialog.locator(".el-form-item");
    await items.nth(0).locator("input").fill(entry.name);
    await items.nth(1).locator("input").fill(PASSWORD);
    await openSelect(page, dialog.locator(".el-select").first(),
                     entry.globalRole);
    await dialog.getByRole("button", { name: "保存" }).click();
    await expect(page.locator(".el-message--success").last())
      .toBeVisible({ timeout: 10000 });
    await expect(page.locator("tr", { hasText: entry.name })).toBeVisible();
  }

  await page.getByRole("button", { name: "项目成员" }).first().click();
  const drawer = page.locator(".el-drawer:visible");
  await expect(drawer.locator(".member-add")).toBeVisible();
  for (const entry of ROLES) {
    await drawer.locator(".member-add .el-select").nth(0).click();
    await page.locator(".el-select-dropdown__item:visible")
      .filter({ hasText: entry.name }).first().click();
    await page.waitForTimeout(300);
    await drawer.locator(".member-add .el-select").nth(1).click();
    await page.locator(".el-select-dropdown__item:visible")
      .filter({ hasText: entry.memberRole }).first().click();
    await page.waitForTimeout(300);
    await drawer.getByRole("button", { name: "添加", exact: true }).click();
    await expect(drawer.locator("tr", { hasText: entry.name }))
      .toBeVisible({ timeout: 10000 });
  }
  await page.keyboard.press("Escape");

  const checks = [];
  for (const entry of ROLES) {
    const context = await browser.newContext();
    const view = await context.newPage();
    await login(view, entry.name, PASSWORD);
    await view.waitForTimeout(800);
    const nav = await view.locator(".rail-nav").innerText();
    const header = await view.locator(".topbar").innerText();
    const check = { name: entry.name, role: entry.memberRole,
                    global: entry.globalRole,
                    headerHasLabel: header.includes(entry.label),
                    navHasAdmin: nav.includes("系统管理") };

    await view.goto("/ui/#/admin/overview");
    await view.waitForTimeout(1200);
    check.adminRedirected = !view.url().includes("/admin");
    check.adminUrl = view.url();

    await view.goto("/ui/#/datasources");
    await view.waitForTimeout(1000);
    check.canCreateDatasource =
      await view.getByRole("button", { name: "新建数据源" }).count() > 0;

    await view.goto("/ui/#/alerts");
    await view.waitForTimeout(800);
    check.alertRuleButton =
      await view.getByRole("button", { name: "新建规则" }).count() > 0;

    checks.push(check);
    await context.close();
  }
  console.log(JSON.stringify(checks, null, 2));

  for (const check of checks) {
    expect(check.headerHasLabel, JSON.stringify(check)).toBe(true);
    expect(check.navHasAdmin, JSON.stringify(check)).toBe(false);
    expect(check.adminRedirected, JSON.stringify(check)).toBe(true);
  }
  for (const check of checks) {
    const entry = ROLES.find((r) => r.name === check.name);
    expect(check.canCreateDatasource, JSON.stringify(check))
      .toBe(entry.write);
    expect(check.alertRuleButton, JSON.stringify(check)).toBe(entry.write);
  }

  // Cleanup is best effort; the assertions above already prove the behaviour.
  try {
    await page.goto("/ui/#/admin/users");
    for (const entry of ROLES) {
      const row = page.locator("tr", { hasText: entry.name });
      if (!(await row.count())) continue;
      const toggle = row.locator(".el-switch").first();
      if (await toggle.count()) {
        await toggle.click({ timeout: 5000 });
        await page.waitForTimeout(500);
      }
    }
  } catch (error) {
    console.log("cleanup:", String(error).slice(0, 120));
  }
});
