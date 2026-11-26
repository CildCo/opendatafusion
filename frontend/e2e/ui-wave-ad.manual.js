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

test("wave AD1: workbench autocomplete and result chart",
     async ({ page }) => {
  test.setTimeout(180000);
  await login(page);
  await page.goto("/ui/#/workbench");
  const editor = page.locator(".cm-content").first();
  await expect(editor).toBeVisible({ timeout: 15000 });
  await editor.click();
  await page.keyboard.press("Control+A");
  await page.keyboard.type("select * from ev");
  await page.keyboard.press("Control+Space");
  await expect(page.locator(".cm-tooltip-autocomplete"))
    .toContainText("events", { timeout: 10000 });

  await page.keyboard.press("Escape");
  await editor.click();
  await page.keyboard.press("Control+A");
  await page.keyboard.type(
    "select city, sum(amount) as total from events group by city");
  await page.getByRole("button", { name: "执行", exact: true }).click();
  await expect(page.locator(".result .el-table__row").first())
    .toBeVisible({ timeout: 20000 });
  await expect(page.locator(".result")).toContainText("shanghai");
  await page.locator(".result-head .el-select").first().click();
  await page.getByRole("option", { name: "柱状图" }).click();
  await expect(page.locator(".result-chart canvas")).toBeVisible({
    timeout: 10000,
  });
});

test("wave AD2: favorite, command palette and glossary link",
     async ({ page }) => {
  test.setTimeout(180000);
  await login(page);
  await page.goto("/ui/#/catalog");
  await page.locator(".el-tree-node__content").filter({ hasText: "events" })
    .first().click();
  await expect(page).toHaveURL(/catalog\/\d+/, { timeout: 15000 });

  const already = page.getByRole("button", { name: "取消收藏", exact: true });
  if (await already.count()) {
    await already.click();
    await expect(page.getByRole("button", { name: "收藏", exact: true }))
      .toBeVisible({ timeout: 10000 });
  }
  await page.getByRole("button", { name: "收藏", exact: true }).click();
  await expect(page.locator(".el-message").last())
    .toContainText("已收藏", { timeout: 15000 });
  await page.keyboard.press("Control+K");
  await expect(page.locator(".cmd-group").filter({ hasText: "我的收藏" }))
    .toBeVisible({ timeout: 15000 });
  await expect(page.locator(".cmd-item").filter({ hasText: "main.events" })
    .first()).toBeVisible();
  await page.keyboard.press("Escape");

  await page.getByRole("tab", { name: "字段", exact: true }).click();
  const filter = page.locator("input[placeholder='筛选字段名、类型或分类']");
  await filter.fill("amount");
  const row = page.locator(".el-tab-pane:visible tr")
    .filter({ hasText: "amount" }).first();
  await row.getByRole("button", { name: "详情" }).click();
  const drawer = page.locator(".el-drawer:visible");
  await drawer.locator(".term-add .el-select").click();
  await page.getByRole("option", { name: "成交额" }).click();
  await drawer.getByRole("button", { name: "绑定" }).click();
  await expect(drawer.locator(".term-links"))
    .toContainText("成交额", { timeout: 15000 });
  await drawer.locator(".el-drawer__close-btn").click();
  await expect(page.locator(".el-tab-pane:visible tr")
    .filter({ hasText: "amount" }).first()).toContainText("成交额");

  await page.goto("/ui/#/catalog");
  await page.locator("input[placeholder='搜索表、字段或标签']").fill("成交额");
  const hit = page.locator(".search-row").filter({ hasText: "events" })
    .first();
  await expect(hit).toContainText("成交额", { timeout: 15000 });
});

test("wave AD3: alert assignment, note and close", async ({ page }) => {
  test.setTimeout(120000);
  await login(page);
  await page.goto("/ui/#/alerts");
  await page.locator("tr", { hasText: "freshness: events" }).first().click();
  const drawer = page.locator(".el-drawer:visible");
  await expect(drawer).toContainText("时间线", { timeout: 15000 });
  await drawer.locator(".drawer-actions .el-select").click();
  await page.getByRole("option", { name: "alice" }).click();
  await drawer.getByRole("button", { name: "分派" }).click();
  await expect(drawer.locator(".el-descriptions"))
    .toContainText("alice", { timeout: 15000 });

  await drawer.locator("textarea[placeholder*='记录排查进展']")
    .fill("checking upstream freshness");
  await drawer.getByRole("button", { name: "添加备注" }).click();
  await expect(drawer.locator(".timeline"))
    .toContainText("checking upstream freshness", { timeout: 15000 });
  await drawer.getByRole("button", { name: "关闭", exact: true }).first()
    .click();
  const confirm = page.locator(".el-message-box:visible");
  await confirm.getByRole("button", { name: "确定" }).click();
  await expect(drawer.locator(".el-descriptions"))
    .toContainText("已关闭", { timeout: 15000 });
});
