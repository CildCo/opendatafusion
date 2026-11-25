import fs from "node:fs";

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

async function pick(page, scope, label, option) {
  await scope.locator(".el-form-item").filter({ hasText: label })
    .locator(".el-select").click();
  await page.waitForTimeout(500);
  await page.locator(".el-select-dropdown:visible").last()
    .locator(".el-select-dropdown__item")
    .filter({ hasText: option }).first().click();
  await page.waitForTimeout(400);
}

test("wave R: time grain comparison, drill-through, scheduled report, embed",
     async ({ page }) => {
  test.setTimeout(240000);
  await login(page);

  // Metric with a month grain and previous-period comparison
  await page.goto("/ui/#/metrics");
  await page.getByRole("button", { name: "新建指标" }).click();
  const prompt = page.locator(".el-message-box:visible");
  await prompt.locator("input").fill(`UI Revenue ${STAMP}`);
  await prompt.getByRole("button", { name: "确定" }).click();
  await expect(page).toHaveURL(/metrics\/\d+/, { timeout: 15000 });
  const form = page.locator(".form");
  await expect(form).toBeVisible();

  await pick(page, form, "数据集", "orders dataset");
  await page.waitForTimeout(800);
  await pick(page, form, "度量列", "amount");
  await pick(page, form, "时间列", "order_date");
  await pick(page, form, "时间粒度", "按月");
  await pick(page, form, "对比", "对比上期");
  await form.locator(".el-form-item").filter({ hasText: "维度" })
    .locator(".el-select").click();
  await page.waitForTimeout(500);
  await page.locator(".el-select-dropdown:visible").last()
    .locator(".el-select-dropdown__item")
    .filter({ hasText: "region" }).first().click();
  await page.keyboard.press("Escape");
  await page.waitForTimeout(500);

  await page.getByRole("button", { name: "保存" }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 10000 });
  await page.getByRole("button", { name: "校验" }).click();
  await expect(page.locator(".el-message--success").last())
    .toContainText("校验", { timeout: 10000 });
  await page.getByRole("button", { name: "预览" }).click();
  const result = page.locator(".result");
  await expect(result.locator("tbody tr").first())
    .toBeVisible({ timeout: 20000 });
  await expect(result.locator("thead")).toContainText("value_previous");
  await expect(result.locator("thead")).toContainText("value_delta_pct");
  await page.getByRole("button", { name: "发布" }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 20000 });

  // Dashboard with a comparison chart and a drillable metric table
  await page.getByRole("link", { name: "数据看板" }).click();
  await expect(page).toHaveURL(/dashboards$/, { timeout: 15000 });
  await page.getByRole("button", { name: "新建看板" }).click();
  const dashPrompt = page.locator(".el-message-box:visible");
  await dashPrompt.locator("input").fill(`UI Sales ${STAMP}`);
  await dashPrompt.getByRole("button", { name: "确定" }).click();
  await expect(page).toHaveURL(/dashboards\/\d+/, { timeout: 15000 });
  const dashUrl = page.url();
  const dashId = (dashUrl.match(/dashboards\/(\d+)/) || [])[1];

  await page.getByRole("button", { name: "柱状图" }).click();
  await page.waitForTimeout(1200);
  const config = page.locator(".config");
  await pick(page, config, "维度", "order_date");

  await page.getByRole("button", { name: "表格" }).click();
  await page.waitForTimeout(800);
  await config.locator(".el-form-item").filter({ hasText: "指标" })
    .locator(".el-select").click();
  await page.locator(".el-select-dropdown__item:visible")
    .filter({ hasText: `UI Revenue ${STAMP}` }).first().click();
  await page.waitForTimeout(800);
  await pick(page, config, "下钻维度", "region");

  await page.getByRole("button", { name: "保存" }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 10000 });
  await page.getByRole("button", { name: "刷新数据" }).click();
  await expect(page.locator(".widget canvas").first())
    .toBeVisible({ timeout: 20000 });
  const widgetTable = page.locator(".widget").filter({ hasText: "表格" });
  await expect(widgetTable.locator("tbody tr").first())
    .toBeVisible({ timeout: 20000 });

  await page.getByRole("button", { name: "发布" }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 20000 });

  // Drill through a table row
  const row = widgetTable.locator("tbody tr").first();
  const region = (await row.locator("td").nth(0).innerText()).trim();
  await row.click();
  const drawer = page.locator(".el-drawer:visible");
  await expect(drawer).toContainText("明细数据", { timeout: 20000 });
  await expect(drawer.locator("tbody tr").first())
    .toBeVisible({ timeout: 20000 });
  await expect(drawer).toContainText(region);
  await drawer.locator(".el-drawer__close-btn").click();
  await page.waitForTimeout(400);

  // Scheduled report: save the schedule, run now, wait for the worker
  await page.getByRole("button", { name: "定时报表" }).click();
  const report = page.locator(".el-drawer:visible");
  await expect(report).toContainText("报表", { timeout: 10000 });
  await report.locator(".el-form-item").filter({ hasText: "执行计划" })
    .locator("input").fill("0 0 8 * * *");
  await report.getByRole("button", { name: "保存计划" }).click();
  await expect(page.locator(".el-message--success").last())
    .toBeVisible({ timeout: 10000 });
  await report.getByRole("button", { name: "立即生成" }).click();
  await expect(report.locator(".el-table tbody tr").first())
    .toContainText("success", { timeout: 40000 });
  const download = page.waitForEvent("download", { timeout: 20000 });
  await report.getByRole("button", { name: "下载" }).click();
  const file = await download;
  expect(file.suggestedFilename()).toContain(".csv");
  const payload = fs.readFileSync(await file.path(), "utf8");
  expect(payload).toContain("value_previous");
  await report.locator(".el-drawer__close-btn").click();
  await page.waitForTimeout(400);

  // Embed snippet from the share dialog
  await page.getByRole("button", { name: "分享" }).click();
  const share = page.locator(".el-dialog:visible");
  await share.getByRole("button", { name: "生成链接" }).click();
  await expect(share.locator("textarea"))
    .toHaveValue(/<iframe/, { timeout: 20000 });
  await expect(share.locator("textarea"))
    .toHaveValue(/#\/share\//);
  await share.locator(".el-dialog__headerbtn").click();
  await page.waitForTimeout(400);

  // The run page renders the published dashboard
  await page.getByRole("button", { name: "运行" }).click();
  await expect(page).toHaveURL(/dashboards\/\d+\/run/, { timeout: 15000 });
  await expect(page.locator(".widget canvas").first())
    .toBeVisible({ timeout: 20000 });
  await expect(page.locator(".widget").filter({ hasText: "表格" })
    .locator("tbody tr").first()).toBeVisible({ timeout: 20000 });
});
