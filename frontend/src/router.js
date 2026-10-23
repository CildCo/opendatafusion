import { createRouter, createWebHashHistory } from "vue-router";
import { getToken } from "./api";

import Login from "./views/Login.vue";
import PublicShare from "./views/PublicShare.vue";
import OidcCallback from "./views/OidcCallback.vue";
import Layout from "./views/Layout.vue";
import Dashboard from "./views/Dashboard.vue";
import Datasources from "./views/Datasources.vue";
import Catalog from "./views/Catalog.vue";
import PipelineList from "./views/PipelineList.vue";
import PipelineEditor from "./views/PipelineEditor.vue";
import ApiList from "./views/ApiList.vue";
import ApiEditor from "./views/ApiEditor.vue";
import ToolCatalog from "./views/ToolCatalog.vue";
import ModelHome from "./views/ModelHome.vue";
import DatasetEditor from "./views/DatasetEditor.vue";
import MetricEditor from "./views/MetricEditor.vue";
import DashboardHome from "./views/DashboardHome.vue";
import DashboardEditor from "./views/DashboardEditor.vue";
import DashboardRun from "./views/DashboardRun.vue";
import AppHome from "./views/AppHome.vue";
import AppEditor from "./views/AppEditor.vue";
import AppRun from "./views/AppRun.vue";
import OpsCenter from "./views/OpsCenter.vue";
import Workbench from "./views/Workbench.vue";
import Grants from "./views/Grants.vue";
import Webhooks from "./views/Webhooks.vue";
import Files from "./views/Files.vue";
import Workspace from "./views/Workspace.vue";
import Security from "./views/Security.vue";
import Flows from "./views/Flows.vue";
import Interfaces from "./views/Interfaces.vue";
import Quality from "./views/Quality.vue";
import Alerts from "./views/Alerts.vue";
import Changes from "./views/Changes.vue";
import Users from "./views/Users.vue";
import Audit from "./views/Audit.vue";

const routes = [
  { path: "/login", component: Login },
  { path: "/share/:token", component: PublicShare },
  { path: "/oidc", component: OidcCallback },
  {
    path: "/",
    component: Layout,
    children: [
      { path: "", redirect: "/dashboard" },
      { path: "dashboard", component: Dashboard, meta: { title: "概览" } },
      { path: "datasources", component: Datasources, meta: { title: "数据源" } },
      { path: "catalog", component: Catalog, meta: { title: "数据目录" } },
      { path: "pipelines", component: PipelineList, meta: { title: "数据管道" } },
      { path: "pipelines/:id", component: PipelineEditor, meta: { title: "管道编辑" } },
      { path: "apis", component: ApiList, meta: { title: "数据接口" } },
      { path: "apis/:id", component: ApiEditor, meta: { title: "接口编辑" } },
      { path: "flows", component: Flows, meta: { title: "数据集成" } },
      { path: "interfaces", component: Interfaces, meta: { title: "数据接口" } },
      { path: "tools", component: ToolCatalog, meta: { title: "AI 工具" } },
      { path: "datasets", component: ModelHome, meta: { title: "数据模型" } },
      { path: "datasets/:id", component: DatasetEditor, meta: { title: "数据集编辑" } },
      { path: "metrics", component: ModelHome, meta: { title: "数据模型" } },
      { path: "metrics/:id", component: MetricEditor, meta: { title: "指标编辑" } },
      { path: "dashboards", component: DashboardHome, meta: { title: "数据看板" } },
      { path: "dashboards/:id", component: DashboardEditor, meta: { title: "看板编辑" } },
      { path: "dashboards/:id/run", component: DashboardRun, meta: { title: "看板运行" } },
      { path: "apps", component: AppHome, meta: { title: "数据应用" } },
      { path: "apps/:id", component: AppEditor, meta: { title: "应用编辑" } },
      { path: "apps/:id/run", component: AppRun, meta: { title: "应用运行" } },
      { path: "ops", component: OpsCenter, meta: { title: "运维中心" } },
      { path: "workbench", component: Workbench, meta: { title: "SQL 工作台" } },
      { path: "grants", component: Grants, meta: { title: "接口授权" } },
      { path: "webhooks", component: Webhooks, meta: { title: "事件订阅" } },
      { path: "files", component: Files, meta: { title: "文件" } },
      { path: "workspace", component: Workspace, meta: { title: "工作区设置" } },
      { path: "security", component: Security, meta: { title: "账号安全" } },
      { path: "quality", component: Quality, meta: { title: "数据质量" } },
      { path: "alerts", component: Alerts, meta: { title: "告警" } },
      { path: "changes", component: Changes, meta: { title: "变更" } },
      { path: "users", component: Users, meta: { title: "用户" } },
      { path: "audit", component: Audit, meta: { title: "审计" } },
    ],
  },
];

const router = createRouter({
  history: createWebHashHistory(),
  routes,
});

router.beforeEach((to) => {
  if (to.path.startsWith("/share/") || to.path === "/oidc") return true;
  if (to.path !== "/login" && !getToken()) return "/login";
  if (to.path === "/login" && getToken()) return "/dashboard";
  return true;
});

export default router;
