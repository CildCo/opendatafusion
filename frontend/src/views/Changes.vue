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
      <el-button type="primary" @click="openCreate">
        {{ t("changes.create") }}
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

    <el-dialog v-model="dialog" :title="t('changes.dialogTitle')"
               width="560px">
      <el-form label-width="90px">
        <el-form-item :label="t('changes.action')" required>
          <el-select v-model="form.action" style="width: 100%" @change="onAction">
            <el-option value="run_flow" :label="t('changes.actionRunFlow')" />
            <el-option value="pause_flow" :label="t('changes.actionPauseFlow')" />
            <el-option value="resume_flow" :label="t('changes.actionResumeFlow')" />
            <el-option value="rollback_flow" :label="t('changes.actionRollbackFlow')" />
            <el-option value="publish_interface" :label="t('changes.actionPublishInterface')" />
            <el-option value="revoke_interface" :label="t('changes.actionRevokeInterface')" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('changes.target')" required>
          <el-select v-if="isFlowAction" v-model="form.target" style="width: 100%" filterable>
            <el-option v-for="f in flows" :key="f.id" :value="f.id"
                       :label="`${f.name} (#${f.id})`" />
          </el-select>
          <el-select v-else v-model="form.target" style="width: 100%" filterable>
            <el-option v-for="i in interfaces" :key="i.id" :value="i.id"
                       :label="`${i.name} (#${i.id})`" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.action === 'rollback_flow'"
                      :label="t('changes.version')">
          <el-select v-model="form.version" style="width: 100%">
            <el-option v-for="v in versions" :key="v.version" :value="v.version"
                       :label="tr('changes.versionLabel', { version: v.version })" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('changes.note')">
          <el-input v-model="form.note" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">{{ t("changes.cancel") }}</el-button>
        <el-button type="primary" :loading="saving" @click="create">
          {{ t("changes.submit") }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg, getProject } from "../api";
import { fmtDate, t } from "../i18n";
import PageHeader from "../components/PageHeader.vue";

function tr(key, vars = {}) {
  return Object.entries(vars).reduce(
    (s, [k, v]) => s.split(`{${k}}`).join(v ?? ""), t(key));
}

const rows = ref([]);
const flows = ref([]);
const interfaces = ref([]);
const versions = ref([]);
const loading = ref(false);
const saving = ref(false);
const dialog = ref(false);
const status = ref("");
const tokens = reactive({});
const form = reactive({
  action: "pause_flow", target: null, version: null, note: "",
});

const isFlowAction = computed(() =>
  ["run_flow", "pause_flow", "resume_flow", "rollback_flow"].includes(form.action)
);

function actionLabel(a) {
  return {
    run_flow: t("changes.actionRunFlow"),
    pause_flow: t("changes.actionPauseFlow"),
    resume_flow: t("changes.actionResumeFlow"),
    rollback_flow: t("changes.actionRollbackFlow"),
    publish_interface: t("changes.actionPublishInterface"),
    revoke_interface: t("changes.actionRevokeInterface"),
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
    flows.value = await api.get("/flows");
    interfaces.value = await api.get("/interfaces");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  Object.assign(form, { action: "pause_flow", target: null, version: null, note: "" });
  versions.value = [];
  dialog.value = true;
  onAction();
}

async function onAction() {
  form.target = isFlowAction.value ? flows.value[0]?.id ?? null
                                   : interfaces.value[0]?.id ?? null;
  versions.value = [];
  if (form.action === "rollback_flow" && form.target) {
    versions.value = await api.flowVersions(form.target);
    form.version = versions.value[0]?.version ?? null;
  }
}

async function create() {
  if (!form.target) {
    ElMessage.warning(t("changes.selectTarget"));
    return;
  }
  saving.value = true;
  try {
    await api.post("/changes", {
      project_id: getProject() || 1,
      action: form.action,
      target: form.target,
      payload: form.action === "rollback_flow"
        ? { version: form.version } : { note: form.note },
    });
    dialog.value = false;
    await load();
    ElMessage.success(t("changes.submitted"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
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
