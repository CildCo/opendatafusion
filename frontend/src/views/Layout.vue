<template>
  <div class="shell" :style="{ '--odf-primary': accentColor }">
    <aside class="rail">
      <router-link to="/dashboard" class="brand">
        <span class="mark">OD</span>
        <span class="brand-copy">
          <b>{{ portal.brand_name }}</b>
          <small>data operations</small>
        </span>
      </router-link>

      <nav class="rail-nav">
        <section v-for="group in menuGroups" :key="group.name" class="nav-group">
          <div class="nav-label">{{ group.name }}</div>
          <router-link v-for="m in group.items" :key="m.path" :to="m.path"
                       class="nav-item"
                       :class="{ active: activePath === m.path }">
            <el-icon><component :is="m.icon" /></el-icon>
            <span>{{ m.title }}</span>
          </router-link>
        </section>
      </nav>

      <div class="rail-foot">
        <div class="service-state">
          <span class="dot" :class="{ on: online }"></span>
          {{ online ? "服务在线" : "服务离线" }}
        </div>
        <div class="rail-meta">
          <span>API 18080</span>
          <span>MCP 18082</span>
          <span>v1.0</span>
        </div>
      </div>
    </aside>

    <div class="workspace">
      <header class="topbar">
        <div class="identity">
          <h1>{{ $route.meta.title || "控制台" }}</h1>
          <div class="context">
            <span>{{ projectName }}</span>
            <span class="sep">/</span>
            <span>{{ roleLabel }}</span>
          </div>
        </div>
        <div class="top-actions">
          <button class="search-entry" type="button"
                  @click="$router.push('/catalog')">
            <el-icon><Search /></el-icon>
            <span>搜索资产、接口、作业</span>
          </button>
          <el-select :model-value="currentProject" class="project-switch"
                     size="small" @change="switchProject">
            <el-option v-for="p in projects" :key="p.id" :value="p.id"
                       :label="p.name" />
          </el-select>
          <div class="online" :class="{ off: !online }">
            <span class="dot" :class="{ on: online }"></span>
            {{ online ? "在线" : "离线" }}
          </div>
          <el-dropdown trigger="click" @command="onUserCommand">
            <button class="user-trigger" type="button">
              <span class="avatar">{{ initial }}</span>
              <span class="user-copy">
                <b>{{ username }}</b>
                <small>{{ roleLabel }}</small>
              </span>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="security">账号安全</el-dropdown-item>
                <el-dropdown-item command="workspace">工作区设置</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>
      <main class="content">
        <router-view :key="$route.fullPath" />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  Odometer, Coin, Collection, Share, Connection, CircleCheck, Bell,
  Switch, User, Document, Grid, Monitor, EditPen, Key, Promotion,
  Folder, Setting, Lock, Search,
} from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { api, clearSession, getProject, getRole, setProject }
  from "../api";

const route = useRoute();
const router = useRouter();
const role = getRole() || "viewer";
const online = ref(true);
const projects = ref([]);
const currentProject = ref(getProject());
const portal = ref({ brand_name: "OpenDataFusion", primary_color: "#1d4ed8",
                     hidden_menus: [], allowed_menus: null });

const groups = [
  { name: "工作台", items: [
    { path: "/dashboard", title: "概览", icon: Odometer },
    { path: "/ops", title: "运维中心", icon: Monitor },
  ] },
  { name: "数据资产", items: [
    { path: "/datasources", title: "数据源", icon: Coin },
    { path: "/catalog", title: "数据目录", icon: Collection },
    { path: "/workbench", title: "SQL 工作台", icon: EditPen },
    { path: "/files", title: "文件", icon: Folder },
  ] },
  { name: "数据开发", items: [
    { path: "/pipelines", title: "数据管道", icon: Share },
    { path: "/flows", title: "数据集成", icon: Share },
    { path: "/datasets", title: "数据模型", icon: Collection },
    { path: "/dashboards", title: "数据看板", icon: Odometer },
    { path: "/apps", title: "数据应用", icon: Grid },
  ] },
  { name: "开放与治理", items: [
    { path: "/apis", title: "数据接口", icon: Connection },
    { path: "/grants", title: "接口授权", icon: Key },
    { path: "/webhooks", title: "事件订阅", icon: Promotion },
    { path: "/quality", title: "数据质量", icon: CircleCheck },
    { path: "/alerts", title: "告警", icon: Bell },
    { path: "/changes", title: "变更", icon: Switch },
    { path: "/tools", title: "AI 工具", icon: Connection },
  ] },
  { name: "管理", items: [
    { path: "/users", title: "用户", icon: User, adminOnly: true },
    { path: "/workspace", title: "工作区设置", icon: Setting },
    { path: "/security", title: "账号安全", icon: Lock },
    { path: "/audit", title: "审计", icon: Document, adminOnly: true },
  ] },
];

