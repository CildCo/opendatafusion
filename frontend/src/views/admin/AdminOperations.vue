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
weft rotate-jwt-secret
weft rotate-fernet --old-key ... --new-key ...</pre>
        <p class="muted">{{ t("adm.maintenanceHint") }}</p>
      </el-card>
      <el-card shadow="never">
        <template #header><b>{{ t("adm.runtime") }}</b></template>
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item :label="t('adm.version')">
            {{ runtime.version || "-" }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('adm.license')">
            {{ runtime.license || "-" }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('adm.database')">
            {{ runtime.database || "-" }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('adm.scheduler')">
            {{ runtime.scheduler || "-" }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('adm.workers')">
            {{ runtime.queue?.workers ?? 0 }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card shadow="never">
        <template #header><b>{{ t("adm.backup") }}</b></template>
        <p class="muted">{{ t("adm.backupIntro") }}</p>
        <div class="backup-actions">
          <el-button type="primary" @click="downloadBackup">
            {{ t("adm.backupExport") }}
          </el-button>
          <el-upload :show-file-list="false" :http-request="restoreBackup">
            <el-button>{{ t("adm.backupRestore") }}</el-button>
          </el-upload>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><b>{{ t("adm.retention") }}</b></template>
        <p class="muted">{{ t("adm.retentionIntro") }}</p>
        <el-table :data="retentionRows" size="small">
          <el-table-column prop="key" :label="t('adm.retentionKey')" />
          <el-table-column prop="days" :label="t('adm.retentionDays')"
                           width="110" />
          <el-table-column prop="matched" :label="t('adm.retentionMatched')"
                           width="110" />
        </el-table>
        <div class="backup-actions">
          <el-button @click="pruneRetention(false)">
            {{ t("adm.retentionPreview") }}
          </el-button>
          <el-button type="primary" @click="pruneRetention(true)">
            {{ t("adm.retentionApply") }}
          </el-button>
          <el-button @click="pruneRetention(true, true)">
            {{ t("adm.retentionArchive") }}
          </el-button>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><b>{{ t("adm.doctor") }}</b></template>
        <div class="flag-row">
          <el-tag :type="doctor.ok ? 'success' : 'danger'" size="small">
            {{ doctor.ok ? t("adm.doctorOk") : t("adm.doctorBad") }}
          </el-tag>
          <el-button link @click="loadDoctor">{{ t("adm.recheck") }}</el-button>
        </div>
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item :label="t('adm.doctorRevision')">
            {{ doctor.migrations?.current || "-" }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('adm.doctorHead')">
            {{ doctor.migrations?.head || "-" }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('adm.doctorDisk')">
            {{ doctor.disk?.free_mb ?? "-" }} MB
          </el-descriptions-item>
          <el-descriptions-item v-if="doctor.migrations?.pending"
                                :label="t('adm.doctorPending')">
            {{ t("adm.doctorBad") }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card shadow="never">
        <template #header><b>{{ t("adm.auditDelivery") }}</b></template>
        <el-form label-width="130px" size="small">
          <el-form-item :label="t('adm.auditRetention')">
            <el-input-number v-model="audit.retention_days" :min="0"
                             :max="3650" controls-position="right" />
          </el-form-item>
          <el-form-item :label="t('adm.siemUrl')">
            <el-input v-model="audit.siem_url"
                      placeholder="https://siem.example/ingest" />
          </el-form-item>
          <el-form-item :label="t('adm.siemToken')">
            <el-input v-model="audit.siem_token" type="password"
                      show-password :placeholder="t('ds.keepPassword')" />
          </el-form-item>
          <el-form-item :label="t('adm.alertWebhook')">
            <el-input v-model="alerts.webhook_url"
                      placeholder="https://hooks.slack.com/services/..." />
          </el-form-item>
          <el-button :loading="auditSaving" @click="saveAudit">
            {{ t("adm.save") }}
          </el-button>
        </el-form>
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
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg, getToken } from "../../api";
import { t } from "../../i18n";
import StatTile from "../../components/StatTile.vue";
import StatusDot from "../../components/StatusDot.vue";

const summary = ref({});
const features = ref({});
const runtime = ref({});
const audit = reactive({ retention_days: 0, siem_url: "", siem_token: "" });
const alerts = reactive({ webhook_url: "" });
const auditSaving = ref(false);
const retention = ref({ policies: {}, counts: {} });
const doctor = ref({});
const retentionRows = computed(() =>
  Object.entries(retention.value.counts || {}).map(([key, matched]) => ({
    key,
    days: (retention.value.policies || {})[key] ?? "-",
    matched,
  })));

async function downloadBackup() {
  try {
    const response = await fetch("/api/v1/platform/backup/export", {
      headers: { Authorization: "Bearer " + getToken() },
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const blob = await response.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "odf-backup.json";
    a.click();
    URL.revokeObjectURL(a.href);
    ElMessage.success(t("adm.backupDownloaded"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function restoreBackup({ file }) {
  try {
    await ElMessageBox.prompt(t("adm.restoreConfirm"), t("adm.backupRestore"),
      { inputPlaceholder: "RESTORE", type: "warning" });
  } catch (e) {
    return;
  }
  const form = new FormData();
  form.append("file", file);
  form.append("confirm", "RESTORE");
  try {
    const response = await fetch("/api/v1/platform/backup/restore", {
      method: "POST",
      headers: { Authorization: "Bearer " + getToken() },
      body: form,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `HTTP ${response.status}`);
    }
    ElMessage.success(t("adm.restoreDone"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function loadRetention() {
  try {
    retention.value = await api.get("/platform/retention");
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function loadDoctor() {
  try {
    doctor.value = await api.get("/platform/doctor");
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function pruneRetention(apply, archive = false) {
  try {
    if (apply) {
      await ElMessageBox.confirm(t("adm.retentionConfirm"),
                                 t("adm.retentionApply"),
                                 { type: "warning" });
    }
    const result = await api.post("/platform/retention/prune",
                                  { apply, archive });
    const removed = Object.values(result).reduce(
      (sum, row) => sum + (row.removed || 0), 0);
    const matched = Object.values(result).reduce(
      (sum, row) => sum + (row.matched || 0), 0);
    ElMessage.success(apply
      ? t("adm.retentionDone") + ` (${removed})`
      : `${matched}`);
    await loadRetention();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

async function saveAudit() {
  auditSaving.value = true;
  try {
    await api.put("/platform/settings", {
      audit: { retention_days: audit.retention_days || 0,
               siem_url: audit.siem_url || "",
               siem_token: audit.siem_token || "" },
      alerts: { webhook_url: alerts.webhook_url || "" },
    });
    ElMessage.success(t("adm.saved"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    auditSaving.value = false;
  }
}

onMounted(async () => {
  try {
    summary.value = await api.get("/platform/overview");
    const doc = await api.get("/platform/settings");
    features.value = doc.features || {};
    runtime.value = await api.get("/platform/runtime");
    await loadRetention();
    await loadDoctor();
    Object.assign(audit, doc.audit || {});
    Object.assign(alerts, doc.alerts || {});
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
