import { expect, test } from "@playwright/test";

async function login(page) {
  await page.goto("/ui/#/login");
  await page.locator(".el-form-item").filter({ hasText: "用户名" })
    .locator("input").fill("e2eadmin");
  await page.locator(".el-form-item").filter({ hasText: "密码" })
    .locator("input").fill("E2ePassw0rd!");
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page).toHaveURL(/dashboard/);
}

test("login and dashboard render", async ({ page }) => {
  await login(page);
  await expect(page.locator(".identity h1")).toHaveText("概览");
  await expect(page.getByRole("heading", { name: "运行记录" })).toBeVisible();
});

test("datasources and catalog search work", async ({ page }) => {
  await login(page);
  await page.goto("/ui/#/datasources");
  await expect(page.getByText("demo sqlite")).toBeVisible();
  await expect(page.getByText("demo file")).toBeVisible();

  await page.goto("/ui/#/catalog");
  await page.getByPlaceholder("搜索表名").fill("demo_src");
  await expect(page.locator(".el-tag.hit", { hasText: "main.demo_src" }))
    .toBeVisible();
  await expect(page.getByText("列级血缘")).toBeVisible({ timeout: 10000 });
});

test("pipeline studio exposes backfill and cursor actions", async ({ page }) => {
  await login(page);
  await page.goto("/ui/#/pipelines/1");
  await expect(page.getByRole("button", { name: "回填" })).toBeVisible();
  await expect(page.getByRole("button", { name: "游标" })).toBeVisible();
  await page.getByRole("button", { name: "游标" }).click();
  await expect(page.getByText("增量游标")).toBeVisible();
  await expect(page.getByText("demo_src")).toBeVisible();
});

test("dataset editor exposes column masking policies", async ({ page }) => {
  await login(page);
  await page.goto("/ui/#/datasets/2");
  await page.getByRole("button", { name: "字段脱敏" }).click();
  const drawer = page.getByRole("dialog", { name: "字段脱敏" });
  await expect(drawer.locator("tbody")).toContainText("全遮蔽");
  await expect(drawer.locator("tbody")).toContainText("editor");
});