const menuGroups = computed(() => {
  const hidden = portal.value.hidden_menus || [];
  const allowed = role === "admin" ? null : portal.value.allowed_menus;
  return groups.map((g) => ({
    ...g,
    items: g.items.filter((m) => !m.adminOnly || role === "admin")
      .filter((m) => !hidden.includes(m.path)
        && (allowed == null || allowed.includes(m.path))),
  })).filter((g) => g.items.length)
    .map((g) => ({ ...g, items: g.items }));
});

const activePath = computed(() => {
  const found = groups.flatMap((g) => g.items)
    .filter((m) => route.path === m.path || route.path.startsWith(m.path + "/"))
    .sort((a, b) => b.path.length - a.path.length)[0];
  return found ? found.path : route.path;
});

const projectName = computed(() => {
  const p = projects.value.find((x) => x.id === currentProject.value);
  return p ? p.name : "Default";
});

const roleLabel = computed(() => ({ admin: "管理员", editor: "编辑者",
                                   approver: "审批者", viewer: "查看者" })[role]
  || role);

function luminance(hex) {
  const m = hex.replace("#", "").match(/.{2}/g);
  if (!m || m.length !== 3) return 0;
  return m.map((x) => parseInt(x, 16) / 255)
    .map((v) => v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)
    .reduce((sum, v, i) => sum + v * [0.2126, 0.7152, 0.0722][i], 0);
}

function safeAccent(value) {
  if (!/^#[0-9a-f]{6}$/i.test(value || "")) return "#1d4ed8";
  let rgb = value.slice(1).match(/.{2}/g).map((x) => parseInt(x, 16));
  for (let i = 0; i < 12; i += 1) {
    const hex = "#" + rgb.map((x) => x.toString(16).padStart(2, "0")).join("");
    if (1.05 / (luminance(hex) + 0.05) >= 4.5) return hex;
    rgb = rgb.map((x) => Math.max(0, Math.floor(x * 0.86)));
  }
  return "#111827";
}

const accentColor = computed(() => safeAccent(portal.value.primary_color));

const username = ref("admin");
const initial = computed(() => (username.value || "A").slice(0, 1).toUpperCase());

async function loadPortal() {
  try {
    portal.value = await api.get("/portal");
    document.title = portal.value.brand_name || "OpenDataFusion";
    const accent = accentColor.value;
    document.documentElement.style.setProperty("--odf-primary", accent);
    document.documentElement.style.setProperty("--odf-accent", accent);
    document.documentElement.style.setProperty(
      "--el-color-primary", accent);
  } catch (e) {
    /* keep defaults */
  }
}

async function loadProjects() {
  try {
    const me = await api.get("/auth/me");
    username.value = me.username || "admin";
    if (!getProject() && me.project_id) {
      setProject(me.project_id);
      currentProject.value = me.project_id;
    }
    projects.value = await api.get("/projects/mine");
  } catch (e) {
    ElMessage.error(e.message || "项目加载失败");
  }
}

async function switchProject(id) {
  try {
    await api.switchProject(id);
    ElMessage.success("已切换项目");
    window.location.reload();
  } catch (e) {
    ElMessage.error(e.message || "切换失败");
  }
}

function onUserCommand(command) {
  if (command === "logout") {
    clearSession();
    router.push("/login");
    return;
  }
  router.push("/" + command);
}

onMounted(async () => {
  await Promise.all([loadProjects(), loadPortal()]);
  try {
    await api.get("/dashboard");
    online.value = true;
  } catch (e) {
    online.value = false;
  }
});
</script>

<style scoped>
.shell {
  height: 100%;
  display: grid;
  grid-template-columns: 232px minmax(0, 1fr);
  background: var(--odf-paper);
  color: var(--odf-ink);
  --odf-primary: #1d4ed8;
  --odf-accent: var(--odf-primary);
  --odf-accent-dark: color-mix(in srgb, var(--odf-primary) 82%, #000);
  --odf-accent-soft: color-mix(in srgb, var(--odf-primary) 8%, #fff);
  --el-color-primary: var(--odf-primary);
}

.rail {
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: #fff;
  border-right: 1px solid var(--odf-rule);
}

.brand {
  height: 64px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 18px;
  border-bottom: 1px solid var(--odf-rule);
  color: var(--odf-ink);
  text-decoration: none;
}

.mark {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  background: var(--odf-ink);
  color: #fff;
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.03em;
  border-bottom: 2px solid var(--odf-primary);
}

.brand-copy b {
  display: block;
  font-size: 14px;
  font-weight: 650;
  letter-spacing: -0.02em;
  line-height: 1.15;
}

.brand-copy small {
  display: block;
  color: var(--odf-muted);
  font-size: 9px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  margin-top: 2px;
}

.rail-nav {
  flex: 1;
  overflow: auto;
  padding: 10px 0 14px;
}

.nav-group {
  margin-bottom: 6px;
}

.nav-label {
  padding: 0 18px 3px;
  color: #6b7280;
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.12em;
}

.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  height: 30px;
  padding: 0 18px;
  color: #4b5563;
  text-decoration: none;
  font-size: 12.5px;
  font-weight: 450;
  transition: background-color 100ms ease, color 100ms ease;
}

.nav-item .el-icon {
  font-size: 14px;
  color: #9ca3af;
}

.nav-item:hover {
  background: #f8f9fb;
  color: var(--odf-ink);
}

.nav-item.active {
  background: var(--odf-accent-soft);
  color: var(--odf-primary);
  font-weight: 550;
}

.nav-item.active::before {
  content: "";
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--odf-primary);
}

.nav-item.active .el-icon {
  color: var(--odf-primary);
}

.rail-foot {
  border-top: 1px solid var(--odf-rule);
  padding: 12px 18px 14px;
}

.service-state {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #4b5563;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--odf-red);
  display: inline-block;
}

.dot.on {
  background: var(--odf-green);
}

.rail-meta {
  margin-top: 7px;
  display: flex;
  gap: 10px;
  color: #6b7280;
  font-family: var(--odf-mono);
  font-size: 9px;
}

.workspace {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.topbar {
  height: 64px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 0 24px;
  background: #fff;
  border-bottom: 1px solid var(--odf-rule);
}

.identity {
  display: flex;
  align-items: baseline;
  gap: 12px;
  min-width: 0;
}

.identity h1 {
  margin: 0;
  font-size: 26px;
  font-weight: 650;
  letter-spacing: -0.035em;
  line-height: 1;
  white-space: nowrap;
}

.context {
  display: flex;
  gap: 6px;
  color: var(--odf-muted);
  font-size: 11px;
  white-space: nowrap;
}

.context .sep {
  color: #d1d5db;
}

.top-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.search-entry {
  height: 32px;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 0 11px;
  border: 1px solid var(--odf-rule);
  background: var(--odf-paper);
  color: var(--odf-muted);
  font: inherit;
  font-size: 11px;
  cursor: pointer;
}

.search-entry:hover {
  border-color: #9ca3af;
  color: var(--odf-ink);
}

.search-entry .el-icon {
  font-size: 13px;
}

.project-switch {
  width: 128px;
}

.project-switch :deep(.el-select__wrapper) {
  min-height: 30px;
}

.online {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--odf-green);
  font-size: 10px;
  white-space: nowrap;
}

.online.off {
  color: var(--odf-red);
}

.user-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 0;
  background: transparent;
  padding: 0;
  cursor: pointer;
  font: inherit;
  color: var(--odf-ink);
  text-align: left;
}

