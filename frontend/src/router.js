import { createRouter, createWebHashHistory } from "vue-router";
import { getPlatformAdmin, getRole, getToken } from "./api";
import Layout from "./views/Layout.vue";

const AdminLayout = () => import("./views/admin/AdminLayout.vue");
const AdminOverview = () => import("./views/admin/AdminOverview.vue");
const AdminProjects = () => import("./views/admin/AdminProjects.vue");
const AdminIdentity = () => import("./views/admin/AdminIdentity.vue");
const AdminAppearance = () => import("./views/admin/AdminAppearance.vue");
const AdminPlatform = () => import("./views/admin/AdminPlatform.vue");
const AdminOperations = () => import("./views/admin/AdminOperations.vue");

const Login = () => import("./views/Login.vue");
const PublicShare = () => import("./views/PublicShare.vue");
const OidcCallback = () => import("./views/OidcCallback.vue");
const Dashboard = () => import("./views/Dashboard.vue");
const Datasources = () => import("./views/Datasources.vue");
const Catalog = () => import("./views/Catalog.vue");
const CatalogDetail = () => import("./views/CatalogDetail.vue");
const PipelineList = () => import("./views/PipelineList.vue");
const PipelineEditor = () => import("./views/PipelineEditor.vue");
const ApiList = () => import("./views/ApiList.vue");
const ApiEditor = () => import("./views/ApiEditor.vue");
const ToolCatalog = () => import("./views/ToolCatalog.vue");
const ModelHome = () => import("./views/ModelHome.vue");
const DatasetEditor = () => import("./views/DatasetEditor.vue");
const MetricEditor = () => import("./views/MetricEditor.vue");
const DashboardHome = () => import("./views/DashboardHome.vue");
const DashboardEditor = () => import("./views/DashboardEditor.vue");
const DashboardRun = () => import("./views/DashboardRun.vue");
const AppHome = () => import("./views/AppHome.vue");
const Dependencies = () => import("./views/Dependencies.vue");
const AppEditor = () => import("./views/AppEditor.vue");
const AppRun = () => import("./views/AppRun.vue");
const OpsCenter = () => import("./views/OpsCenter.vue");
const Governance = () => import("./views/Governance.vue");
const Workbench = () => import("./views/Workbench.vue");
const Engines = () => import("./views/Engines.vue");
const Cdc = () => import("./views/Cdc.vue");
const Grants = () => import("./views/Grants.vue");
const Webhooks = () => import("./views/Webhooks.vue");
const Files = () => import("./views/Files.vue");
const Workspace = () => import("./views/Workspace.vue");
const Security = () => import("./views/Security.vue");
const Flows = () => import("./views/Flows.vue");
const Interfaces = () => import("./views/Interfaces.vue");
const Quality = () => import("./views/Quality.vue");
const Alerts = () => import("./views/Alerts.vue");
const Changes = () => import("./views/Changes.vue");
const Users = () => import("./views/Users.vue");
const Members = () => import("./views/Members.vue");
const Audit = () => import("./views/Audit.vue");

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
      { path: "governance", component: Governance, meta: { title: "业务域与术语" } },
      { path: "catalog/:id", component: CatalogDetail, meta: { title: "数据目录" } },
      { path: "pipelines", component: PipelineList, meta: { title: "数据管道" } },
      { path: "pipelines/:id", component: PipelineEditor, meta: { title: "管道编辑" } },
      { path: "apis", component: ApiList, meta: { title: "数据接口" } },
      { path: "apis/:id", component: ApiEditor, meta: { title: "接口编辑" } },
      { path: "flows", component: Flows, meta: { title: "数据集成" } },
      { path: "flows/:id", component: Flows, meta: { title: "数据集成" } },
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
      { path: "dependencies", component: Dependencies, meta: { title: "调度依赖" } },
      { path: "workbench", component: Workbench, meta: { title: "SQL 工作台" } },
      { path: "engines", component: Engines, meta: { title: "计算引擎" } },
      { path: "cdc", component: Cdc, meta: { title: "增量同步" } },
      { path: "grants", component: Grants, meta: { title: "接口授权" } },
      { path: "webhooks", component: Webhooks, meta: { title: "事件订阅" } },
      { path: "files", component: Files, meta: { title: "文件" } },
      { path: "workspace", component: Workspace, meta: { title: "工作区设置" } },
      { path: "security", component: Security, meta: { title: "账号安全" } },
      { path: "members", component: Members, meta: { title: "项目成员" } },
      { path: "quality", component: Quality, meta: { title: "数据质量" } },
      { path: "alerts", component: Alerts, meta: { title: "告警" } },
      { path: "changes", component: Changes, meta: { title: "变更" } },
      { path: "users", redirect: "/admin/users" },
      { path: "audit", redirect: "/admin/audit" },
    ],
  },
  {
    path: "/admin",
    component: AdminLayout,
    children: [
      { path: "", redirect: "/admin/overview" },
      { path: "overview", component: AdminOverview },
      { path: "users", component: Users },
      { path: "projects", component: AdminProjects },
      { path: "identity", component: AdminIdentity },
      { path: "appearance", component: AdminAppearance },
      { path: "platform", component: AdminPlatform },
      { path: "operations", component: AdminOperations },
      { path: "audit", component: Audit },
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
  if (to.path.startsWith("/admin") && !getPlatformAdmin()) return "/dashboard";
  if (to.path === "/members" && getRole() !== "admin") return "/dashboard";
  return true;
});

export default router;
