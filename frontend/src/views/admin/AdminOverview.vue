<template>
  <div class="admin-page">
    <section class="tiles">
      <stat-tile icon="user" :label="t('adm.ovUsers')"
                 :value="`${data.users.active}/${data.users.total}`"
                 :hint="t('adm.ovUsersHint')" />
      <stat-tile icon="workspace" :label="t('adm.ovProjects')"
                 :value="data.projects.total"
                 :hint="`${data.projects.active} ${t('adm.ovActive')}`" />
      <stat-tile icon="dataset" :label="t('adm.ovAssets')"
                 :value="data.assets.total"
                 :hint="t('adm.ovAssetsHint')" />
      <stat-tile icon="job" :label="t('adm.ovQueue')"
                 :value="data.jobs.queued + data.jobs.running"
                 :tone="data.jobs.failed_24h ? 'danger' : ''"
                 :hint="`${data.jobs.failed_24h} ${t('adm.ovFailed')}`" />
      <stat-tile icon="alert" :label="t('adm.ovAlerts')"
                 :value="data.alerts.open"
                 :tone="data.alerts.open ? 'warning' : ''" />
    </section>

    <div class="grid">
      <el-card shadow="never">
        <template #header><b>{{ t("adm.ovRecent") }}</b></template>
        <el-table :data="audit" size="small">
          <el-table-column prop="actor" :label="t('adm.actor')" width="130" />
          <el-table-column prop="action" :label="t('adm.action')"
                           min-width="170" />
          <el-table-column prop="target" :label="t('adm.target')" width="110" />
          <el-table-column :label="t('adm.time')" width="170">
            <template #default="{ row }">{{ fmt(row.at) }}</template>
          </el-table-column>
        </el-table>
      </el-card>
      <el-card shadow="never">
        <template #header>
          <div class="card-head">
            <b>{{ t("adm.mcpActivity") }}</b>
            <span class="muted">{{ data.mcp?.calls_24h || 0 }} / 24h</span>
          </div>
        </template>
        <el-table :data="data.mcp?.recent || []" size="small">
          <el-table-column prop="action" :label="t('adm.action')" />
          <el-table-column prop="target" :label="t('adm.target')" width="120" />
          <el-table-column :label="t('adm.time')" width="160">
            <template #default="{ row }">{{ fmt(row.at) }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!(data.mcp?.recent || []).length"
                  :description="t('adm.mcpEmpty')" :image-size="50" />
      </el-card>
      <el-card shadow="never">
        <template #header><b>{{ t("adm.ovShortcuts") }}</b></template>
        <div class="links">
          <router-link v-for="link in links" :key="link.path" :to="link.path"
                       class="link">
            <entity-icon :type="link.icon" :size="22" />
            <span>{{ t(link.label) }}</span>
          </router-link>
        </div>
        <el-alert v-if="announcement" :title="t('adm.announcement')"
                  :description="announcement" type="info" :closable="false"
                  style="margin-top: 14px" />
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { api, errMsg } from "../../api";
import { fmtDate, t } from "../../i18n";
import { ElMessage } from "element-plus";
import StatTile from "../../components/StatTile.vue";
import EntityIcon from "../../components/EntityIcon.vue";

const data = reactive({
  users: { total: 0, active: 0 }, projects: { total: 0, active: 0 },
  assets: { total: 0 }, jobs: { queued: 0, running: 0, failed_24h: 0 },
  alerts: { open: 0 }, mcp: { calls_24h: 0, recent: [] },
});
const audit = ref([]);
const announcement = ref("");
const links = [
  { path: "/admin/users", label: "admin.users", icon: "user" },
  { path: "/admin/projects", label: "admin.projects", icon: "workspace" },
  { path: "/admin/identity", label: "admin.identity", icon: "security" },
  { path: "/admin/platform", label: "admin.platform", icon: "engine" },
];
const fmt = fmtDate;

onMounted(async () => {
  try {
    Object.assign(data, await api.get("/platform/overview"));
    audit.value = await api.get("/audit?limit=8");
    const settings = await api.get("/platform/settings");
    announcement.value = settings.brand?.announcement || "";
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
});
</script>

<style scoped>
.tiles {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.grid {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
  gap: 14px;
}
.links { display: flex; flex-direction: column; gap: 8px; }
.link {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  color: #334155;
  text-decoration: none;
  font-size: 13px;
}
.link:hover { border-color: #bfd3ff; color: #1d4ed8; }
@media (max-width: 1100px) {
  .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .grid { grid-template-columns: 1fr; }
}
</style>
