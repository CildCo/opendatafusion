<template>
  <div class="page">
    <page-header icon="alert" :title="t('menu.alerts')"
                 :intro="t('alerts.intro')" />
    <div class="toolbar">
      <el-select v-model="status" clearable
                 :placeholder="t('alerts.allStatus')" style="width: 140px"
                 @change="search">
        <el-option value="open" :label="t('alerts.statusOpen')" />
        <el-option value="acked" :label="t('alerts.statusAcked')" />
        <el-option value="closed" :label="t('alerts.statusClosed')" />
      </el-select>
      <el-select v-model="severity" clearable
                 :placeholder="t('alerts.allSeverity')" style="width: 140px">
        <el-option value="critical" :label="t('alerts.severityCritical')" />
        <el-option value="warning" :label="t('alerts.severityWarning')" />
        <el-option value="error" :label="t('alerts.severityError')" />
      </el-select>
      <el-select v-model="assignee" clearable filterable
                 :placeholder="t('alerts.allAssignees')"
                 style="width: 150px">
        <el-option v-for="name in assignees" :key="name" :value="name"
                   :label="name" />
      </el-select>
      <div class="spacer" />
      <el-button @click="$router.push('/webhooks')">
        {{ t("alerts.subscriptions") }}
      </el-button>
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
        <el-table-column :label="t('alerts.colStatus')" width="110">
          <template #default="{ row }">
            <status-dot :status="row.status" :label="statusLabel(row.status)" />
          </template>
        </el-table-column>
        <el-table-column :label="t('alerts.assignedTo')" width="120">
          <template #default="{ row }">
            {{ row.assigned_to || "-" }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" :label="t('alerts.colTime')"
                         width="200" />
        <el-table-column :label="t('alerts.colActions')" width="180"
                         fixed="right">
          <template #default="{ row }">
            <el-button v-if="canEdit" link :disabled="row.status !== 'open'"
                       @click.stop="ack(row)">
              {{ t("alerts.ack") }}
            </el-button>
            <el-button v-if="canEdit" link :disabled="row.status === 'closed'"
                       @click.stop="close(row)">
              {{ t("alerts.close") }}
            </el-button>
            <el-button v-if="canApply && row.status === 'open'
                             && row.title.startsWith('schema drift:')"
                       link @click.stop="acceptDrift(row)">
              {{ t("alerts.acceptDrift") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-if="total > pageSize" class="pager"
                     layout="total, prev, pager, next"
                     :total="total" :page-size="pageSize"
                     :current-page="page" @current-change="changePage" />
      <empty-state v-if="!loading && !filtered.length"
                   :title="t('alerts.empty')" />
    </el-card>

    <el-card class="card" shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <b>{{ t("alerts.rules") }}</b>
          <el-button v-if="canEdit" size="small" type="primary"
                     @click="openRule">
            {{ t("alerts.newRule") }}
          </el-button>
        </div>
      </template>
      <el-table :data="rules" size="small">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" :label="t('alerts.ruleName')"
                         min-width="180" />
        <el-table-column prop="kind" :label="t('alerts.ruleKind')"
                         width="150" />
        <el-table-column :label="t('alerts.colActions')" width="100">
          <template #default="{ row }">
            <el-button v-if="canEdit" link type="danger"
                       @click="removeRule(row)">
              {{ t("alerts.deleteRule") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <empty-state v-if="!rules.length" :title="t('alerts.noRules')"
                   :action-text="canEdit ? t('alerts.newRule') : ''" @action="openRule" />
    </el-card>

    <el-drawer v-model="drawer"
               :title="current.title || t('alerts.drawerTitle')"
               size="560px">
      <el-descriptions :column="1" border>
        <el-descriptions-item :label="t('alerts.colSeverity')">
          {{ current.severity }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('alerts.colStatus')">
          {{ statusLabel(current.status) }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('alerts.assignedTo')">
          {{ current.assigned_to || t("alerts.unassigned") }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('alerts.ackedBy')">
          {{ current.acked_by || "-" }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('alerts.closedBy')">
          {{ current.closed_by || "-" }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('alerts.colTime')">
          {{ current.created_at }}
        </el-descriptions-item>
      </el-descriptions>

      <div class="drawer-actions">
        <template v-if="canEdit">
          <el-select v-model="assigneeDraft" clearable filterable
                     size="small" style="flex: 1"
                     :placeholder="t('alerts.assignee')">
            <el-option v-for="name in assignees" :key="name" :value="name"
                       :label="name" />
          </el-select>
          <el-button size="small" type="primary" :loading="assigning"
                     @click="saveAssignee">{{ t("alerts.assign") }}</el-button>
        </template>
        <el-button v-if="canEdit" size="small"
                   :disabled="current.status !== 'open'"
                   @click="ack(current)">{{ t("alerts.ack") }}</el-button>
        <el-button v-if="canEdit" size="small"
                   :disabled="current.status === 'closed'"
                   @click="close(current)">{{ t("alerts.close") }}</el-button>
      </div>

      <h4>{{ t("alerts.timeline") }}</h4>
      <div class="timeline">
        <div class="tl-row">
          <span class="tl-time">{{ current.created_at }}</span>
          <span>{{ t("alerts.raised") }}</span>
        </div>
        <div v-if="current.acked_at" class="tl-row">
          <span class="tl-time">{{ current.acked_at }}</span>
          <span>{{ t("alerts.ackedBy") }} {{ current.acked_by || "-" }}</span>
        </div>
        <div v-for="note in current.notes || []" :key="note.id" class="tl-row">
          <span class="tl-time">{{ note.created_at }}</span>
          <span><b>{{ note.actor }}</b> {{ note.body }}</span>
        </div>
        <div v-if="current.closed_at" class="tl-row">
          <span class="tl-time">{{ current.closed_at }}</span>
          <span>{{ t("alerts.closedBy") }} {{ current.closed_by || "-" }}</span>
        </div>
        <p v-if="!current.notes?.length" class="muted">
          {{ t("alerts.noNotes") }}
        </p>
      </div>
      <div class="note-box">
        <el-input v-model="noteText" type="textarea" :rows="3"
                  :placeholder="t('alerts.notePlaceholder')" />
        <el-button type="primary" :loading="noting"
                   :disabled="!noteText.trim()" @click="saveNote">
          {{ t("alerts.addNote") }}
        </el-button>
      </div>

      <h4>{{ t("alerts.detail") }}</h4>
      <json-view :value="current.detail" />
    </el-drawer>

    <el-dialog v-model="ruleDialog" :title="t('alerts.newRule')"
               width="520px">
      <el-form label-width="110px">
        <el-form-item :label="t('alerts.ruleName')" required>
          <el-input v-model="ruleForm.name" />
        </el-form-item>
        <rule-builder v-model="ruleValue" />
      </el-form>
      <template #footer>
        <el-button @click="ruleDialog = false">{{ t("alerts.cancel") }}</el-button>
        <el-button type="primary" @click="createRule">
          {{ t("alerts.save") }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, canApprove, canWrite, errMsg } from "../api";
import { t } from "../i18n";
import EmptyState from "../components/EmptyState.vue";
import PageHeader from "../components/PageHeader.vue";
import JsonView from "../components/JsonView.vue";
import RuleBuilder from "../components/RuleBuilder.vue";
import StatusDot from "../components/StatusDot.vue";

const rows = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(50);
const canEdit = canWrite();
const canApply = canApprove();
const rules = ref([]);
const loading = ref(false);
const status = ref("");
const severity = ref("");
const assignee = ref("");
const assignees = ref([]);
const assigneeDraft = ref("");
const assigning = ref(false);
const noteText = ref("");
const noting = ref(false);
const drawer = ref(false);
const current = ref({});
const ruleDialog = ref(false);
const ruleForm = reactive({ name: "" });
const ruleValue = reactive({ kind: "mute", config: {} });

const filtered = computed(() =>
  rows.value.filter((r) =>
    (!severity.value || r.severity === severity.value)
    && (!assignee.value || r.assigned_to === assignee.value))
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
    const params = new URLSearchParams({
      page: String(page.value), page_size: String(pageSize.value),
    });
    if (status.value) params.set("status", status.value);
    const result = await api.get(`/alerts?${params.toString()}`);
    rows.value = result.items || [];
    total.value = result.total || 0;
    rules.value = await api.get("/alerts/rules");
    try {
      assignees.value = await api.get("/alerts/assignees");
    } catch {
      assignees.value = [];
    }
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

function changePage(next) {
  page.value = next;
  load();
}

function search() {
  page.value = 1;
  load();
}
async function showDetail(row) {
  current.value = row;
  assigneeDraft.value = row.assigned_to || "";
  noteText.value = "";
  drawer.value = true;
  try {
    current.value = await api.get(`/alerts/${row.id}`);
    assigneeDraft.value = current.value.assigned_to || "";
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function refreshDetail() {
  if (!current.value?.id) return;
  try {
    current.value = await api.get(`/alerts/${current.value.id}`);
    assigneeDraft.value = current.value.assigned_to || "";
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function saveAssignee() {
  if (!current.value?.id) return;
  assigning.value = true;
  try {
    await api.post(`/alerts/${current.value.id}/assign`, {
      assignee: assigneeDraft.value || "",
    });
    await load();
    await refreshDetail();
    ElMessage.success(t("alerts.assigned"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    assigning.value = false;
  }
}

async function saveNote() {
  if (!current.value?.id || !noteText.value.trim()) return;
  noting.value = true;
  try {
    await api.post(`/alerts/${current.value.id}/notes`,
                   { body: noteText.value });
    noteText.value = "";
    await refreshDetail();
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    noting.value = false;
  }
}
async function ack(row) {
  try {
    await api.post(`/alerts/${row.id}/ack`);
    await load();
    if (current.value?.id === row.id) await refreshDetail();
    ElMessage.success(t("alerts.ackedMsg"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}
async function acceptDrift(row) {
  const dsId = (row.detail || {}).datasource_id;
  if (!dsId) return;
  try {
    const out = await api.post(`/datasources/${dsId}/accept-schema-drift`);
    ElMessage.success(t("alerts.driftAccepted").replace("{n}", out.alerts));
    await load();
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
    if (current.value?.id === row.id) await refreshDetail();
    ElMessage.success(t("alerts.closedMsg"));
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}
onMounted(load);

function openRule() {
  ruleForm.name = "";
  ruleValue.kind = "mute";
  ruleValue.config = {};
  ruleDialog.value = true;
}

async function createRule() {
  if (!ruleForm.name.trim()) {
    ElMessage.warning(t("alerts.nameRequired"));
    return;
  }
  try {
    await api.post("/alerts/rules", {
      name: ruleForm.name.trim(), kind: ruleValue.kind,
      config: ruleValue.config,
    });
    ruleDialog.value = false;
    await load();
    ElMessage.success(t("alerts.created"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function removeRule(row) {
  try {
    await ElMessageBox.confirm(
      t("alerts.deleteRuleConfirm").replace("{name}", row.name),
      t("alerts.deleteRule"), { type: "warning" });
  } catch (e) {
    return;
  }
  try {
    await api.del(`/alerts/rules/${row.id}`);
    await load();
    ElMessage.success(t("alerts.deleted"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}
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
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.rule-hint { color: #64748b; font-size: 12px; line-height: 1.5; }
.drawer-actions { display: flex; gap: 8px; margin-top: 14px;
                  flex-wrap: wrap; }
.timeline { border-left: 2px solid #e2e8f0; padding-left: 12px;
            margin: 8px 0; }
.tl-row { display: flex; gap: 10px; font-size: 12px; color: #475569;
          padding: 4px 0; }
.tl-time { color: #94a3b8; min-width: 138px; }
.note-box { display: flex; flex-direction: column; gap: 8px;
            align-items: flex-end; margin-bottom: 8px; }
.note-box :deep(.el-textarea) { width: 100%; }
.pager { margin-top: 12px; justify-content: flex-end; }
</style>
