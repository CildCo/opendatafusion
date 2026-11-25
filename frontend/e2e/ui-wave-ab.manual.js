import { expect, test } from "@playwright/test";

async function login(page) {
  await page.addInitScript(() => localStorage.setItem("odf_locale", "zh"));
  await page.goto("/ui/#/login");
  await page.locator(".el-form-item").filter({ hasText: "用户名" })
    .locator("input").fill("admin");
  await page.locator(".el-form-item").filter({ hasText: "密码" })
    .locator("input").fill(process.env.ODF_SWEEP_PASSWORD || "");
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page).toHaveURL(/dashboard/, { timeout: 15000 });
}

test("wave AB1: app free-form canvas, drag, undo and new components",
     async ({ page }) => {
  test.setTimeout(180000);
  await login(page);
  await page.goto("/ui/#/apps");
  await page.locator("tr", { hasText: "lowcode demo" }).first()
    .getByRole("button", { name: "编辑" }).click();
  await expect(page).toHaveURL(/apps\/\d+/, { timeout: 15000 });

  const widgets = page.locator(".app-widget");
  await expect(widgets.first()).toBeVisible({ timeout: 15000 });
  const startCount = await widgets.count();
  expect(startCount).toBeGreaterThanOrEqual(6);
  const heading = widgets.filter({ hasText: "销售概览" }).first();
  await expect(heading).toContainText("销售概览 · shanghai");
  await expect(page.locator(".app-widget.progress"))
    .toContainText("60");
  await expect(page.locator(".el-loading-mask")).toHaveCount(0, {
    timeout: 15000,
  });

  const before = await heading.boundingBox();
  const head = heading.locator(".widget-head");
  const box = await head.boundingBox();
  await page.mouse.move(box.x + 60, box.y + 8);
  await page.mouse.down();
  for (let i = 1; i <= 8; i++) {
    await page.mouse.move(box.x + 60, box.y + 8 + i * 20);
    await page.waitForTimeout(60);
  }
  await page.mouse.up();
  await page.waitForTimeout(500);
  const after = await heading.boundingBox();
  expect(after.y).toBeGreaterThan(before.y + 50);

  await page.keyboard.press("Control+z");
  await page.waitForTimeout(700);
  const undone = await heading.boundingBox();
  expect(Math.abs(undone.y - before.y)).toBeLessThan(10);

  await page.getByRole("button", { name: "+ 标题" }).click();
  await expect(widgets).toHaveCount(startCount + 1);
  const configText = page.locator(".config textarea").first();
  await configText.fill("新增标题 {{city}}");
  await expect(page.locator(".app-widget").filter({ hasText: "新增标题" })
    .first()).toBeVisible();

  await page.getByRole("button", { name: "整理布局" }).click();
  await page.waitForTimeout(400);
  await page.getByRole("button", { name: "校验", exact: true }).click();
  await expect(page.locator(".el-message").last())
    .toContainText("校验通过", { timeout: 15000 });

  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.locator(".el-message").last())
    .toContainText("已保存草稿", { timeout: 15000 });
  await page.getByRole("button", { name: "发布", exact: true }).click();
  await expect(page.locator(".el-message").last())
    .toContainText("已发布", { timeout: 15000 });
});

test("wave AB2: runtime layout, progress, visibility and button navigation",
     async ({ page }) => {
  test.setTimeout(120000);
  await login(page);
  await page.goto("/ui/#/apps");
  await page.locator("tr", { hasText: "lowcode demo" }).first()
    .getByRole("button", { name: "运行" }).click();
  await expect(page).toHaveURL(/apps\/\d+\/run/, { timeout: 15000 });

  await expect(page.locator(".app-widget.heading").first())
    .toContainText("销售概览 · shanghai");
  await expect(page.locator(".app-widget.progress"))
    .toContainText("60");
  await expect(page.getByText("当前城市：shanghai")).toBeVisible();

  await page.locator(".filters input").first().fill("beijing");
  await page.getByRole("button", { name: "查询" }).click();
  await expect(page.locator(".app-widget.heading").first())
    .toContainText("销售概览 · beijing", { timeout: 15000 });
  await expect(page.locator(".app-widget.text")).toBeHidden();

  await page.getByRole("button", { name: "查看明细" }).click();
  await expect(page.locator(".app-widget.heading").first())
    .toContainText("明细", { timeout: 15000 });
});

test("wave AB3: transform model editor loads and undoes edits",
     async ({ page }) => {
  test.setTimeout(120000);
  await login(page);
  await page.goto("/ui/#/models");
  await page.locator("tr", { hasText: "events model" }).first()
    .getByRole("button", { name: "编辑" }).click();
  await expect(page).toHaveURL(/models\/\d+/, { timeout: 15000 });
  await expect(page.getByText("页面加载失败")).toHaveCount(0);
  const description = page.locator(".form textarea").first();
  await expect(description).toBeVisible({ timeout: 15000 });
  const original = await description.inputValue();
  await description.fill("temporary description");
  await page.waitForTimeout(600);
  await page.getByRole("button", { name: "撤销" }).click();
  await expect(description).toHaveValue(original, { timeout: 10000 });
});
