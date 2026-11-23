<template>
  <div class="admin-shell">
    <aside class="admin-rail">
      <a class="admin-brand" href="#/admin/overview">
        <span class="mark">OD</span>
        <span class="name">{{ brand }}</span>
        <span class="tag">{{ t("admin.console") }}</span>
      </a>
      <nav class="admin-nav">
        <router-link v-for="item in items" :key="item.path" :to="item.path"
                     class="admin-link"
                     :class="{ active: $route.path === item.path }">
          <entity-icon :type="item.icon" :size="20" />
          <span>{{ t(item.label) }}</span>
        </router-link>
      </nav>
      <div class="admin-foot">
        <a href="#/dashboard" class="back">{{ t("admin.back") }}</a>
      </div>
    </aside>
    <div class="admin-main">
      <header class="admin-top">
        <div>
          <div class="crumb">{{ t("admin.console") }}</div>
          <h1>{{ title }}</h1>
        </div>
        <div class="admin-user">
          <span class="who">{{ username }}</span>
          <el-button size="small" text @click="toggleLocale">
            {{ t("top.language") }}
          </el-button>
        </div>
      </header>
      <main class="admin-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, clearSession, getPlatformAdmin } from "../../api";
import { t, toggleLocale } from "../../i18n";
import EntityIcon from "../../components/EntityIcon.vue";

const route = useRoute();
const router = useRouter();
const brand = ref("OpenDataFusion");
const username = ref("admin");
const items = [
  { path: "/admin/overview", label: "admin.overview", icon: "page" },
  { path: "/admin/users", label: "admin.users", icon: "user" },
  { path: "/admin/projects", label: "admin.projects", icon: "workspace" },
  { path: "/admin/identity", label: "admin.identity", icon: "security" },
  { path: "/admin/appearance", label: "admin.appearance", icon: "tool" },
  { path: "/admin/platform", label: "admin.platform", icon: "engine" },
  { path: "/admin/operations", label: "admin.operations", icon: "alert" },
  { path: "/admin/audit", label: "admin.audit", icon: "audit" },
];

const title = computed(() => {
  const found = items.find((item) => route.path.startsWith(item.path));
  return found ? t(found.label) : t("admin.console");
});

onMounted(async () => {
  if (!getPlatformAdmin()) {
    router.replace("/dashboard");
    return;
  }
  try {
    const [portal, me] = await Promise.all([
      api.get("/platform/public"), api.get("/auth/me"),
    ]);
    brand.value = portal?.brand?.name || "OpenDataFusion";
    username.value = me.username || "admin";
    const color = portal?.brand?.color;
    if (color) {
      document.documentElement.style.setProperty("--odf-primary", color);
      document.documentElement.style.setProperty("--odf-accent", color);
      document.documentElement.style.setProperty("--el-color-primary", color);
    }
  } catch {
    clearSession();
    router.replace("/login");
  }
});
</script>

<style scoped>
.admin-shell {
  display: grid;
  grid-template-columns: 236px minmax(0, 1fr);
  height: 100%;
  background: #f6f7f9;
}
.admin-rail {
  background: #0f172a;
  color: #e2e8f0;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.admin-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 18px 14px;
  color: #fff;
  text-decoration: none;
  border-bottom: 1px solid #1e293b;
}
.admin-brand .mark {
  width: 30px;
  height: 30px;
  background: var(--odf-accent, #1d4ed8);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 12px;
  border-radius: 6px;
}
.admin-brand .name { font-weight: 650; font-size: 14px; }
.admin-brand .tag {
  margin-left: auto;
  font-size: 10px;
  color: #94a3b8;
  border: 1px solid #334155;
  border-radius: 999px;
  padding: 2px 8px;
}
.admin-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 12px 10px;
  overflow: auto;
}
.admin-link {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  color: #cbd5e1;
  text-decoration: none;
  border-radius: 8px;
  font-size: 13px;
}
.admin-link:hover { background: #1e293b; color: #fff; }
.admin-link.active { background: #1d4ed8; color: #fff; }
.admin-foot {
  margin-top: auto;
  padding: 14px 18px;
  border-top: 1px solid #1e293b;
}
.admin-foot .back { color: #94a3b8; font-size: 12px; text-decoration: none; }
.admin-main { min-width: 0; display: flex; flex-direction: column; }
.admin-top {
  height: 68px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 26px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
}
.admin-top .crumb { color: #94a3b8; font-size: 11px; }
.admin-top h1 { margin: 2px 0 0; font-size: 18px; color: #0f172a; }
.admin-user { display: flex; align-items: center; gap: 10px; }
.admin-user .who { font-size: 12px; color: #475569; }
.admin-content { padding: 20px 26px 30px; overflow: auto; }
@media (max-width: 900px) {
  .admin-shell { grid-template-columns: 64px minmax(0, 1fr); }
  .admin-brand .name, .admin-brand .tag, .admin-link span,
  .admin-foot .back { display: none; }
  .admin-link { justify-content: center; }
}
</style>
