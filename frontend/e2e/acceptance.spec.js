import { expect, test } from "@playwright/test";

const USER = process.env.ODF_ACCEPTANCE_USER || "acceptance";
const PASS = process.env.ODF_ACCEPTANCE_PASSWORD;

test.beforeEach(() => {
  test.skip(!PASS, "ODF_ACCEPTANCE_PASSWORD is not set");
});

async function login(page) {
  await page.goto("/ui/#/login");
  await page.locator(".el-form-item").filter({ hasText: "用户名" })
    .locator("input").fill(USER);
  await page.locator(".el-form-item").filter({ hasText: "密码" })
    .locator("input").fill(PASS);
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page).toHaveURL(/dashboard/);
}

test("acceptance: login and console", async ({ page }) => {
  await login(page);
  await expect(page.locator(".identity h1")).toHaveText("概览");
  await expect(page.getByRole("heading", { name: "运行记录" })).toBeVisible();
});

test("acceptance: datasource and catalog", async ({ page }) => {
  await login(page);
  await page.goto("/ui/#/datasources");
  await expect(page.getByText(/accept-source-/).first()).toBeVisible();
  await page.goto("/ui/#/catalog");
  await page.getByPlaceholder("搜索表名").fill("accept_source");
  await expect(page.locator(".el-tag.hit", { hasText: "main.accept_source" })
    .first()).toBeVisible();
  await expect(page.getByText("列级血缘")).toBeVisible({ timeout: 10000 });
});

test("acceptance: pipeline actions and column masking UI", async ({ page }) => {
  await login(page);
  const token = await page.evaluate(() => localStorage.getItem("odf_token"));
  const pipe = await page.evaluate(async (t) => {
    const r = await fetch("/api/v1/pipelines", {
      headers: { Authorization: "Bearer " + t },
    });
    return (await r.json())[0];
  }, token);
  await page.goto(`/ui/#/pipelines/${pipe.id}`);
  await expect(page.getByRole("button", { name: "回填" })).toBeVisible();
  await expect(page.getByRole("button", { name: "游标" })).toBeVisible();

  const dataset = await page.evaluate(async (t) => {
    const r = await fetch("/api/v1/datasets", {
      headers: { Authorization: "Bearer " + t },
    });
    const rows = await r.json();
    return rows.find((x) => x.name.startsWith("accept-dataset-"));
  }, token);
  await page.goto(`/ui/#/datasets/${dataset.id}`);
  await page.getByRole("button", { name: "字段脱敏" }).click();
  const drawer = page.getByRole("dialog", { name: "字段脱敏" });
  await expect(drawer.locator("tbody")).toContainText("全遮蔽");
});
