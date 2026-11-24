<template>
  <div class="page">
    <page-header icon="change" :title="t('menu.changes')"
                 :intro="t('changes.intro')" />
    <div class="toolbar">
      <el-select v-model="status" clearable
                 :placeholder="t('changes.allStatus')" style="width: 150px"
                 @change="load">
        <el-option value="proposed" :label="t('changes.statusProposed')" />
        <el-option value="applied" :label="t('changes.statusApplied')" />
        <el-option value="withdrawn" :label="t('changes.statusWithdrawn')" />
      </el-select>
      <div class="spacer" />
      <el-button @click="load" :loading="loading">
        {{ t("changes.refresh") }}
      </el-button>
    </div>

    <el-card class="card" shadow="never">
      <el-table :data="rows" size="small" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="action" :label="t('changes.colAction')"
                         width="170">
          <template #default="{ row }">{{ actionLabel(row.action) }}</template>
        </el-table-column>
        <el-table-column :label="t('changes.colTarget')" width="200">
          <template #default="{ row }">
            <span v-if="row.target_name">{{ row.target_name }}</span>
            <span v-else>{{ row.target }}</span>
            <span class="muted"> #{{ row.target }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="actor" :label="t('changes.colActor')"
                         width="130" />
        <el-table-column prop="status" :label="t('changes.colStatus')"
                         width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('changes.colTime')" width="200">
          <template #default="{ row }">{{ fmtDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column :label="t('changes.colActions')" width="320"
                         fixed="right">
          <template #default="{ row }">
            <el-button link :disabled="row.status !== 'proposed'" @click="approve(row)">
              {{ t("changes.approve") }}
            </el-button>
            <el-button link :disabled="row.status !== 'proposed'" @click="apply(row)">
              {{ t("changes.apply") }}
            </el-button>
            <el-button link :disabled="row.status !== 'proposed'" @click="approveAndApply(row)">
              {{ t("changes.approveAndApply") }}
            </el-button>
            <el-button link type="danger" :disabled="row.status !== 'proposed'"
                       @click="withdraw(row)">
              {{ t("changes.withdraw") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !rows.length"
                :description="t('changes.empty')" />
    </el-card>

  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../api";
import { fmtDate, t } from "../i18n";
import PageHeader from "../components/PageHeader.vue";

const rows = ref([]);
const loading = ref(false);
const status = ref("");
const tokens = reactive({});

function actionLabel(a) {
  return {
    publish_metric: t("changes.actionPublishMetric"),
    rollback_metric: t("changes.actionRollbackMetric"),
    publish_dataset: t("changes.actionPublishDataset"),
    rollback_dataset: t("changes.actionRollbackDataset"),
    publish_pipeline: t("changes.actionPublishPipeline"),
    pause_pipeline: t("changes.actionPausePipeline"),
    resume_pipeline: t("changes.actionResumePipeline"),
    publish_api: t("changes.actionPublishApi"),
    rollback_api: t("changes.actionRollbackApi"),
    enable_api: t("changes.actionEnableApi"),
    revoke_api: t("changes.actionRevokeApi"),
    publish_dashboard: t("changes.actionPublishDashboard"),
    publish_app: t("changes.actionPublishApp"),
  }[a] || a;
}

async function load() {
  loading.value = true;
  try {
    const q = status.value ? `?status=${status.value}` : "";
    rows.value = await api.get("/changes" + q);
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

function statusType(s) {
  return s === "applied" ? "success" : s === "withdrawn" ? "info" : "warning";
}

function statusLabel(s) {
  return {
    applied: t("changes.statusApplied"),
    proposed: t("changes.statusProposed"),
    withdrawn: t("changes.statusWithdrawn"),
  }[s] || s;
}

async function withdraw(row) {
  try {
    await ElMessageBox.confirm(
      t("changes.withdrawConfirm").replace("{action}", actionLabel(row.action)),
      t("changes.withdrawTitle"), { type: "warning" });
    await api.post(`/changes/${row.id}/withdraw`);
    await load();
    ElMessage.success(t("changes.withdrawnMsg"));
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

async function approve(row) {
  try {
    const a = await api.post(`/changes/${row.id}/approve`, {});
    tokens[row.id] = a.approval_token;
    ElMessage.success(t("changes.approvedCanApply"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function apply(row) {
  const token = tokens[row.id];
  if (!token) {
    ElMessage.warning(t("changes.approveFirst"));
    return;
  }
  try {
    await api.post(`/changes/${row.id}/apply?approval_token=${encodeURIComponent(token)}`, {});
    delete tokens[row.id];
    await load();
    ElMessage.success(t("changes.appliedMsg"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function approveAndApply(row) {
  try {
    const a = await api.post(`/changes/${row.id}/approve`, {});
    await api.post(`/changes/${row.id}/apply?approval_token=${encodeURIComponent(a.approval_token)}`, {});
    await load();
    ElMessage.success(t("changes.approvedAndApplied"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

onMounted(load);
</script>

<style scoped>
.card {
  border-radius: 12px;
  border: 1px solid #e5e7eb;
}
</style>
