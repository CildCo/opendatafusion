<template>
  <div class="page">
    <page-header icon="interface" :title="t('menu.interfaces')"
                 :intro="t('iface.intro')" />
    <div class="toolbar">
      <el-input v-model="q" :placeholder="t('iface.searchPlaceholder')" clearable style="width: 240px"
                :prefix-icon="Search" />
      <el-select v-model="statusFilter" clearable :placeholder="t('iface.allStatus')" style="width: 140px">
        <el-option :value="1" :label="t('iface.published')" />
        <el-option :value="0" :label="t('iface.draft')" />
      </el-select>
      <div class="spacer" />
      <el-button @click="load" :loading="loading">{{ t("iface.refresh") }}</el-button>
      <el-button type="primary" @click="openCreate">{{ t("iface.new") }}</el-button>
    </div>

    <el-card class="card" shadow="never">
      <el-table :data="paged" size="small" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column :label="t('iface.name')" min-width="190">
          <template #default="{ row }">
            <span class="entity-cell">
              <entity-icon type="interface" :size="20" />
              <b>{{ row.name }}</b>
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="key" :label="t('iface.key')" min-width="220">
          <template #default="{ row }">
            <span class="mono">{{ row.key }}</span>
            <el-button link @click="copy(row.key)">{{ t("iface.copy") }}</el-button>
          </template>
        </el-table-column>
        <el-table-column :label="t('iface.status')" width="110">
          <template #default="{ row }">
            <status-dot :status="row.status"
                        :label="row.status === 1
                          ? t('iface.published') : t('iface.draft')" />
          </template>
        </el-table-column>
        <el-table-column :label="t('iface.actions')" width="330" fixed="right">
          <template #default="{ row }">
            <el-button link @click="openDetail(row)">{{ t("iface.detail") }}</el-button>
            <el-button v-if="row.status !== 1" link @click="publish(row)">{{ t("iface.publish") }}</el-button>
            <el-button v-else link @click="revoke(row)">{{ t("iface.revoke") }}</el-button>
            <el-button link :disabled="row.status !== 1" @click="execute(row)">{{ t("iface.execute") }}</el-button>
            <el-button link type="danger" @click="remove(row)">{{ t("iface.delete") }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <empty-state v-if="!loading && !filtered.length"
                   :title="t('iface.empty')"
                   :description="t('iface.intro')"
                   :action-text="t('iface.new')"
                   @action="openCreate" />
      <div class="pager">
        <el-pagination v-model:current-page="page" :page-size="pageSize"
                       :total="filtered.length" layout="total, prev, pager, next" small />
      </div>
    </el-card>

    <el-dialog v-model="dialog" :title="t('iface.newTitle')" width="720px">
      <el-form label-width="90px">
        <el-form-item :label="t('iface.name')" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item :label="t('iface.datasource')" required>
          <el-select v-model="form.datasource_id" style="width: 100%">
            <el-option v-for="d in datasources" :key="d.id" :value="d.id"
                       :label="`${d.name} (${d.kind})`" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('iface.sql')" required>
          <el-input v-model="form.sql_text" type="textarea" :rows="7"
                    class="sql" placeholder="select * from t where day = ${day}" />
        </el-form-item>
        <el-form-item :label="t('iface.params')">
          <div class="param-box">
            <div v-for="(p, i) in form.params" :key="i" class="param-row">
              <el-input v-model="p.name" :placeholder="t('iface.paramName')" style="width: 130px" />
              <el-select v-model="p.type" style="width: 110px">
                <el-option value="string" :label="t('iface.typeString')" />
                <el-option value="number" :label="t('iface.typeNumber')" />
              </el-select>
              <el-checkbox v-model="p.required">{{ t("iface.required") }}</el-checkbox>
              <el-button link type="danger" @click="form.params.splice(i, 1)">{{ t("iface.delete") }}</el-button>
            </div>
            <el-button link type="primary" @click="addParam">+ {{ t("iface.addParam") }}</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">{{ t("iface.cancel") }}</el-button>
        <el-button type="primary" :loading="saving" @click="create">{{ t("iface.save") }}</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="drawer" :title="detail.name || t('iface.detailTitle')" size="700px">
      <el-descriptions :column="2" border>
        <el-descriptions-item :label="t('iface.interfaceId')">{{ detail.id }}</el-descriptions-item>
        <el-descriptions-item :label="t('iface.status')">
          <el-tag :type="detail.status === 1 ? 'success' : 'info'" size="small">
            {{ detail.status === 1 ? t("iface.published") : t("iface.draft") }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="t('iface.openapiPath')" :span="2">
          <span class="mono">/openapi/{{ detail.key }}</span>
          <el-button link @click="copy(`/openapi/${detail.key}`)">
            {{ t("iface.copy") }}
          </el-button>
        </el-descriptions-item>
        <el-descriptions-item :label="t('iface.datasource')">{{ detail.datasource_id }}</el-descriptions-item>
      </el-descriptions>
      <h4>SQL</h4>
      <pre class="sql-preview">{{ detail.sql }}</pre>
      <h4>{{ t("iface.params") }}</h4>
      <el-table :data="detail.params || []" size="small">
        <el-table-column prop="name" :label="t('iface.paramName')" />
        <el-table-column :label="t('iface.paramType')" width="100" />
        <el-table-column :label="t('iface.required')" width="80">
          <template #default="{ row }">{{ row.required ? t("iface.yes") : t("iface.no") }}</template>
        </el-table-column>
      </el-table>
      <div class="actions">
        <el-button v-if="detail.status !== 1" type="primary" @click="publish(detail)">{{ t("iface.publish") }}</el-button>
        <el-button v-else @click="revoke(detail)">{{ t("iface.revoke") }}</el-button>
        <el-button :disabled="detail.status !== 1" @click="execute(detail)">{{ t("iface.execute") }}</el-button>
      </div>

      <el-divider content-position="left">{{ t("iface.history") }}</el-divider>
      <div class="history-head">
        <span class="hint">
          {{ t("iface.totalCalls") }}: {{ history.length }}
        </span>
        <span class="hint" v-if="history.length">
          {{ t("iface.lastCall") }}: {{ history[0].at }}
        </span>
      </div>
      <el-table :data="history" size="small" max-height="240">
        <el-table-column :label="t('iface.time')" width="200">
          <template #default="{ row }">{{ fmt(row.at) }}</template>
        </el-table-column>
        <el-table-column prop="actor" :label="t('iface.actor')" width="120" />
        <el-table-column prop="action" :label="t('iface.status')" width="120" />
        <el-table-column :label="t('iface.rows')">
          <template #default="{ row }">
            {{ row.detail && row.detail.rows !== undefined
              ? row.detail.rows : "-" }}
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!history.length" :description="t('iface.noHistory')"
                :image-size="50" />

      <el-divider content-position="left">{{ t("iface.byDay") }}</el-divider>
      <div class="history-head">
        <span class="hint">{{ t("iface.totalCalls") }}: {{ stats.total.calls }}</span>
        <span class="hint">{{ t("iface.statsRows") }}: {{ stats.total.rows }}</span>
      </div>
      <el-table :data="stats.days" size="small" max-height="220">
        <el-table-column prop="day" :label="t('iface.day')" width="140" />
        <el-table-column prop="calls" :label="t('iface.totalCalls')" width="120" />
        <el-table-column prop="rows" :label="t('iface.statsRows')" />
      </el-table>
    </el-drawer>

    <el-dialog v-model="execDialog" :title="t('iface.execTitle')" width="620px">
      <el-form label-width="100px">
        <el-form-item v-for="p in execParams" :key="p.name" :label="p.name">
          <el-input v-model="execValues[p.name]" :placeholder="p.type" />
        </el-form-item>
      </el-form>
      <el-button type="primary" :loading="execLoading" @click="doExecute">{{ t("iface.execute") }}</el-button>
      <pre class="result">{{ result }}</pre>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Search } from "@element-plus/icons-vue";
import { api, errMsg, getProject } from "../api";
import { fmtDate, t } from "../i18n";
import EmptyState from "../components/EmptyState.vue";
import EntityIcon from "../components/EntityIcon.vue";
import PageHeader from "../components/PageHeader.vue";
import StatusDot from "../components/StatusDot.vue";

const fmt = fmtDate;

const rows = ref([]);
const datasources = ref([]);
const loading = ref(false);
const saving = ref(false);
const dialog = ref(false);
const drawer = ref(false);
const execDialog = ref(false);
const detail = ref({});
const history = ref([]);
const stats = ref({ days: [], total: { calls: 0, rows: 0 } });
const execParams = ref([]);
const execValues = reactive({});
const execLoading = ref(false);
const result = ref("");
const q = ref("");
const statusFilter = ref(null);
const page = ref(1);
const pageSize = 10;
watch([q, statusFilter], () => { page.value = 1; });

const form = reactive({
  name: "", datasource_id: null, sql_text: "",
  params: [{ name: "", type: "string", required: false }],
});

const filtered = computed(() =>
  rows.value.filter((r) => {
    const hitQ = !q.value ||
      (r.name + r.key).toLowerCase().includes(q.value.toLowerCase());
    const hitS = statusFilter.value === null || r.status === statusFilter.value;
    return hitQ && hitS;
  })
);
const paged = computed(() =>
  filtered.value.slice((page.value - 1) * pageSize, page.value * pageSize)
);

async function load() {
  loading.value = true;
  try {
    rows.value = await api.get("/interfaces");
    if (!datasources.value.length) datasources.value = await api.get("/datasources");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  Object.assign(form, {
    name: "", datasource_id: datasources.value[0]?.id ?? null,
    sql_text: "", params: [{ name: "", type: "string", required: false }],
  });
  dialog.value = true;
}
function addParam() {
  form.params.push({ name: "", type: "string", required: false });
}
async function create() {
  if (!form.name || !form.sql_text || !form.datasource_id) {
    ElMessage.warning(t("iface.requiredFields"));
    return;
  }
  saving.value = true;
  try {
    await api.post("/interfaces", {
      project_id: getProject() || 1,
      datasource_id: form.datasource_id,
      name: form.name,
      sql_text: form.sql_text,
      params: form.params.filter((p) => p.name),
    });
    dialog.value = false;
    await load();
    ElMessage.success(t("iface.created"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(
      t("iface.deleteConfirm").replace("{name}", row.name),
      t("iface.deleteTitle"), { type: "warning" });
  } catch (e) {
    return;
  }
  try {
    await api.del(`/interfaces/${row.id}`);
    if (drawer.value && detail.value.id === row.id) drawer.value = false;
    await load();
    ElMessage.success(t("iface.deleted"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function openDetail(row) {
  try {
    detail.value = await api.get(`/interfaces/${row.id}`);
    history.value = await api.get(`/interfaces/${row.id}/history`);
    stats.value = await api.get(`/interfaces/${row.id}/stats`);
    drawer.value = true;
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function publish(row) {
  try {
    const a = await api.post(`/interfaces/${row.id}/approve?action=publish`, {});
    await api.post(`/interfaces/${row.id}/publish?approval_token=${encodeURIComponent(a.approval_token)}`, {});
    await load();
    if (drawer.value && detail.value.id === row.id) await openDetail(row);
    ElMessage.success(t("iface.publishedMsg"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}
async function revoke(row) {
  try {
    await ElMessageBox.confirm(t("iface.revokeConfirm"),
      t("iface.revokeTitle"), { type: "warning" });
    const a = await api.post(`/interfaces/${row.id}/approve?action=revoke`, {});
    await api.post(`/interfaces/${row.id}/revoke?approval_token=${encodeURIComponent(a.approval_token)}`, {});
    await load();
    if (drawer.value && detail.value.id === row.id) await openDetail(row);
    ElMessage.success(t("iface.revokedMsg"));
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

async function execute(row) {
  try {
    const d = await api.get(`/interfaces/${row.id}`);
    execParams.value = d.params || [];
    for (const k of Object.keys(execValues)) delete execValues[k];
    for (const p of execParams.value) execValues[p.name] = "";
    result.value = "";
    detail.value = d;
    execDialog.value = true;
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}
async function doExecute() {
  execLoading.value = true;
  try {
    const payload = {};
    for (const p of execParams.value) {
      const v = execValues[p.name];
      if (p.required && (v === "" || v === undefined)) {
        throw new Error(t("iface.paramRequired").replace("{name}", p.name));
      }
      if (v === "" || v === undefined) continue;
      payload[p.name] = p.type === "number" ? Number(v) : v;
    }
    const r = await api.post(`/interfaces/${detail.value.id}/execute`, payload);
    result.value = JSON.stringify(r, null, 2);
    try {
      history.value = await api.get(
        `/interfaces/${detail.value.id}/history`);
      stats.value = await api.get(
        `/interfaces/${detail.value.id}/stats`);
    } catch {
      /* history is advisory */
    }
  } catch (e) {
    result.value = errMsg(e);
  } finally {
    execLoading.value = false;
  }
}

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success(t("iface.copied"));
  } catch (e) {
    ElMessage.warning(text);
  }
}

onMounted(load);
</script>

<style scoped>
.entity-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.card {
  border-radius: 12px;
  border: 1px solid #e5e7eb;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}
.mono {
  font-family: Consolas, "Courier New", monospace;
  font-size: 12px;
}
.sql :deep(textarea),
.sql-preview {
  font-family: Consolas, "Courier New", monospace;
  font-size: 12px;
}
.sql-preview {
  background: #0f172a;
  color: #e2e8f0;
  padding: 14px;
  border-radius: 8px;
  overflow: auto;
}
.param-box {
  width: 100%;
}
.param-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
.actions {
  margin-top: 16px;
  display: flex;
  gap: 10px;
}
.history-head {
  display: flex;
  gap: 14px;
  margin-bottom: 8px;
}
.result {
  margin-top: 14px;
  background: #0f172a;
  color: #e2e8f0;
  padding: 14px;
  border-radius: 8px;
  max-height: 320px;
  overflow: auto;
  font-size: 12px;
}
</style>
