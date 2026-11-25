import { expect, test } from "@playwright/test";

const USER = process.env.ODF_SWEEP_USER || "admin";
const PASS = process.env.ODF_SWEEP_PASSWORD || "";
const PYTHON = "H:/My_script/opendatafusion/impl/.venv/Scripts/python.exe";
const FAKE = "C:/Users/zs/AppData/Local/Temp/odf_ui210/fake_airbyte.py";

const GEO = {
  type: "FeatureCollection",
  features: [
    { type: "Feature", properties: { name: "north" },
      geometry: { type: "Polygon", coordinates: [
        [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]] } },
    { type: "Feature", properties: { name: "south" },
      geometry: { type: "Polygon", coordinates: [
        [[0, 1], [1, 1], [1, 2], [0, 2], [0, 1]]] } },
  ],
};

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

test("wave T: Airbyte import, GraphQL, map widget and mobile navigation",
     async ({ page }) => {
  test.setTimeout(240000);
  await login(page);

  // Airbyte protocol connector through the console
  await page.goto("/ui/#/datasources");
  await page.getByRole("button", { name: "新建数据源" }).click();
  const dialog = page.locator(".el-dialog:visible");
  await dialog.locator(".el-form-item").filter({ hasText: "名称" })
    .locator("input").fill("airbyte users");
  await dialog.locator(".el-form-item").filter({ hasText: "类型" })
    .locator(".el-select").click();
  await page.locator(".el-select-dropdown:visible")
    .locator(".el-select-dropdown__item")
    .filter({ hasText: "Airbyte connector" }).first().click();
  await page.waitForTimeout(500);
  await dialog.locator(".el-form-item").filter({ hasText: "连接器镜像" })
    .locator("input").fill(`${PYTHON} ${FAKE}`);
  await dialog.locator(".el-form-item").filter({ hasText: "运行方式" })
    .locator(".el-select").click();
  await page.locator(".el-select-dropdown:visible")
    .locator(".el-select-dropdown__item")
    .filter({ hasText: "command" }).first().click();
  await dialog.locator(".el-form-item").filter({ hasText: "连接器配置" })
    .locator("textarea").fill('{"token": "demo"}');
  await dialog.getByRole("button", { name: "保存" }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 10000 });
  const row = page.locator("tr", { hasText: "airbyte users" });
  await expect(row).toBeVisible();
  await row.getByRole("button", { name: "测试", exact: true }).click();
  await expect(page.locator(".el-message--success")
    .filter({ hasText: "连接正常" }).last())
    .toBeVisible({ timeout: 20000 });
  await row.getByRole("button", { name: "同步元数据" }).click();
  await expect(page.locator(".el-message--success")
    .filter({ hasText: "已同步" }).last())
    .toBeVisible({ timeout: 20000 });
  await page.goto("/ui/#/catalog");
  await page.getByPlaceholder("搜索表、字段或标签").fill("users");
  await expect(page.locator(".search-row").first())
    .toBeVisible({ timeout: 15000 });

  // GraphQL schema and endpoint in the API console
  await page.goto("/ui/#/apis");
  await page.getByRole("button", { name: "GraphQL" }).click();
  const gql = page.locator(".el-dialog:visible");
  await expect(gql).toContainText("/openapi/graphql", { timeout: 15000 });
  await expect(gql.locator("textarea").first())
    .toHaveValue(/total/);
  await expect(gql.locator("textarea").last())
    .toHaveValue(/type Query/);
  await gql.getByRole("button", { name: "关闭", exact: true }).click();

  // Map widget upload and render
  await page.goto("/ui/#/dashboards");
  await page.locator(".el-table__body tbody tr", { hasText: "orders map" })
    .first().getByRole("button", { name: "编辑" }).click();
  await expect(page).toHaveURL(/dashboards\/\d+/, { timeout: 15000 });
  await page.locator(".widget").first().click();
  const config = page.locator(".config");
  await expect(config).toContainText("地图数据", { timeout: 10000 });
  await config.locator('input[type="file"]').setInputFiles({
    name: "regions.json", mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(GEO)),
  });
  await expect(config).toContainText("2 个区域", { timeout: 10000 });
  await page.getByRole("button", { name: "保存" }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 10000 });
  await page.getByRole("button", { name: "发布" }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 20000 });
  await page.getByRole("button", { name: "运行" }).click();
  await expect(page).toHaveURL(/dashboards\/\d+\/run/, { timeout: 15000 });
  await expect(page.locator(".widget canvas").first())
    .toBeVisible({ timeout: 20000 });

  // Mobile navigation drawer
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/ui/#/dashboard");
  await page.locator(".mobile-menu").click();
  const mobile = page.locator(".mobile-nav-drawer");
  await expect(mobile).toContainText("数据源", { timeout: 10000 });
  await mobile.getByRole("link", { name: "数据源" }).click();
  await expect(page).toHaveURL(/datasources/, { timeout: 15000 });
  await expect(page.locator(".page")).toBeVisible();
});
