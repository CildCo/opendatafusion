import { computed, ref } from "vue";
import zhCn from "element-plus/es/locale/lang/zh-cn";
import en from "element-plus/es/locale/lang/en";
import assets from "./locales/assets";
import development from "./locales/development";
import studio from "./locales/studio";
import governance from "./locales/governance";
import admin from "./locales/admin";
import pipelineEditor from "./locales/pipeline_editor";
import modelEditor from "./locales/model_editor";
import dashboardEditor from "./locales/dashboard_editor";
import appEditor from "./locales/app_editor";
import apiEditor from "./locales/api_editor";

const KEY = "odf_locale";

const stored = localStorage.getItem(KEY);
const initial = stored === "en" || stored === "zh"
  ? stored
  : (typeof navigator !== "undefined" && navigator.language || "")
    .toLowerCase().startsWith("en") ? "en" : "zh";

export const locale = ref(initial);
if (typeof document !== "undefined") {
  document.documentElement.lang = initial === "en" ? "en" : "zh-CN";
}

const base = {
  zh: {
    "nav.workspace": "工作台",
    "nav.assets": "数据资产",
    "nav.development": "数据开发",
    "nav.governance": "开放与治理",
    "nav.management": "管理",
    "menu.dashboard": "概览",
    "menu.ops": "运维中心",
    "menu.datasources": "数据源",
    "menu.catalog": "数据目录",
    "menu.workbench": "SQL 工作台",
    "menu.files": "文件",
    "menu.pipelines": "数据管道",
    "menu.engines": "计算引擎",
    "menu.cdc": "增量同步",
    "menu.flows": "数据集成",
    "menu.datasets": "数据模型",
    "menu.dashboards": "数据看板",
    "menu.apps": "数据应用",
    "menu.apis": "数据 API",
    "menu.interfaces": "SQL 接口",
    "menu.grants": "接口授权",
    "menu.webhooks": "事件订阅",
    "menu.quality": "数据质量",
    "menu.alerts": "告警",
    "menu.changes": "变更",
    "menu.tools": "AI 工具",
    "menu.dependencies": "调度依赖",
    "menu.users": "用户",
    "menu.workspace": "工作区设置",
    "menu.security": "账号安全",
    "menu.audit": "审计",
    "top.search": "搜索资产、接口、作业",
    "top.online": "在线",
    "top.offline": "离线",
    "top.serviceOnline": "服务在线",
    "top.serviceOffline": "服务离线",
    "top.security": "账号安全",
    "top.workspace": "工作区设置",
    "top.logout": "退出登录",
    "common.remove": "删除",
    "common.back": "返回",
    "top.language": "English",
    "role.admin": "管理员",
    "role.editor": "编辑者",
    "role.approver": "审批者",
    "role.viewer": "查看者",
    "login.subtitle": "使用管理员或项目成员账号进入控制台。",
    "login.username": "用户名",
    "login.password": "密码",
    "login.otp": "动态验证码（启用 2FA 时）",
    "login.project": "项目 ID",
    "login.submit": "登录",
    "login.help": "遇到权限问题请联系工作区管理员",
    "login.feature1": "数据源 → 管道 → 模型 → 接口",
    "login.feature2": "治理、审批与审计在同一条链路上",
    "login.feature3": "外部 AI 通过 MCP 接入同一套能力",
    "dash.title": "概览",
    "dash.subtitle": "工作区的数据流动、作业状态与待处理事项。",
    "dash.running": "运行中",
    "dash.currentJobs": "当前作业",
    "dash.failedToday": "今日失败",
    "dash.last24h": "最近 24 小时",
    "dash.openAlerts": "未处理告警",
    "dash.needsAttention": "需要关注",
    "dash.runs24h": "24h 运行",
    "dash.allFlows": "全部流程",
    "dash.runHistory": "运行记录",
    "dash.runHistoryHint": "按时间倒序，点击行进入运维中心",
    "dash.toHandle": "需要处理",
    "dash.openAlertCount": "条未处理告警",
    "dash.openOps": "打开运维中心 →",
    "dash.schedule": "计划窗口",
    "dash.scheduledPipelines": "已启用 cron 的管道",
    "dash.assets": "资产概览",
    "dash.datasources": "数据源",
    "dash.flows": "流程",
    "dash.interfaces": "接口",
    "dash.qualityRules": "质量规则",
    "common.refresh": "刷新",
    "common.save": "保存",
    "common.cancel": "取消",
    "common.delete": "删除",
    "common.create": "新建",
    "common.edit": "编辑",
    "common.run": "运行",
    "common.close": "关闭",
    "common.test": "测试",
    "common.submit": "提交",
    "common.language": "界面语言",
    "common.languageZh": "简体中文",
    "common.languageEn": "English",
    "settings.intro": "品牌、主题色、菜单可见性与界面语言。",
    "settings.scope": "按项目生效",
    "settings.themeColor": "主题色",
    "settings.welcomeTitle": "欢迎标题",
    "settings.welcomePlaceholder": "例如：欢迎使用数据平台",
    "settings.welcomeText": "欢迎说明",
    "settings.hiddenMenus": "隐藏菜单",
    "settings.menuPermissions": "菜单权限",
    "settings.menuHint": "仅对非管理员生效；勾选为空表示不限制。隐藏菜单只影响界面，菜单权限会同时拦截后端接口。",
    "settings.applyHint": "设置保存后立即应用到侧边栏品牌、主题色和菜单可见性。",
    "settings.saved": "已保存，正在刷新",
    "login.passwordPlaceholder": "输入密码",
    "login.otpPlaceholder": "可选",
    "login.oidc": "使用企业账号登录 (OIDC)",
    "login.missing": "请输入用户名和密码",
    "layout.projectError": "项目加载失败",
    "layout.switched": "已切换项目",
    "layout.switchError": "切换失败",
  },
  en: {
    "nav.workspace": "Workspace",
    "nav.assets": "Data assets",
    "nav.development": "Data development",
    "nav.governance": "Open access & governance",
    "nav.management": "Administration",
    "menu.dashboard": "Overview",
    "menu.ops": "Operations",
    "menu.datasources": "Data sources",
    "menu.catalog": "Catalog",
    "menu.workbench": "SQL workbench",
    "menu.files": "Files",
    "menu.pipelines": "Pipelines",
    "menu.engines": "Engines",
    "menu.cdc": "Change data capture",
    "menu.flows": "Integration",
    "menu.datasets": "Data models",
    "menu.dashboards": "Dashboards",
    "menu.apps": "Data apps",
    "menu.apis": "Data APIs",
    "menu.interfaces": "SQL interfaces",
    "menu.grants": "Access control",
    "menu.webhooks": "Webhooks",
    "menu.quality": "Data quality",
    "menu.alerts": "Alerts",
    "menu.changes": "Changes",
    "menu.tools": "AI tools",
    "menu.dependencies": "Scheduling dependencies",
    "menu.users": "Users",
    "menu.workspace": "Workspace settings",
    "menu.security": "Account security",
    "menu.audit": "Audit",
    "top.search": "Search assets, interfaces, jobs",
    "top.online": "Online",
    "top.offline": "Offline",
    "top.serviceOnline": "Service online",
    "top.serviceOffline": "Service offline",
    "top.security": "Account security",
    "top.workspace": "Workspace settings",
    "top.logout": "Sign out",
    "common.remove": "Remove",
    "common.back": "Back",
    "top.language": "中文",
    "role.admin": "Administrator",
    "role.editor": "Editor",
    "role.approver": "Approver",
    "role.viewer": "Viewer",
    "login.subtitle": "Sign in with an administrator or project member account.",
    "login.username": "Username",
    "login.password": "Password",
    "login.otp": "One-time code (when 2FA is enabled)",
    "login.project": "Project ID",
    "login.submit": "Sign in",
    "login.help": "Contact your workspace administrator for access",
    "login.feature1": "Sources → pipelines → models → interfaces",
    "login.feature2": "Governance, approval and audit on one path",
    "login.feature3": "External AI agents share the same capabilities over MCP",
    "dash.title": "Overview",
    "dash.subtitle": "Data movement, job state and pending items in this workspace.",
    "dash.running": "Running",
    "dash.currentJobs": "Current jobs",
    "dash.failedToday": "Failed today",
    "dash.last24h": "Last 24 hours",
    "dash.openAlerts": "Open alerts",
    "dash.needsAttention": "Needs attention",
    "dash.runs24h": "Runs in 24h",
    "dash.allFlows": "All flows",
    "dash.runHistory": "Run history",
    "dash.runHistoryHint": "Newest first; open a row in Operations",
    "dash.toHandle": "To handle",
    "dash.openAlertCount": "open alerts",
    "dash.openOps": "Open Operations →",
    "dash.schedule": "Schedule window",
    "dash.scheduledPipelines": "Pipelines with cron enabled",
    "dash.assets": "Asset overview",
    "dash.datasources": "Data sources",
    "dash.flows": "Flows",
    "dash.interfaces": "Interfaces",
    "dash.qualityRules": "Quality rules",
    "common.refresh": "Refresh",
    "common.save": "Save",
    "common.cancel": "Cancel",
    "common.delete": "Delete",
    "common.create": "New",
    "common.edit": "Edit",
    "common.run": "Run",
    "common.close": "Close",
    "common.test": "Test",
    "common.submit": "Submit",
    "common.language": "Interface language",
    "common.languageZh": "简体中文",
    "common.languageEn": "English",
    "settings.intro": "Brand, theme colour, menu visibility and interface language.",
    "settings.scope": "Applies per project",
    "settings.themeColor": "Theme colour",
    "settings.welcomeTitle": "Welcome title",
    "settings.welcomePlaceholder": "For example: welcome to the data platform",
    "settings.welcomeText": "Welcome text",
    "settings.hiddenMenus": "Hidden menus",
    "settings.menuPermissions": "Menu permissions",
    "settings.menuHint": "Applies to non-admins only; an empty selection means no restriction. Hiding a menu only affects the console; permissions also block the backend routes.",
    "settings.applyHint": "Saving applies the brand, theme colour and menu visibility to the sidebar immediately.",
    "settings.saved": "Saved, reloading",
    "login.passwordPlaceholder": "Enter password",
    "login.otpPlaceholder": "Optional",
    "login.oidc": "Sign in with a corporate account (OIDC)",
    "login.missing": "Enter a username and password",
    "layout.projectError": "Could not load projects",
    "layout.switched": "Project switched",
    "layout.switchError": "Could not switch project",
  },
};

const parts = [assets, development, studio, governance, admin,
               pipelineEditor, modelEditor, dashboardEditor, appEditor, apiEditor];

const messages = {
  zh: Object.assign({}, base.zh, ...parts.map((p) => p.zh || {})),
  en: Object.assign({}, base.en, ...parts.map((p) => p.en || {})),
};

export function t(key) {
  return (messages[locale.value] && messages[locale.value][key])
    || messages.zh[key] || key;
}

export function setLocale(value) {
  locale.value = value === "en" ? "en" : "zh";
  localStorage.setItem(KEY, locale.value);
  document.documentElement.lang = locale.value === "en" ? "en" : "zh-CN";
}

export function toggleLocale() {
  setLocale(locale.value === "en" ? "zh" : "en");
}

export const elementLocale = computed(() =>
  locale.value === "en" ? en : zhCn);

export function fmtDate(value) {
  if (!value) return "-";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value
    : d.toLocaleString(locale.value === "en" ? "en-US" : "zh-CN");
}
