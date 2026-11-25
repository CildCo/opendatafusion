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

async function pick(page, label, option) {
  const item = page.locator(".el-dialog:visible .el-form-item")
    .filter({ hasText: label }).first();
  await item.locator(".el-select").click();
  await page.waitForTimeout(250);
  await page.locator(".el-select-dropdown__item:visible")
    .filter({ hasText: option }).first().click();
  await page.waitForTimeout(300);
}

test("wave L: connector forms show honest capabilities",
     async ({ page }) => {
  test.setTimeout(180000);
  await login(page);
  await page.goto("/ui/#/datasources");
  for (let guard = 0; guard < 8; guard += 1) {
    const stale = page.locator("tr", { hasText: "UI Http " }).first();
    if (!(await stale.count())) break;
    await stale.getByRole("button", { name: "删除" }).click();
    await page.locator(".el-message-box")
      .getByRole("button", { name: "确定" }).click();
    await page.waitForTimeout(700);
  }

  const name = `UI Http ${STAMP}`;
  await page.getByRole("button", { name: "新建数据源" }).click();
  const dialog = page.locator(".el-dialog:visible");
  await dialog.locator(".el-form-item").filter({ hasText: "名称" })
    .locator("input").fill(name);
  await pick(page, "类型", "HTTP API");
  await expect(dialog.locator(".cap-row")).toContainText("管道源");
  await expect(dialog.locator(".cap-row")).toContainText("管道目标");
  await expect(dialog.locator(".cap-row")).not.toContainText("元数据");
  await expect(dialog.locator(".cap-row")).not.toContainText("查询");
  await dialog.locator(".el-form-item").filter({ hasText: "服务地址" })
    .locator("input").fill("http://127.0.0.1:18080/livez");
  await dialog.getByRole("button", { name: "测试连接" }).click();
  await expect(dialog.locator(".el-tag").filter({ hasText: "连接失败" }))
    .toBeVisible({ timeout: 15000 });
  await page.screenshot({ path: "../.screens/datasource-form.png" });
  await dialog.getByRole("button", { name: "保存" }).click();
  await expect(page.getByText(name)).toBeVisible({ timeout: 10000 });

  const row = page.locator("tr", { hasText: name });
  await expect(row).toContainText("仅管道");
  await expect(row.getByRole("button", { name: "同步元数据" }))
    .toHaveCount(0);
  await row.getByRole("button", { name: "测试" }).click();
  await expect(page.locator(".el-message--error")
    .filter({ hasText: "连接失败" })).toBeVisible({ timeout: 15000 });

  await row.getByRole("button", { name: "编辑" }).click();
  const edit = page.locator(".el-dialog:visible");
  await expect(edit.locator(".el-form-item").filter({ hasText: "类型" })
    .locator("input").first()).toBeDisabled();
  await expect(edit.locator(".el-form-item").filter({ hasText: "服务地址" })
    .locator("input")).toHaveValue("http://127.0.0.1:18080/livez");
  const renamed = `${name} edited`;
  await edit.locator(".el-form-item").filter({ hasText: "名称" })
    .locator("input").fill(renamed);
  await edit.getByRole("button", { name: "保存" }).click();
  await expect(page.getByText(renamed)).toBeVisible({ timeout: 10000 });

  const edited = page.locator("tr", { hasText: renamed });
  await edited.getByRole("button", { name: "删除" }).click();
  await page.locator(".el-message-box")
    .getByRole("button", { name: "确定" }).click();
  await expect(page.locator("tr", { hasText: renamed })).toHaveCount(0,
    { timeout: 10000 });
});
