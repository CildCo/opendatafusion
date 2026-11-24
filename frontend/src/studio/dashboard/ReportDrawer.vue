<template>
  <el-drawer :model-value="modelValue" :title="t('report.title')"
             size="620px"
             @update:model-value="$emit('update:modelValue', $event)">
    <el-alert v-if="!published" type="warning" :closable="false"
              :title="t('report.notPublished')" />
    <template v-else>
      <el-form label-width="96px" size="small">
        <el-form-item :label="t('report.cron')">
          <el-input v-model="cron" :placeholder="t('report.cronPlaceholder')" />
          <div class="hint">{{ t("report.cronHint") }}</div>
        </el-form-item>
        <el-form-item :label="t('report.enabled')">
          <el-switch v-model="enabled" />
        </el-form-item>
      </el-form>
      <div class="actions">
        <el-button size="small" type="primary" :loading="saving"
                   @click="save">{{ t("report.save") }}</el-button>
        <el-button size="small" :disabled="!schedule" :loading="running"
                   @click="runNow">{{ t("report.runNow") }}</el-button>
        <el-button size="small" type="danger" :disabled="!schedule"
                   @click="remove">{{ t("report.delete") }}</el-button>
      </div>
      <template v-if="schedule">
        <el-descriptions :column="1" border size="small"
                         style="margin-top: 12px">
          <el-descriptions-item :label="t('report.lastRun')">
            {{ fmt(schedule.last_run_at) }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('report.lastStatus')">
            <el-tag v-if="schedule.last_status" size="small"
                    :type="schedule.last_status === 'ok'
                      ? 'success' : 'danger'">
              {{ schedule.last_status }}
            </el-tag>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item :label="t('report.file')">
            <el-button v-if="schedule.last_file_id" link type="primary"
                       @click="download">
              {{ t("report.download") }}
            </el-button>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item v-if="schedule.last_error"
                                :label="t('report.error')">
            {{ schedule.last_error }}
          </el-descriptions-item>
        </el-descriptions>
        <h4>{{ t("report.runs") }}</h4>
        <el-table :data="runs" size="small">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="status" :label="t('report.status')"
                           width="100" />
          <el-table-column :label="t('report.time')" min-width="160">
            <template #default="{ row }">{{ fmt(row.created_at) }}</template>
          </el-table-column>
          <el-table-column :label="t('report.error')" min-width="160">
            <template #default="{ row }">
              <span class="muted">{{ row.error || "-" }}</span>
            </template>
          </el-table-column>
        </el-table>
      </template>
      <el-empty v-else :description="t('report.none')" :image-size="60" />
    </template>
  </el-drawer>
</template>

<script setup>
import { ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../../api";
import { fmtDate, t } from "../../i18n";

const props = defineProps({
  modelValue: Boolean,
  assetId: { type: Number, required: true },
  published: Boolean,
});
defineEmits(["update:modelValue"]);
const cron = ref("0 0 8 * * *");
const enabled = ref(true);
const schedule = ref(null);
const runs = ref([]);
const saving = ref(false);
const running = ref(false);

function fmt(value) {
  return value ? fmtDate(value) : "-";
}

async function load() {
  if (!props.assetId) return;
  try {
    const r = await api.get(`/dashboards/${props.assetId}/report`);
    schedule.value = r.schedule;
    runs.value = r.runs || [];
    if (r.schedule) {
      cron.value = r.schedule.cron;
      enabled.value = r.schedule.enabled;
    }
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function save() {
  saving.value = true;
  try {
    await api.put(`/dashboards/${props.assetId}/report`, {
      cron: cron.value, enabled: enabled.value,
    });
    ElMessage.success(t("report.saved"));
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

async function runNow() {
  running.value = true;
  try {
    await api.post(`/dashboards/${props.assetId}/report/run`, {});
    ElMessage.success(t("report.queued"));
    await load();
    for (let i = 0; i < 20; i += 1) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      await load();
      if (runs.value[0]?.status === "success"
          || runs.value[0]?.status === "failed") break;
    }
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    running.value = false;
  }
}

async function remove() {
  try {
    await ElMessageBox.confirm(t("report.deleteConfirm"),
                               t("report.deleteTitle"),
                               { type: "warning" });
    await api.del(`/dashboards/${props.assetId}/report`);
    schedule.value = null;
    runs.value = [];
    ElMessage.success(t("report.deleted"));
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

async function download() {
  try {
    await api.download(`/files/${schedule.value.last_file_id}/download`,
                       `dashboard-report-${props.assetId}.csv`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

watch(() => props.modelValue, (open) => {
  if (open) load();
});
</script>

<style scoped>
.hint { font-size: 12px; color: #6b7280; margin-top: 4px; }
.actions { display: flex; gap: 8px; }
h4 { margin: 16px 0 8px; font-size: 13px; }
.muted { color: #6b7280; }
</style>
