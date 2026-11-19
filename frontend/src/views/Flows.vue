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
            <el-table-column :label="t('flows.actions')" width="180">
              <template #default="{ row }">
                <el-button link :disabled="row.version === current.version"
                           @click="rollback(row)">{{ t("flows.rollback") }}</el-button>
                <el-button link @click="compareVersion(row)">{{ t("flows.compare") }}</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="t('flows.runs')" name="runs">
          <el-table :data="runs" size="small" @row-click="openRun"
                    row-class-name="clickable">
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="status" :label="t('flows.status')" width="100">
              <template #default="{ row }">
                <el-tag :type="runType(row.status)" size="small">
                  {{ runLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="t('flows.startedAt')" width="150">
              <template #default="{ row }">{{ fmt(row.started_at) }}</template>
            </el-table-column>
            <el-table-column :label="t('flows.duration')" width="100">
              <template #default="{ row }">{{ duration(row) }}</template>
            </el-table-column>
            <el-table-column prop="in" :label="t('flows.input')" width="80" />
            <el-table-column prop="out" :label="t('flows.output')" width="80" />
            <el-table-column :label="t('flows.actions')" width="130">
              <template #default="{ row }">
                <el-button link @click.stop="openRun(row)">
                  {{ t("flows.runDetail") }}
                </el-button>
                <el-button link type="primary"
                           :disabled="current.status !== 1 || row.status < 2"
                           @click.stop="retryRun(row)">
                  {{ t("flows.retry") }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="t('flows.downstream')" name="downstream">
          <div v-if="downstream.edges.length" class="lineage">
            <div v-for="(e, i) in downstream.edges" :key="i" class="edge">
              <span class="node-tag">{{ e.from }}</span>
              <el-icon><Right /></el-icon>
              <span class="node-tag dst">{{ e.to }}</span>
            </div>
            <div v-if="downstream.column_edges.length" class="hint"
                 style="margin-top: 10px">
              {{ tr("cat.columnImpact", { n: downstream.column_edges.length }) }}
            </div>
          </div>
          <el-empty v-else :description="t('flows.noDownstream')"
                    :image-size="70" />
          <div v-if="downstream.tables.length" style="margin-top: 12px">
            <div class="hint">{{ t("cat.tables") }}</div>
            <el-tag v-for="tb in downstream.tables" :key="tb" size="small"
                    type="info" style="margin: 6px 6px 0 0">
              {{ tb }}
            </el-tag>
          </div>
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

    <el-dialog v-model="runOpen" :title="t('flows.runDetail')" width="520px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="ID">{{ runRow.id }}</el-descriptions-item>
        <el-descriptions-item :label="t('flows.status')">
          <el-tag :type="runType(runRow.status)" size="small">
            {{ runLabel(runRow.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="t('flows.startedAt')">
          {{ fmt(runRow.started_at) }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('flows.finishedAt')">
          {{ fmt(runRow.finished_at) }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('flows.duration')">
          {{ duration(runRow) }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('flows.rowsPerSecond')">
          {{ rate(runRow) }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('flows.input')">
          {{ runRow.in }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('flows.output')">
          {{ runRow.out }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('flows.error')">
          {{ runRow.err }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('flows.cursor')">
          {{ runRow.cursor || "-" }}
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="runOpen = false">{{ t("flows.cancel") }}</el-button>
        <el-button type="primary"
                   :disabled="current.status !== 1 || runRow.status < 2"
                   @click="retryRun(runRow)">{{ t("flows.retry") }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="compareOpen" :title="t('flows.compareTitle')"
               width="720px">
      <p class="hint" style="margin-top: 0">
        v{{ compareVersionNo }} → v{{ current.version }}
      </p>
      <el-table :data="compareRows" size="small">
        <el-table-column prop="key" :label="t('flows.changedKeys')"
                         min-width="160" />
        <el-table-column :label="'v' + compareVersionNo" min-width="180">
          <template #default="{ row }">
            <span class="mono">{{ row.left }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="'v' + current.version" min-width="180">
          <template #default="{ row }">
            <span class="mono">{{ row.right }}</span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!compareRows.length" :description="t('flows.noChanges')"
                :image-size="60" />
      <template #footer>
        <el-button @click="compareOpen = false">{{ t("flows.cancel") }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Search, Right } from "@element-plus/icons-vue";
import { api, errMsg } from "../api";
import { fmtDate, t } from "../i18n";

function tr(key, vars = {}) {
  return Object.entries(vars).reduce(
    (s, [k, v]) => s.split(`{${k}}`).join(v ?? ""), t(key));
}

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
const runOpen = ref(false);
const runRow = ref({});
const downstream = reactive({ edges: [], column_edges: [], tables: [] });
const compareOpen = ref(false);
const compareVersionNo = ref(1);
const compareRows = ref([]);
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

const fmt = fmtDate;

function duration(row) {
  const ms = row.duration_ms;
  if (ms === null || ms === undefined) return "-";
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

function rate(row) {
  if (!row.duration_ms || row.duration_ms <= 0) return "-";
  return Math.round((row.in || 0) / (row.duration_ms / 1000));
}

function openRun(row) {
  runRow.value = row;
  runOpen.value = true;
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
    loadDownstream();
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

async function loadDownstream() {
  downstream.edges = [];
  downstream.column_edges = [];
  downstream.tables = [];
  const d = dag.value || {};
  if (!d.sink_ds_id || !d.sink_table) return;
  try {
    const ref = `${d.sink_ds_id}:${d.sink_table}`;
    const r = await api.get(
      `/catalog/impact?ref=${encodeURIComponent(ref)}`);
    downstream.edges = r.edges || [];
    downstream.column_edges = r.column_edges || [];
    downstream.tables = [...new Set((r.edges || []).map((e) => e.to))];
  } catch {
    /* impact is advisory */
  }
}

function flatten(value, prefix = "", out = {}) {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    for (const [k, v] of Object.entries(value)) {
      flatten(v, prefix ? `${prefix}.${k}` : k, out);
    }
  } else {
    out[prefix] = value;
  }
  return out;
}

function display(value) {
  if (value === undefined) return "-";
  if (value === null) return "null";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

async function compareVersion(row) {
  try {
    const v = await api.get(
      `/flows/${current.value.id}/versions/${row.version}`);
    compareVersionNo.value = row.version;
    const left = flatten(v.dag || {});
    const right = flatten(dag.value || {});
    const keys = [...new Set([...Object.keys(left), ...Object.keys(right)])];
    compareRows.value = keys
      .filter((k) => JSON.stringify(left[k]) !== JSON.stringify(right[k]))
      .map((k) => ({ key: k, left: display(left[k]),
                     right: display(right[k]) }));
    compareOpen.value = true;
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function retryRun(row) {
  try {
    await api.post(
      `/flows/${current.value.id}/runs/${row.id}/retry`);
    ElMessage.success(t("flows.retried"));
    runOpen.value = false;
    await pollDetail();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
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
  color: #64748b;
  font-size: 12px;
  margin-left: 8px;
}
.actions {
  margin-top: 16px;
  display: flex;
  gap: 10px;
}
.lineage {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.edge {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.node-tag {
  background: #eff6ff;
  color: #1d4ed8;
  border-radius: 6px;
  padding: 3px 8px;
}
.node-tag.dst {
  background: #ecfdf5;
  color: #047857;
}
.mono {
  font-family: Consolas, "Courier New", monospace;
  font-size: 12px;
}
:deep(.clickable) {
  cursor: pointer;
}
</style>
