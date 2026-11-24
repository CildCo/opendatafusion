import fs from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";

// Full console sweep: log in through the form, visit every page, open each
// visible tab, and open/close every create dialog. Collects browser errors
// and 4xx responses so a broken page or control fails the run with a list.

const USER = process.env.ODF_SWEEP_USER || "admin";
const PASS = process.env.ODF_SWEEP_PASSWORD || "";
const OUT = path.resolve("test-results", "sweep");

const PAGES = [
  ["/dashboard", "概览"],
  ["/ops", "运维中心"],
  ["/datasources", "数据源"],
  ["/catalog", "数据目录"],
  ["/workbench", "SQL 工作台"],
  ["/files", "文件"],
  ["/pipelines", "数据管道"],
  ["/engines", "计算引擎"],
  ["/cdc", "增量同步"],
  ["/datasets", "数据模型"],
  ["/dashboards", "数据看板"],
  ["/apps", "数据应用"],
  ["/dependencies", "调度依赖"],
  ["/apis", "数据 API"],
  ["/grants", "接口授权"],
  ["/webhooks", "事件订阅"],
  ["/quality", "数据质量"],
  ["/alerts", "告警"],
  ["/changes", "变更"],
  ["/tools", "AI 工具"],
  ["/admin/users", "用户"],
  ["/workspace", "工作区设置"],
  ["/security", "账号安全"],
  ["/admin/audit", "审计"],
];

const CREATE_DIALOGS = [
  ["/datasources", "新建数据源"],
  ["/dashboards", "新建看板"],
  ["/apps", "新建应用"],
  ["/dependencies", "新建依赖"],
  ["/webhooks", "新建订阅"],
  ["/alerts", "新建规则"],
  ["/quality", "新建规则"],
  ["/users", "新建用户"],
];

function short(error) {
  return String(error && error.message ? error.message : error)
    .split("\n")[0].slice(0, 160);
}

test("console sweep", async ({ page }) => {
  test.setTimeout(1500000);
  fs.mkdirSync(OUT, { recursive: true });
  const problems = [];
  const visited = [];
  const save = () => fs.writeFileSync(
    path.join(OUT, "report.json"),
    JSON.stringify({ visited, problems }, null, 2));

  await page.addInitScript(() => localStorage.setItem("odf_locale", "zh"));

  const watch = (label) => {
    page.on("pageerror", (err) => {
      problems.push(`${label}: page error: ${short(err)}`);
    });
    page.on("console", (msg) => {
      if (msg.type() !== "error") return;
      const text = msg.text();
      if (text.includes("Failed to load resource")) return;
      problems.push(`${label}: console error: ${text.slice(0, 200)}`);
    });
    page.on("response", (resp) => {
      if (resp.status() >= 400) {
        problems.push(`${label}: HTTP ${resp.status()} ${resp.url()}`);
      }
    });
  };

  await page.goto("/ui/#/login", { timeout: 20000 });
  await page.locator(".el-form-item").filter({ hasText: "用户名" })
    .locator("input").fill(USER);
  await page.locator(".el-form-item").filter({ hasText: "密码" })
    .locator("input").fill(PASS);
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page).toHaveURL(/dashboard/, { timeout: 15000 });

  for (const [route] of PAGES) {
    watch(route);
    try {
      await page.goto(`/ui/#${route}`, { timeout: 20000 });
    } catch (error) {
      problems.push(`${route}: navigation failed: ${short(error)}`);
      continue;
    }
    await page.waitForTimeout(800);
    const main = page.locator("main, .admin-content");
    if (!(await main.count())) {
      problems.push(`${route}: no main element (blank page)`);
      continue;
    }
    const text = (await main.innerText({ timeout: 5000 }).catch(() => "")).trim();
    if (!text) problems.push(`${route}: main is empty`);
    const tabs = page.locator(".el-tabs__item:visible");
    const tabCount = Math.min(await tabs.count(), 12);
    for (let i = 0; i < tabCount; i += 1) {
      try {
        const tab = tabs.nth(i);
        const name = (await tab.innerText({ timeout: 2000 })).trim();
        await tab.click({ timeout: 4000 });
        await page.waitForTimeout(400);
        await page.locator(".el-tab-pane:visible").first()
          .innerText({ timeout: 3000 }).catch(() => "");
      } catch (error) {
        problems.push(`${route}: tab ${i} failed: ${short(error)}`);
      }
    }
    const slug = route.replace(/\//g, "_").replace(/^_/, "") || "root";
    await page.screenshot({ path: path.join(OUT, `${slug}.png`),
                            fullPage: true, timeout: 20000 })
      .catch(() => {});
    visited.push({ route, tabs: tabCount });
    save();
  }

  for (const [route, label] of CREATE_DIALOGS) {
    watch(`${route}#${label}`);
    try {
      await page.goto(`/ui/#${route}`, { timeout: 20000 });
      await page.waitForTimeout(700);
      const button = page.getByRole("button", { name: label, exact: true })
        .first();
      if (!(await button.count())) {
        problems.push(`${route}: button "${label}" not found`);
        continue;
      }
      await button.click({ timeout: 5000 });
      await page.waitForTimeout(600);
      if (label === "新建看板" || label === "新建应用") {
        const box = page.locator(".el-message-box");
        await expect(box).toBeVisible({ timeout: 5000 });
        await box.getByRole("button", { name: "取消" }).click();
        await expect(box).toBeHidden({ timeout: 5000 });
        continue;
      }
      const dialog = page.locator(".el-dialog:visible").first();
      if (!(await dialog.count())) {
        problems.push(`${route}: "${label}" opened no dialog`);
        continue;
      }
      const cancel = dialog.getByRole("button", { name: /取消|关闭/ }).first();
      if (await cancel.count()) await cancel.click({ timeout: 4000 });
      else await dialog.locator(".el-dialog__headerbtn").click({ timeout: 4000 });
      await expect(dialog).toBeHidden({ timeout: 5000 }).catch(() => {
        problems.push(`${route}: "${label}" dialog did not close`);
      });
    } catch (error) {
      problems.push(`${route}#${label}: ${short(error)}`);
      await page.keyboard.press("Escape").catch(() => {});
    }
    save();
  }

  save();
  expect(problems, problems.join("\n")).toEqual([]);
});