.avatar {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  background: var(--odf-ink);
  color: #fff;
  font-size: 10px;
  font-weight: 600;
}

.user-copy b {
  display: block;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.2;
}

.user-copy small {
  display: block;
  color: var(--odf-muted);
  font-size: 9px;
  line-height: 1.3;
}

.content {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

@media (max-width: 1180px) {
  .shell {
    grid-template-columns: 204px minmax(0, 1fr);
  }

  .search-entry span {
    display: none;
  }

  .search-entry {
    width: 32px;
    justify-content: center;
    padding: 0;
  }

  .context {
    display: none;
  }
}

@media (max-width: 900px) {
  .shell {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: auto minmax(0, 1fr);
  }

  .rail {
    width: 100%;
    min-width: 0;
    overflow: hidden;
    border-right: 0;
    border-bottom: 1px solid var(--odf-rule);
  }

  .brand {
    height: 52px;
  }

  .rail-nav {
    display: flex;
    gap: 2px;
    width: 100%;
    min-width: 0;
    max-width: 100%;
    padding: 6px 10px;
    overflow-x: auto;
    overflow-y: hidden;
    scrollbar-width: none;
  }

  .rail-nav::-webkit-scrollbar {
    display: none;
  }

  .nav-group {
    display: flex;
    align-items: center;
    margin: 0;
    gap: 2px;
  }

  .nav-label {
    display: none;
  }

  .nav-item {
    height: 32px;
    padding: 0 10px;
    white-space: nowrap;
  }

  .nav-item.active::before {
    left: 0;
    right: 0;
    top: auto;
    bottom: 0;
    width: auto;
    height: 2px;
  }

  .rail-foot {
    display: none;
  }

  .topbar {
    height: 56px;
    padding: 0 14px;
  }

  .identity h1 {
    font-size: 17px;
  }

  .user-copy,
  .online {
    display: none;
  }

  .project-switch {
    width: 108px;
  }
}
</style>
