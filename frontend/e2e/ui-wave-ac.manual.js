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

test("wave AC1: catalog domain tree, glossary, search and lineage",
     async ({ page }) => {
  test.setTimeout(180000);
  await login(page);
  await page.goto("/ui/#/catalog");
  await expect(page.locator(".el-tree-node").first())
    .toBeVisible({ timeout: 15000 });

  await page.getByText("按业务域", { exact: true }).click();
  await expect(page.locator(".el-tree-node__content")
    .filter({ hasText: "Sales" }).first()).toBeVisible();
  await expect(page.locator(".term").filter({ hasText: "城市" }))
    .toBeVisible();
  await page.locator(".term").filter({ hasText: "城市" }).click();
  await expect(page.locator(".domain-filter")).toContainText("Sales");

  await page.locator("input[placeholder='搜索表名']").fill("city");
  const hit = page.locator(".search-row").filter({ hasText: "events" })
    .first();
  await expect(hit).toBeVisible({ timeout: 15000 });
  await expect(hit).toContainText("city");

  const explorer = page.locator(".lineage-explorer");
  await expect(explorer).toContainText("个节点", { timeout: 15000 });
  await expect(explorer.locator(".vue-flow__node")
    .filter({ hasText: "1:events" }).first()).toBeVisible();
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    explorer.getByRole("button", { name: "导出 JSON" }).click(),
  ]);
  expect(download.suggestedFilename()).toContain("lineage");

  await hit.click();
  await expect(page).toHaveURL(/catalog\/\d+/, { timeout: 15000 });
});

test("wave AC2: catalog summary, column drawer, comments and impact",
     async ({ page }) => {
  test.setTimeout(180000);
  await login(page);
  await page.goto("/ui/#/catalog");
  await page.locator(".el-tree-node__content").filter({ hasText: "events" })
    .first().click();
  await expect(page).toHaveURL(/catalog\/\d+/, { timeout: 15000 });

  const summary = page.locator(".summary");
  await expect(summary).toContainText("Sales");
  await expect(page.locator(".stat").filter({ hasText: "字段数" })
    .locator("b")).toHaveText("3");
  await expect(page.locator(".rail-card").first()).toContainText("治理状态");
  await expect(page.locator(".rail-card").nth(1))
    .toContainText("城市", { timeout: 15000 });

  await page.getByRole("tab", { name: "字段", exact: true }).click();
  const filter = page.locator("input[placeholder='筛选字段名、类型或分类']");
  await filter.fill("city");
  const row = page.locator(".el-tab-pane:visible tr")
    .filter({ hasText: "city" }).first();
  await expect(row).toContainText("pii");
  await row.getByRole("button", { name: "详情" }).click();
  const drawer = page.locator(".el-drawer:visible");
  await expect(drawer).toContainText("脱敏方式");
  await expect(drawer).toContainText("redact");
  await drawer.locator(".el-drawer__close-btn").click();

  await page.getByRole("tab", { name: "评论", exact: true }).click();
  await page.locator("textarea[placeholder='写下问题、说明或数据口径…']")
    .fill("请补充城市口径说明");
  await page.getByRole("button", { name: "发表评论" }).click();
  const comment = page.locator(".comment").filter({
    hasText: "请补充城市口径说明",
  });
  await expect(comment).toBeVisible({ timeout: 15000 });
  await comment.getByRole("button", { name: "标记解决" }).click();
  await page.locator(".el-radio-button__inner")
    .filter({ hasText: "已解决" }).click();
  const resolved = page.locator(".comment").filter({
    hasText: "请补充城市口径说明",
  });
  await expect(resolved.first()).toContainText("已解决", {
    timeout: 15000,
  });

  await page.getByRole("tab", { name: "依赖与影响" }).click();
  const impact = page.locator(".el-tab-pane:visible .lineage-explorer");
  await expect(impact).toContainText("个节点", { timeout: 15000 });
  await impact.getByText("上游", { exact: true }).click();
  await expect(impact).toContainText("1:events");
  await impact.getByText("下游", { exact: true }).click();
  await expect(impact).toContainText("model:");
});
