<template>
  <div class="page">
    <div class="toolbar">
      <el-select v-model="status" clearable
                 :placeholder="t('alerts.allStatus')" style="width: 140px"
                 @change="load">
        <el-option value="open" :label="t('alerts.statusOpen')" />
        <el-option value="acked" :label="t('alerts.statusAcked')" />
        <el-option value="closed" :label="t('alerts.statusClosed')" />
      </el-select>
      <el-select v-model="severity" clearable
                 :placeholder="t('alerts.allSeverity')" style="width: 140px">
        <el-option value="critical" :label="t('alerts.severityCritical')" />
        <el-option value="warning" :label="t('alerts.severityWarning')" />
      </el-select>
      <div class="spacer" />
      <el-button @click="load" :loading="loading">
        {{ t("alerts.refresh") }}
      </el-button>
    </div>

    <el-card class="card" shadow="never">
      <el-table :data="filtered" size="small" v-loading="loading"
                @row-click="showDetail" row-class-name="clickable">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="severity" :label="t('alerts.colSeverity')"
                         width="90">
          <template #default="{ row }">
            <el-tag :type="row.severity === 'critical' ? 'danger' : 'warning'"
                    size="small">{{ row.severity }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" :label="t('alerts.colTitle')"
                         min-width="220" />
        <el-table-column prop="status" :label="t('alerts.colStatus')"
                         width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'open' ? 'danger' : row.status === 'acked' ? 'warning' : 'info'"
                    size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" :label="t('alerts.colTime')"
                         width="200" />
        <el-table-column :label="t('alerts.colActions')" width="180"
                         fixed="right">
          <template #default="{ row }">
            <el-button link :disabled="row.status !== 'open'"
                       @click.stop="ack(row)">
              {{ t("alerts.ack") }}
            </el-button>
            <el-button link :disabled="row.status === 'closed'"
                       @click.stop="close(row)">
              {{ t("alerts.close") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !filtered.length"
                :description="t('alerts.empty')" />
    </el-card>

    <el-drawer v-model="drawer"
               :title="current.title || t('alerts.drawerTitle')"
               size="520px">
      <el-descriptions :column="1" border>
        <el-descriptions-item :label="t('alerts.colSeverity')">
          {{ current.severity }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('alerts.colStatus')">
          {{ statusLabel(current.status) }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('alerts.colTime')">
          {{ current.created_at }}
        </el-descriptions-item>
      </el-descriptions>
      <h4>{{ t("alerts.detail") }}</h4>
      <pre class="detail">{{ JSON.stringify(current.detail, null, 2) }}</pre>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../api";
import { t } from "../i18n";

const rows = ref([]);
const loading = ref(false);
const status = ref("");
const severity = ref("");
const drawer = ref(false);
const current = ref({});

const filtered = computed(() =>
  rows.value.filter((r) => !severity.value || r.severity === severity.value)
);

function statusLabel(s) {
  return {
    open: t("alerts.statusOpen"),
    acked: t("alerts.statusAcked"),
    closed: t("alerts.statusClosed"),
  }[s] || s;
}

async function load() {
  loading.value = true;
  try {
    const q = status.value ? `?status=${status.value}` : "";
    rows.value = await api.get("/alerts" + q);
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}
function showDetail(row) {
  current.value = row;
  drawer.value = true;
}
async function ack(row) {
  try {
    await api.post(`/alerts/${row.id}/ack`);
    await load();
    ElMessage.success(t("alerts.ackedMsg"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}
async function close(row) {
  try {
    await ElMessageBox.confirm(t("alerts.closeConfirm"),
                               t("alerts.closeTitle"),
                               { type: "warning" });
    await api.post(`/alerts/${row.id}/close`);
    await load();
    ElMessage.success(t("alerts.closedMsg"));
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}
onMounted(load);
</script>

<style scoped>
.card {
  border-radius: 0;
  border: 1px solid #e5e7eb;
}
.detail {
  background: #0f172a;
  color: #e2e8f0;
  padding: 14px;
  border-radius: 0;
  font-size: 12px;
  overflow: auto;
}
:deep(.clickable) {
  cursor: pointer;
}
</style>
