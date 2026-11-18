<template>
  <div class="page">
    <div class="toolbar">
      <el-input v-model="q" :placeholder="t('flows.searchPlaceholder')" clearable style="width: 220px"
                :prefix-icon="Search" />
      <el-select v-model="statusFilter" clearable :placeholder="t('flows.allStatus')" style="width: 140px">
        <el-option :value="1" :label="t('flows.enabled')" />
        <el-option :value="0" :label="t('flows.disabled')" />
      </el-select>
      <div class="spacer" />
      <el-button @click="load" :loading="loading">{{ t("flows.refresh") }}</el-button>
      <el-button type="primary" @click="openCreate">{{ t("flows.newFlow") }}</el-button>
    </div>

    <el-card class="card" shadow="never">
      <el-table :data="paged" size="small" v-loading="loading"
                @row-click="openDetail" row-class-name="clickable">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" :label="t('flows.name')" min-width="160" />
        <el-table-column prop="cron" :label="t('flows.schedule')" width="150" />
        <el-table-column prop="version" :label="t('flows.version')" width="80" />
        <el-table-column prop="status" :label="t('flows.status')" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
              {{ row.status === 1 ? t("flows.enabled") : t("flows.disabled") }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('flows.actions')" width="240" fixed="right">
          <template #default="{ row }">
            <el-button link @click.stop="toggle(row)">
              {{ row.status === 1 ? t("flows.disabled") : t("flows.enabled") }}
            </el-button>
            <el-button link :disabled="row.status !== 1" @click.stop="run(row)">{{ t("flows.run") }}</el-button>
            <el-button link @click.stop="openDetail(row)">{{ t("flows.details") }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !filtered.length" :description="t('flows.empty')" />
      <div class="pager">
        <el-pagination v-model:current-page="page" :page-size="pageSize"
                       :total="filtered.length" layout="total, prev, pager, next" small />
      </div>
    </el-card>

    <el-dialog v-model="dialog" :title="t('flows.newFlow')" width="680px">
      <el-form label-width="110px">
        <el-form-item :label="t('flows.name')" required>
          <el-input v-model="form.name" :placeholder="t('flows.namePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('flows.schedule')">
          <el-select v-model="form.cronPreset" style="width: 200px" @change="onCronPreset">
            <el-option value="0 */5 * * * ?" :label="t('flows.every5')" />
            <el-option value="0 0 * * * ?" :label="t('flows.hourly')" />
            <el-option value="0 0 2 * * ?" :label="t('flows.daily2')" />
            <el-option value="custom" :label="t('flows.custom')" />
          </el-select>
          <el-input v-if="form.cronPreset === 'custom'" v-model="form.cron"
                    style="width: 220px; margin-left: 10px"
                    placeholder="0 */5 * * * ?" />
        </el-form-item>
        <el-divider content-position="left">{{ t("flows.source") }}</el-divider>
        <el-form-item :label="t('flows.datasource')">
          <el-select v-model="form.source_ds_id" style="width: 100%"
                     @change="loadSourceTables">
            <el-option v-for="d in datasources" :key="d.id" :value="d.id"
                       :label="`${d.name} (${d.kind})`" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('flows.table')">
          <el-select v-model="form.source_table" style="width: 100%"
                     filterable @change="onSourceTable">
            <el-option v-for="tbl in sourceTables" :key="tbl.table" :value="tableValue(tbl)"
                       :label="`${tbl.schema}.${tbl.table}`" />
          </el-select>
        </el-form-item>
        <el-divider content-position="left">{{ t("flows.target") }}</el-divider>
        <el-form-item :label="t('flows.datasource')">
          <el-select v-model="form.sink_ds_id" style="width: 100%"
                     @change="loadSinkTables">
            <el-option v-for="d in datasources" :key="d.id" :value="d.id"
                       :label="`${d.name} (${d.kind})`" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('flows.table')">
          <el-select v-model="form.sink_table" style="width: 100%" filterable>
            <el-option v-for="tbl in sinkTables" :key="tbl.table" :value="tableValue(tbl)"
                       :label="`${tbl.schema}.${tbl.table}`" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('flows.pk')">
          <el-select v-model="form.pk" style="width: 100%" filterable allow-create>
            <el-option v-for="c in sourceColumns" :key="c.name" :value="c.name"
                       :label="`${c.name} (${c.type})`" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('flows.cursorColumn')">
          <el-select v-model="form.cursor_column" style="width: 100%" clearable
                     filterable allow-create>
            <el-option v-for="c in sourceColumns" :key="c.name" :value="c.name"
                       :label="`${c.name} (${c.type})`" />
          </el-select>
          <div class="hint">{{ t("flows.cursorHint") }}</div>
        </el-form-item>
        <el-form-item :label="t('flows.batch')">
          <el-input-number v-model="form.batch" :min="1" :step="100" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">{{ t("flows.cancel") }}</el-button>
        <el-button type="primary" :loading="saving" @click="create">{{ t("flows.save") }}</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="drawer" :title="current.name || t('flows.flowDetail')" size="720px">
      <el-tabs v-model="tab">
        <el-tab-pane :label="t('flows.overview')" name="overview">
          <el-descriptions :column="2" border>
            <el-descriptions-item :label="t('flows.flowId')">{{ current.id }}</el-descriptions-item>
            <el-descriptions-item :label="t('flows.status')">
              <el-tag :type="current.status === 1 ? 'success' : 'info'" size="small">
                {{ current.status === 1 ? t("flows.enabled") : t("flows.disabled") }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item :label="t('flows.schedule')">{{ current.cron }}</el-descriptions-item>
            <el-descriptions-item :label="t('flows.currentVersion')">{{ current.version }}</el-descriptions-item>
            <el-descriptions-item :label="t('flows.source')" :span="2">
              {{ dag.source_table }} ← {{ t("flows.datasource") }} {{ dag.source_ds_id }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('flows.target')" :span="2">
              {{ dag.sink_table }} ← {{ t("flows.datasource") }} {{ dag.sink_ds_id }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('flows.pk')">{{ dag.pk }}</el-descriptions-item>
            <el-descriptions-item :label="t('flows.cursorColumn')">{{ dag.cursor_column || t("flows.fullLoad") }}</el-descriptions-item>
          </el-descriptions>
          <div class="actions">
            <el-button type="primary" :disabled="current.status !== 1" @click="run(current)">
              {{ t("flows.runOnce") }}
            </el-button>
            <el-button @click="toggle(current)">
              {{ current.status === 1 ? t("flows.disabled") : t("flows.enabled") }}
            </el-button>
            <el-button @click="refreshDetail">{{ t("flows.refresh") }}</el-button>
          </div>
        </el-tab-pane>

        <el-tab-pane :label="t('flows.versions')" name="versions">
          <el-table :data="versions" size="small">
            <el-table-column prop="version" :label="t('flows.version')" width="80" />
            <el-table-column prop="created_by" :label="t('flows.createdBy')" width="140" />
            <el-table-column prop="created_at" :label="t('flows.time')" />
            <el-table-column :label="t('flows.actions')" width="120">
              <template #default="{ row }">
                <el-button link :disabled="row.version === current.version"
                           @click="rollback(row)">{{ t("flows.rollback") }}</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="t('flows.runs')" name="runs">
          <el-table :data="runs" size="small">
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="status" :label="t('flows.status')" width="100">
              <template #default="{ row }">
                <el-tag :type="runType(row.status)" size="small">
                  {{ runLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="in" :label="t('flows.input')" width="90" />
            <el-table-column prop="out" :label="t('flows.output')" width="90" />
            <el-table-column prop="err" :label="t('flows.error')" width="80" />
            <el-table-column prop="cursor" :label="t('flows.cursor')" />
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="t('flows.jobs')" name="jobs">
          <el-table :data="jobs" size="small">
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="status" :label="t('flows.status')" width="100" />
            <el-table-column prop="attempts" :label="t('flows.attempts')" width="70" />
            <el-table-column prop="run_at" :label="t('flows.plannedAt')" width="200" />
            <el-table-column prop="last_error" :label="t('flows.lastError')" />
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Search } from "@element-plus/icons-vue";
import { api, errMsg } from "../api";
import { t } from "../i18n";

const rows = ref([]);
const datasources = ref([]);
const sourceTables = ref([]);
const sinkTables = ref([]);
const sourceColumns = ref([]);
const versions = ref([]);
const runs = ref([]);
const jobs = ref([]);
const loading = ref(false);
const saving = ref(false);
const dialog = ref(false);
const drawer = ref(false);
const tab = ref("overview");
const current = ref({});
const dag = ref({});
const q = ref("");
const statusFilter = ref(null);
const page = ref(1);
const pageSize = 10;
let timer = null;

const form = reactive({
  name: "", cronPreset: "0 */5 * * * ?", cron: "0 */5 * * * ?",
  source_ds_id: null, source_table: "", sink_ds_id: null, sink_table: "",
  pk: "id", cursor_column: "", batch: 1000,
});

const filtered = computed(() =>
  rows.value.filter((r) => {
    const hitQ = !q.value || r.name.toLowerCase().includes(q.value.toLowerCase());
    const hitS = statusFilter.value === null || r.status === statusFilter.value;
    return hitQ && hitS;
  })
);
const paged = computed(() =>
  filtered.value.slice((page.value - 1) * pageSize, page.value * pageSize)
);

function runType(s) {
  return s === 2 ? "success" : s === 3 ? "danger" : s === 1 ? "warning" : "info";
}
function runLabel(s) {
  return {
    0: t("flows.runQueued"), 1: t("flows.runRunning"),
    2: t("flows.runSuccess"), 3: t("flows.runFailed"),
    4: t("flows.runSkipped"),
  }[s] || s;
}

async function load() {
  loading.value = true;
  try {
    rows.value = await api.get("/flows");
    if (!datasources.value.length) datasources.value = await api.get("/datasources");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  Object.assign(form, {
    name: "", cronPreset: "0 */5 * * * ?", cron: "0 */5 * * * ?",
    source_ds_id: datasources.value[0]?.id ?? null,
    source_table: "", sink_ds_id: datasources.value[0]?.id ?? null,
    sink_table: "", pk: "id", cursor_column: "", batch: 1000,
  });
  sourceTables.value = [];
  sinkTables.value = [];
  sourceColumns.value = [];
  dialog.value = true;
  if (form.source_ds_id) loadSourceTables();
  if (form.sink_ds_id) loadSinkTables();
}

function onCronPreset(v) {
  if (v !== "custom") form.cron = v;
}

function tableValue(tbl) {
  return tbl.schema && tbl.schema !== "main" && tbl.schema !== "public"
    ? `${tbl.schema}.${tbl.table}` : tbl.table;
}

async function loadSourceTables() {
  sourceTables.value = await api.tablesOf(form.source_ds_id);
  form.source_table = "";
  sourceColumns.value = [];
}
async function loadSinkTables() {
  sinkTables.value = await api.tablesOf(form.sink_ds_id);
  form.sink_table = "";
}
function onSourceTable(name) {
  const tbl = sourceTables.value.find((x) => tableValue(x) === name);
  sourceColumns.value = tbl ? tbl.columns || [] : [];
  if (sourceColumns.value.length && !form.pk) form.pk = sourceColumns.value[0].name;
}

async function create() {
  if (!form.name || !form.source_table || !form.sink_table) {
    ElMessage.warning(t("flows.required"));
    return;
  }
  saving.value = true;
  try {
    await api.post("/flows", {
      project_id: 1,
      name: form.name,
      cron: form.cronPreset === "custom" ? form.cron : form.cronPreset,
      dag: {
        source_ds_id: form.source_ds_id,
        sink_ds_id: form.sink_ds_id,
        source_table: form.source_table,
        sink_table: form.sink_table,
        pk: form.pk,
        cursor_column: form.cursor_column || null,
        batch: form.batch,
      },
    });
    dialog.value = false;
    await load();
    ElMessage.success(t("flows.created"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

async function openDetail(row) {
  drawer.value = true;
  tab.value = "overview";
  try {
    const f = await api.get(`/flows/${row.id}`);
    current.value = f;
    dag.value = f.dag || {};
    versions.value = await api.flowVersions(row.id);
    runs.value = await api.flowRuns(row.id);
    jobs.value = await api.get(`/flows/${row.id}/jobs`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
  if (timer) clearInterval(timer);
  timer = setInterval(pollDetail, 5000);
}

async function pollDetail() {
  if (!drawer.value || !current.value.id) return;
  try {
    runs.value = await api.flowRuns(current.value.id);
    jobs.value = await api.get(`/flows/${current.value.id}/jobs`);
    const f = await api.get(`/flows/${current.value.id}`);
    current.value = f;
    dag.value = f.dag || {};
  } catch (e) {
    /* silent polling */
  }
}

async function refreshDetail() {
  if (current.value.id) await openDetail(current.value);
}

async function run(row) {
  try {
    await api.post(`/flows/${row.id}/runs`);
    ElMessage.success(t("flows.queued"));
    if (drawer.value && current.value.id === row.id) await pollDetail();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function toggle(row) {
  const action = row.status === 1 ? "pause_flow" : "resume_flow";
  try {
    await ElMessageBox.confirm(
      action === "pause_flow" ? t("flows.confirmPause") : t("flows.confirmResume"),
      t("flows.confirmChange"), { type: "warning" }
    );
    await api.applyChange(action, row.id);
    await load();
    if (drawer.value) await pollDetail();
    ElMessage.success(t("flows.applied"));
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

async function rollback(row) {
  try {
    await ElMessageBox.confirm(
      t("flows.confirmRollback").replace("{version}", row.version),
      t("flows.rollbackTitle"), { type: "warning" });
    await api.applyChange("rollback_flow", current.value.id, { version: row.version });
    await pollDetail();
    ElMessage.success(t("flows.rolledBack"));
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

onMounted(load);
onBeforeUnmount(() => timer && clearInterval(timer));
</script>

<style scoped>
.card {
  border-radius: 12px;
  border: 1px solid #e5e7eb;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}
.hint {
  color: #9ca3af;
  font-size: 12px;
  margin-left: 8px;
}
.actions {
  margin-top: 16px;
  display: flex;
  gap: 10px;
}
:deep(.clickable) {
  cursor: pointer;
}
</style>
