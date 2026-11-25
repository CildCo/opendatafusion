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

test("wave AA1: pipeline history, copy, layout and runtime",
     async ({ page }) => {
  test.setTimeout(180000);
  await login(page);
  await page.goto("/ui/#/pipelines");
  await page.locator("tr", { hasText: "matrix pipeline" }).first().click();
  await expect(page).toHaveURL(/pipelines\/\d+/, { timeout: 15000 });

  await expect(page.getByText("2 rows").first()).toBeVisible({ timeout: 15000 });
  const nodes = page.locator(".vue-flow__node");
  await expect(nodes).toHaveCount(2);
  await nodes.filter({ hasText: "Source" }).click();
  await nodes.filter({ hasText: "Sink" }).click({ modifiers: ["Shift"] });
  await page.keyboard.press("Control+c");
  await page.keyboard.press("Control+v");
  await expect(page.getByText("Source copy", { exact: true }))
    .toBeVisible({ timeout: 10000 });
  await page.waitForTimeout(600);
  await page.keyboard.press("Control+z");
  await expect(page.getByText("Source copy", { exact: true }))
    .toHaveCount(0, { timeout: 10000 });

  await page.getByRole("button", { name: "自动布局" }).click();
  await page.getByRole("button", { name: "校验", exact: true }).click();
  const validation = page.locator(".el-dialog:visible");
  await expect(validation).toContainText("管道校验", { timeout: 10000 });
  await expect(validation).toContainText("校验通过");
  await validation.getByRole("button", { name: "关闭", exact: true }).click();

  await page.getByRole("button", { name: "回填" }).click();
  const backfill = page.locator(".el-dialog:visible");
  await backfill.locator(".el-form-item").filter({ hasText: "起始游标" })
    .locator("input").fill("0");
  await backfill.getByRole("button", { name: "预览影响" }).click();
  await expect(backfill).toContainText("1 个数据源", { timeout: 15000 });
});

test("wave AA2: dashboard gallery, collision and undo", async ({ page }) => {
  test.setTimeout(120000);
  await login(page);
  await page.goto("/ui/#/dashboards");
  await page.locator("tr", { hasText: "layout dashboard" }).first()
    .getByRole("button", { name: "编辑" }).click();
  await expect(page).toHaveURL(/dashboards\/\d+/, { timeout: 15000 });

  await page.getByRole("button", { name: "添加组件" }).click();
  const gallery = page.locator(".el-dialog:visible");
  await expect(gallery).toContainText("选择图表类型", { timeout: 10000 });
  await expect(gallery.getByText("折线图")).toBeVisible();
  await gallery.getByRole("button", { name: "取消" }).click();
  await expect(page.locator(".el-dialog:visible")).toHaveCount(0,
    { timeout: 10000 });
  await page.waitForTimeout(300);

  const widgets = page.locator(".widget");
  await expect(widgets).toHaveCount(2);
  const firstBefore = await widgets.nth(0).boundingBox();
  const secondBefore = await widgets.nth(1).boundingBox();
  const head = widgets.nth(0).locator(".head");
  const box = await head.boundingBox();
  await page.mouse.move(box.x + 40, box.y + 10);
  await page.mouse.down();
  for (let i = 1; i <= 10; i++) {
    await page.mouse.move(box.x + 40, box.y + 10 + i * 25);
    await page.waitForTimeout(30);
  }
  await page.mouse.up();
  await page.waitForTimeout(500);
  const firstAfter = await widgets.nth(0).boundingBox();
  const secondAfter = await widgets.nth(1).boundingBox();
  expect(firstAfter.y).toBeGreaterThan(firstBefore.y + 100);
  expect(secondAfter.y).toBeGreaterThan(secondBefore.y + 100);
  await page.waitForTimeout(600);
  await page.keyboard.press("Control+z");
  const secondUndo = await widgets.nth(1).boundingBox();
  expect(Math.abs(secondUndo.y - secondBefore.y)).toBeLessThan(10);
});

test("wave AA3: run matrix", async ({ page }) => {
  test.setTimeout(60000);
  await login(page);
  await page.goto("/ui/#/ops");
  await page.getByRole("tab", { name: "运行矩阵" }).click();
  const row = page.locator(".el-tab-pane:visible tr",
                           { hasText: "matrix pipeline" }).first();
  await expect(row).toBeVisible({ timeout: 15000 });
  await expect(row.locator(".matrix-cell").first()).toBeVisible();
});
