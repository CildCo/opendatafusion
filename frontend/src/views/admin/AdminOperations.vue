<template>
  <div class="admin-page">
    <section class="tiles">
      <stat-tile icon="job" :label="t('adm.queue')"
                 :value="summary.jobs?.queued ?? 0" />
      <stat-tile icon="job" :label="t('adm.running')"
                 :value="summary.jobs?.running ?? 0" />
      <stat-tile icon="alert" :label="t('adm.failed')"
                 :value="summary.jobs?.failed_24h ?? 0"
                 :tone="summary.jobs?.failed_24h ? 'danger' : ''" />
      <stat-tile icon="alert" :label="t('adm.openAlerts')"
                 :value="summary.alerts?.open ?? 0"
                 :tone="summary.alerts?.open ? 'warning' : ''" />
    </section>

    <div class="grid">
      <el-card shadow="never">
        <template #header><b>{{ t("adm.maintenance") }}</b></template>
        <p class="muted">{{ t("adm.maintenanceIntro") }}</p>
        <pre class="code">scripts/backup.sh             # database + file backup
scripts/restore.sh &lt;archive&gt;  # restore (stops writers first)
deploy/systemd/odf-backup.timer
python -m odf.cli rotate-jwt-secret
python -m odf.cli rotate-fernet --old-key ... --new-key ...</pre>
        <p class="muted">{{ t("adm.maintenanceHint") }}</p>
      </el-card>
      <el-card shadow="never">
        <template #header><b>{{ t("adm.featureState") }}</b></template>
        <div v-for="(enabled, key) in features" :key="key" class="flag-row">
          <span>{{ key }}</span>
          <status-dot :status="enabled"
                      :label="enabled ? t('adm.enabled') : t('adm.disabled')" />
        </div>
        <el-button link type="primary" @click="$router.push('/admin/appearance')">
          {{ t("adm.editFeatures") }}
        </el-button>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { api, errMsg } from "../../api";
import { t } from "../../i18n";
import StatTile from "../../components/StatTile.vue";
import StatusDot from "../../components/StatusDot.vue";

const summary = ref({});
const features = ref({});

onMounted(async () => {
  try {
    summary.value = await api.get("/platform/overview");
    const doc = await api.get("/platform/settings");
    features.value = doc.features || {};
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
});
</script>

<style scoped>
.tiles {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.muted { color: #64748b; font-size: 12px; line-height: 1.6; }
.code {
  background: #0f172a;
  color: #e2e8f0;
  padding: 12px 14px;
  border-radius: 8px;
  font-size: 12px;
  overflow: auto;
}
.flag-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 13px;
  color: #334155;
}
@media (max-width: 900px) {
  .tiles { grid-template-columns: repeat(2, 1fr); }
  .grid { grid-template-columns: 1fr; }
}
</style>
