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

async function fill(page, label, value) {
  const item = page.locator(".el-dialog:visible .el-form-item")
    .filter({ has: page.locator(".el-form-item__label")
      .filter({ hasText: new RegExp(`^\\*?\\s*${label}`) }) });
  await item.locator("input").fill(value);
}

async function remove(page, name) {
  const row = page.locator("tr", { hasText: name });
  await row.getByRole("button", { name: "删除" }).click();
  await page.locator(".el-message-box")
    .getByRole("button", { name: "确定" }).click();
  await page.waitForTimeout(700);
  if (await page.locator(".el-message-box").count()) {
    await page.locator(".el-message-box")
      .getByRole("button", { name: "确定" }).click();
  }
  await expect(page.locator("tr", { hasText: name })).toHaveCount(0,
    { timeout: 10000 });
}

test("wave M: DuckDB and compatible database families work",
     async ({ page }) => {
  test.setTimeout(240000);
  await login(page);
  await page.goto("/ui/#/datasources");

  for (const prefix of ["UI Duck ", "UI Gauss "]) {
    for (let guard = 0; guard < 6; guard += 1) {
      const stale = page.locator("tr", { hasText: prefix }).first();
      if (!(await stale.count())) break;
      await stale.getByRole("button", { name: "删除" }).click();
      await page.locator(".el-message-box")
        .getByRole("button", { name: "确定" }).click();
      await page.waitForTimeout(600);
    }
  }

  const duck = `UI Duck ${STAMP}`;
  await page.getByRole("button", { name: "新建数据源" }).click();
  const dlg = page.locator(".el-dialog:visible");
  await dlg.locator(".el-form-item").filter({ hasText: "名称" })
    .locator("input").fill(duck);
  await pick(page, "类型", "DuckDB");
  await fill(page, "文件路径", `duckdb:////tmp/ui_duck_${STAMP}.duckdb`);
  await dlg.getByRole("button", { name: "测试连接" }).click();
  await expect(dlg.locator(".el-tag").filter({ hasText: "连接正常" }))
    .toBeVisible({ timeout: 20000 });
  await dlg.getByRole("button", { name: "保存" }).click();
  await expect(page.getByText(duck)).toBeVisible({ timeout: 10000 });
  const duckRow = page.locator("tr", { hasText: duck });
  await duckRow.getByRole("button", { name: "同步元数据" }).click();
  await expect(page.locator(".el-message--success")
    .filter({ hasText: "已同步" })).toBeVisible({ timeout: 20000 });
  await remove(page, duck);

  const gauss = `UI Gauss ${STAMP}`;
  await page.getByRole("button", { name: "新建数据源" }).click();
  const dlg2 = page.locator(".el-dialog:visible");
  await dlg2.locator(".el-form-item").filter({ hasText: "名称" })
    .locator("input").fill(gauss);
  await pick(page, "类型", "openGauss");
  await fill(page, "主机", "127.0.0.1");
  await fill(page, "端口", "5432");
  await fill(page, "数据库", "odf_demo");
  await fill(page, "用户名", "odf");
  await dlg2.getByRole("button", { name: "测试连接" }).click();
  await expect(dlg2.locator(".el-tag").filter({ hasText: "连接正常" }))
    .toBeVisible({ timeout: 20000 });
  await dlg2.getByRole("button", { name: "保存" }).click();
  await expect(page.getByText(gauss)).toBeVisible({ timeout: 10000 });
  const gaussRow = page.locator("tr", { hasText: gauss });
  await gaussRow.getByRole("button", { name: "同步元数据" }).click();
  await expect(page.locator(".el-message--success")
    .filter({ hasText: "已同步" })).toBeVisible({ timeout: 30000 });
  await gaussRow.getByRole("button", { name: "表", exact: true }).click();
  const drawer = page.locator(".el-drawer:visible");
  await expect(drawer).toBeVisible();
  await expect(drawer.locator(".el-table__body tbody tr").first())
    .toBeVisible({ timeout: 10000 });
  await drawer.locator(".el-drawer__close-btn").click();
  await remove(page, gauss);

  await page.goto("/ui/#/cdc");
  await page.getByRole("button", { name: "新建 CDC 源" }).click();
  const cdcDialog = page.locator(".el-dialog:visible");
  await pick(page, "类型", "SQL Server");
  await expect(cdcDialog.locator(".el-form-item").filter({ hasText: "端口" })
    .locator("input")).toHaveValue("1433");
  await expect(cdcDialog.getByRole("textbox", { name: "Schema", exact: true }))
    .toHaveValue("dbo");
  await cdcDialog.getByRole("button", { name: "取消" }).click();

  await page.goto("/ui/#/datasources");
  const kafka = `UI Kafka ${STAMP}`;
  await page.getByRole("button", { name: "新建数据源" }).click();
  const kdlg = page.locator(".el-dialog:visible");
  await kdlg.locator(".el-form-item").filter({ hasText: "名称" })
    .locator("input").fill(kafka);
  await pick(page, "类型", "Kafka");
  await fill(page, "Bootstrap", "kafka:9092");
  await kdlg.getByRole("button", { name: "保存" }).click();
  await expect(page.getByText(kafka)).toBeVisible({ timeout: 10000 });
  const krow = page.locator("tr", { hasText: kafka });
  await expect(krow).toContainText("仅管道");
  await expect(krow.getByRole("button", { name: "同步元数据" }))
    .toHaveCount(0);
  await remove(page, kafka);
});
