import { expect, test } from "@playwright/test";

const USER = process.env.ODF_SWEEP_USER || "admin";
const PASS = process.env.ODF_SWEEP_PASSWORD || "";

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

test("wave S: legacy modules are gone and old paths redirect",
     async ({ page }) => {
  test.setTimeout(120000);
  await login(page);

  const nav = page.locator(".rail-nav");
  await expect(nav).not.toContainText("数据集成（旧版）");
  await expect(nav).not.toContainText("SQL 接口（旧版）");

  await page.goto("/ui/#/flows");
  await expect(page).toHaveURL(/pipelines$/, { timeout: 15000 });
  await page.goto("/ui/#/interfaces");
  await expect(page).toHaveURL(/apis$/, { timeout: 15000 });

  await page.goto("/ui/#/dashboard");
  await expect(page.locator(".inventory-line").filter({ hasText: "管道" }))
    .toBeVisible({ timeout: 15000 });

  await page.keyboard.press("Control+k");
  const palette = page.locator(".cmd-panel");
  await expect(palette).toBeVisible({ timeout: 10000 });
  await palette.locator("input").fill("新建数据集成流程");
  await expect(palette).not.toContainText("新建数据集成流程");
  await page.keyboard.press("Escape");
});
