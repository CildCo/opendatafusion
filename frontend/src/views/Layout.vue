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
          <div class="nav-label">{{ t(group.key) }}</div>
          <router-link v-for="m in group.items" :key="m.path" :to="m.path"
                       class="nav-item"
                       :class="{ active: activePath === m.path }">
            <el-icon><component :is="m.icon" /></el-icon>
            <span>{{ t(m.key) }}</span>
          </router-link>
        </section>
      </nav>

      <div class="rail-foot">
        <router-link v-if="platformAdmin" to="/admin/overview"
                     class="rail-admin">
          <el-icon><Setting /></el-icon>
          <span>{{ t("admin.console") }}</span>
        </router-link>
        <div class="service-state">
          <span class="dot" :class="{ on: online }"></span>
          {{ online ? t("top.serviceOnline") : t("top.serviceOffline") }}
        </div>
        <div class="rail-meta">
          <span>API 18080</span>
          <span>MCP 18082</span>
          <span>v{{ appVersion }}</span>
        </div>
      </div>
    </aside>

    <div class="workspace">
      <header class="topbar">
        <div class="identity">
          <span v-if="pageGroup" class="crumb-group">{{ pageGroup }} /</span>
          <h1>{{ pageTitle }}</h1>
          <div class="context">
            <span>{{ projectName }}</span>
            <span class="sep">/</span>
            <span>{{ roleLabel }}</span>
          </div>
        </div>
        <div class="top-actions">
          <button class="search-entry" type="button"
                  @click="paletteOpen = true">
            <el-icon><Search /></el-icon>
            <span>{{ t("top.search") }}</span>
            <kbd class="search-kbd">Ctrl K</kbd>
          </button>
          <el-button size="small" text @click="toggleLocale">
            {{ t("top.language") }}
          </el-button>
          <el-select :model-value="currentProject" class="project-switch"
                     size="small" @change="switchProject">
            <el-option v-for="p in projects" :key="p.id" :value="p.id"
                       :label="p.name" />
          </el-select>
          <div class="online" :class="{ off: !online }">
            <span class="dot" :class="{ on: online }"></span>
            {{ online ? t("top.online") : t("top.offline") }}
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
                <el-dropdown-item v-if="platformAdmin" command="admin">
                  {{ t("admin.console") }}
                </el-dropdown-item>
                <el-dropdown-item command="security">{{ t("top.security") }}</el-dropdown-item>
                <el-dropdown-item command="workspace">{{ t("top.workspace") }}</el-dropdown-item>
                <el-dropdown-item command="logout" divided>{{ t("top.logout") }}</el-dropdown-item>
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
  <command-palette v-model="paletteOpen" />
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Search, Setting } from "@element-plus/icons-vue";
import { MENU_GROUPS, MENU_ITEMS } from "../menu";
import { ElMessage } from "element-plus";
import { api, clearSession, getPlatformAdmin, getProject, getRole,
         setPlatformAdmin, setProject, setRole } from "../api";
import { t, toggleLocale } from "../i18n";
import CommandPalette from "../components/CommandPalette.vue";
import { pushRecent } from "../recent";

const route = useRoute();
const router = useRouter();
const paletteOpen = ref(false);
const appVersion = typeof __APP_VERSION__ !== "undefined" ? __APP_VERSION__ : "dev";
const role = ref(getRole() || "viewer");
const platformAdmin = ref(getPlatformAdmin());
const online = ref(true);
const projects = ref([]);
const currentProject = ref(getProject());
const portal = ref({ brand_name: "OpenDataFusion", primary_color: "#1d4ed8",
                     hidden_menus: [], allowed_menus: null });

const groups = MENU_GROUPS;
const FEATURE_PATHS = {"/workbench": "workbench", "/cdc": "cdc",
                       "/tools": "tools", "/apps": "apps",
                       "/dashboards": "dashboards"};

const menuGroups = computed(() => {
  const hidden = portal.value.hidden_menus || [];
  const allowed = role.value === "admin" ? null : portal.value.allowed_menus;
  const features = portal.value.features || {};
  return groups.map((g) => ({
    ...g,
    items: g.items.filter((m) => !m.adminOnly || platformAdmin.value)
      .filter((m) => !hidden.includes(m.path)
        && (allowed == null || allowed.includes(m.path)))
      .filter((m) => features[FEATURE_PATHS[m.path]] !== false),
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

const roleLabel = computed(() =>
  t("role." + (["admin", "editor", "approver", "viewer"].includes(role.value)
    ? role.value : "viewer")));

const pageTitle = computed(() => {
  const found = groups.flatMap((g) => g.items).find(
    (m) => route.path === m.path || route.path.startsWith(m.path + "/"));
  return found ? t(found.key) : (route.meta.title || "");
});

const pageGroup = computed(() => {
  for (const group of groups) {
    if (group.items.some((m) => route.path === m.path
        || route.path.startsWith(m.path + "/"))) {
      return t(group.key);
    }
  }
  return "";
});

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
    role.value = me.role || "viewer";
    setRole(me.role);
    platformAdmin.value = !!me.platform_admin;
    setPlatformAdmin(me.platform_admin);
    if (!getProject() && me.project_id) {
      setProject(me.project_id);
      currentProject.value = me.project_id;
    }
    projects.value = await api.get("/projects/mine");
  } catch (e) {
    ElMessage.error(e.message || t("layout.projectError"));
  }
}

async function switchProject(id) {
  try {
    await api.switchProject(id);
    ElMessage.success(t("layout.switched"));
    window.location.reload();
  } catch (e) {
    ElMessage.error(e.message || t("layout.switchError"));
  }
}

function onUserCommand(command) {
  if (command === "admin") {
    router.push("/admin/overview");
    return;
  }
  if (command === "logout") {
    clearSession();
    router.push("/login");
    return;
  }
  router.push("/" + command);
}

watch(() => route.fullPath, (path) => {
  if (path.startsWith("/login")) return;
  const item = MENU_ITEMS.find((m) => path === m.path
    || path.startsWith(m.path + "/"));
  if (item) pushRecent({ type: "page", route: path, key: item.key });
}, { immediate: true });

let chord = false;
let chordTimer = null;

function onKeydown(event) {
  const target = event.target;
  const typing = target && (target.tagName === "INPUT"
    || target.tagName === "TEXTAREA" || target.isContentEditable);
  if ((event.ctrlKey || event.metaKey)
      && event.key.toLowerCase() === "k") {
    event.preventDefault();
    paletteOpen.value = !paletteOpen.value;
    return;
  }
  if (typing || event.ctrlKey || event.metaKey || event.altKey) return;
  if (event.key === "/") {
    event.preventDefault();
    paletteOpen.value = true;
    return;
  }
  if (event.key === "g") {
    chord = true;
    clearTimeout(chordTimer);
    chordTimer = setTimeout(() => { chord = false; }, 900);
    return;
  }
  if (!chord) return;
  const routes = {
    d: "/dashboard", o: "/ops", c: "/catalog", f: "/flows",
    p: "/pipelines", q: "/quality", a: "/alerts", u: "/users",
    i: "/interfaces", w: "/workbench",
  };
  if (routes[event.key]) {
    event.preventDefault();
    router.push(routes[event.key]);
  }
  chord = false;
}

onMounted(async () => {
  window.addEventListener("keydown", onKeydown);
  await Promise.all([loadProjects(), loadPortal()]);
  try {
    await api.get("/dashboard");
    online.value = true;
  } catch (e) {
    online.value = false;
  }
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", onKeydown);
  clearTimeout(chordTimer);
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
  color: #64748b;
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

.rail-admin {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  padding: 7px 9px;
  border: 1px solid var(--odf-rule);
  border-radius: 6px;
  color: #374151;
  font-size: 12px;
  font-weight: 500;
  text-decoration: none;
}

.rail-admin:hover {
  border-color: var(--odf-primary);
  color: var(--odf-primary);
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

.crumb-group {
  font-size: 11px;
  color: #94a3b8;
  font-weight: 500;
  letter-spacing: 0.02em;
  white-space: nowrap;
}

.identity {
  display: flex;
  align-items: baseline;
  gap: 8px;
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

.search-entry kbd {
  font-size: 10px;
  color: #94a3b8;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  padding: 1px 4px;
  margin-left: 6px;
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
  border-color: #64748b;
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
