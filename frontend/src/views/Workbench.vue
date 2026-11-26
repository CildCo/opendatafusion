<template>
  <div class="wb-page">
    <div class="head">
      <el-tag size="small" type="info">{{ t("wb.readonly") }}</el-tag>
      <div class="spacer" />
      <el-button size="small" @click="openPlan"
                 :disabled="tab !== 'single'">{{ t("wb.explain") }}</el-button>
      <el-button size="small" @click="openHistory">{{ t("wb.history") }}</el-button>
      <el-button size="small" @click="saveQuery">{{ t("wb.saveQuery") }}</el-button>
      <el-button size="small" @click="openSaved">{{ t("wb.savedQueries") }}</el-button>
      <el-button size="small" @click="loadDatasources">{{ t("wb.refreshSources") }}</el-button>
    </div>

    <el-tabs v-model="tab" class="panel">
      <el-tab-pane :label="t('wb.single')" name="single">
        <div class="query-tabs">
          <button v-for="(tab, i) in queryTabs" :key="tab.id" type="button"
                  class="query-tab" :class="{ active: i === activeTab }"
                  @click="activateTab(i)">
            <span>{{ tab.name }}</span>
            <span v-if="queryTabs.length > 1" class="tab-close"
                  @click.stop="closeTab(i)">×</span>
          </button>
          <el-button link size="small" @click="addTab">
            + {{ t("wb.newTab") }}
          </el-button>
        </div>
        <div class="query-layout">
          <aside class="schema-panel">
            <div class="schema-head">
              <b>{{ t("wb.schema") }}</b>
              <el-button link size="small" :loading="schemaLoading"
                         @click="loadTables(datasourceId)">
                {{ t("wb.refreshSchema") }}
              </el-button>
            </div>
            <el-input v-model="schemaFilter" size="small" clearable
                      :placeholder="t('wb.searchSchema')" />
            <el-tree :data="schemaTree" :props="{ label: 'label' }"
                     node-key="key" default-expand-all highlight-current
                     empty-text="-" @node-click="insertSchema" />
          </aside>
          <div class="query-main">
            <div class="toolbar">
              <el-select v-model="datasourceId"
                         :placeholder="t('wb.selectSource')" size="small"
                         style="width: 220px">
                <el-option v-for="d in datasources" :key="d.id" :value="d.id"
                           :label="`${d.name} (${d.kind})`" />
              </el-select>
              <span class="hint">{{ t("wb.limit") }}</span>
              <el-input-number v-model="limit" :min="1" :max="10000"
                               size="small" :controls="false"
                               style="width: 90px" />
              <div class="spacer" />
              <el-button size="small" :loading="formatting"
                         @click="formatSql">{{ t("wb.format") }}</el-button>
              <el-button type="primary" size="small" :loading="loading"
                         @click="runSingle">{{ t("wb.run") }}</el-button>
            </div>
            <SqlEditor ref="editorRef" v-model="singleSql"
                       :schema="sqlSchema" />
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane :label="t('wb.federated')" name="federated">
        <div class="federation">
          <div v-for="(s, i) in sources" :key="i" class="source-row">
            <el-input v-model="s.alias" size="small" :placeholder="t('wb.alias')"
                      style="width: 100px" />
            <el-select v-model="s.datasource_id" size="small"
                       :placeholder="t('wb.datasource')" style="width: 190px"
                       @change="loadTables(s.datasource_id)">
              <el-option v-for="d in datasources" :key="d.id" :value="d.id"
                         :label="d.name" />
            </el-select>
            <el-select v-model="s.table" size="small" filterable
                       :placeholder="t('wb.table')" style="width: 220px">
              <el-option v-for="t in tables[s.datasource_id] || []"
                         :key="(t.schema ? t.schema + '.' : '') + t.table"
                         :value="(t.schema ? t.schema + '.' : '') + t.table"
                         :label="(t.schema ? t.schema + '.' : '') + t.table" />
            </el-select>
            <el-button link type="danger" size="small"
                       @click="removeSource(i)":aria-label="t('common.remove')">×</el-button>
          </div>
          <el-button size="small" :disabled="sources.length >= 4"
                     @click="addSource">+ {{ t("wb.addSource") }}</el-button>
          <span class="hint">
            {{ t("wb.fedHint") }}
          </span>
        </div>
        <div class="toolbar">
          <span class="hint">{{ t("wb.limit") }}</span>
          <el-input-number v-model="limit" :min="1" :max="10000"
                           size="small" :controls="false"
                           style="width: 90px" />
          <div class="spacer" />
          <el-button type="primary" size="small" :loading="loading"
                     @click="runFederated">{{ t("wb.run") }}</el-button>
        </div>
        <SqlEditor v-model="fedSql" />
      </el-tab-pane>
    </el-tabs>

    <div v-if="error" class="result">
      <el-alert :title="error" type="error" :closable="false" />
    </div>
    <div v-else-if="result" class="result">
      <div class="result-head">
        <span>{{ result.row_count }} {{ t("wb.rows") }} · {{ result.ms }} ms</span>
        <el-tag v-if="result.truncated" size="small" type="warning">
          {{ t("wb.truncated") }}
        </el-tag>
        <div class="spacer" />
        <el-radio-group v-model="resultView" size="small">
          <el-radio-button value="table">{{ t("wb.resultTable") }}</el-radio-button>
          <el-radio-button value="chart">{{ t("wb.resultChart") }}</el-radio-button>
          <el-radio-button value="stats">{{ t("wb.resultStats") }}</el-radio-button>
          <el-radio-button value="request">{{ t("wb.resultRequest") }}</el-radio-button>
          <el-radio-button value="json">{{ t("wb.resultJson") }}</el-radio-button>
        </el-radio-group>
        <el-button size="small" @click="exportCsv">{{ t("wb.exportCsv") }}</el-button>
      </div>
      <template v-if="resultView === 'chart'">
        <div class="chart-controls">
          <el-select v-model="chartType" size="small" style="width: 96px"
                     :aria-label="t('wb.chartType')">
            <el-option value="bar" :label="t('wb.chartBar')" />
            <el-option value="line" :label="t('wb.chartLine')" />
            <el-option value="area" :label="t('wb.chartArea')" />
            <el-option value="pie" :label="t('wb.chartPie')" />
          </el-select>
          <el-select v-model="chartDim" size="small" style="width: 130px"
                     :placeholder="t('wb.dimension')">
            <el-option v-for="c in result.columns" :key="'d' + c" :value="c"
                       :label="c" />
          </el-select>
          <el-select v-model="chartVal" size="small" style="width: 130px"
                     :placeholder="t('wb.measure')">
            <el-option v-for="c in result.columns" :key="'v' + c" :value="c"
                       :label="c" />
          </el-select>
        </div>
        <chart-view v-if="chartOption" :option="chartOption"
                    class="result-chart" />
      </template>
      <el-table v-else-if="resultView === 'table'" :data="result.rows"
                size="small" height="380" border>
        <el-table-column v-for="c in result.columns" :key="c" :prop="c"
                         :label="c" min-width="130" show-overflow-tooltip />
      </el-table>
      <el-descriptions v-else-if="resultView === 'stats'" :column="2" border>
        <el-descriptions-item :label="t('wb.statRows')">
          {{ result.row_count }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('wb.statMs')">
          {{ result.ms }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('wb.statColumns')">
          {{ result.columns.length }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('wb.statDatasource')">
          {{ datasourceName }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('wb.statTruncated')">
          {{ result.truncated ? t("wb.yes") : t("wb.no") }}
        </el-descriptions-item>
      </el-descriptions>
      <pre v-else-if="resultView === 'request'" class="inspector-pre">{{ singleSql }}</pre>
      <pre v-else class="inspector-pre">{{ JSON.stringify(result.rows, null, 2) }}</pre>
    </div>
    <el-empty v-else :description="t('wb.empty')" />
    <el-drawer v-model="savedOpen" :title="t('wb.savedQueries')" size="420px"
               @open="loadSaved">
      <el-empty v-if="!saved.length" :description="t('wb.noSaved')"
                :image-size="60" />
      <div v-for="row in saved" :key="row.id" class="saved-row">
        <button type="button" class="saved-main" @click="applySaved(row)">
          <b>{{ row.name }}</b>
          <small>{{ row.tab }} · {{ row.created_at }}</small>
        </button>
        <el-button link type="danger" @click="removeSaved(row)">
          {{ t("common.remove") }}
        </el-button>
      </div>
    </el-drawer>

    <el-drawer v-model="historyOpen" :title="t('wb.history')" size="540px"
               @open="loadHistory">
      <el-empty v-if="!runs.length" :description="t('wb.noHistory')"
                :image-size="60" />
      <div v-for="row in runs" :key="row.id" class="hist-row"
           @click="applyRun(row)">
        <div class="hist-top">
          <el-tag size="small" :type="row.status === 'ok' ? 'success' : 'danger'">
            {{ row.status === "ok" ? t("wb.ok") : t("wb.failed") }}
          </el-tag>
          <span class="hist-source">{{ row.source }}</span>
          <span class="hist-meta">{{ row.ms }} ms · {{ row.rows }} {{ t("wb.rows") }}</span>
        </div>
        <div class="hist-sql">{{ row.sql_preview }}</div>
        <div v-if="row.error" class="hist-error">{{ row.error }}</div>
        <div class="hist-meta">
          {{ row.actor }} · {{ row.datasource_name || "-" }} · {{ fmt(row.created_at) }}
        </div>
      </div>
    </el-drawer>

    <el-dialog v-model="planOpen" :title="t('wb.plan')" width="780px">
      <el-alert v-if="planError" :title="planError" type="error"
                :closable="false" />
      <el-table v-else :data="plan.rows" size="small" height="380" border>
        <el-table-column v-for="c in plan.columns" :key="c" :prop="c"
                         :label="c" min-width="160" show-overflow-tooltip />
      </el-table>
      <template #footer>
        <span class="hint">{{ plan.ms }} ms</span>
        <el-button @click="planOpen = false">{{ t("common.close") }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../api";
import { t } from "../i18n";
import SqlEditor from "../studio/api/SqlEditor.vue";
import ChartView from "../studio/dashboard/ChartView.vue";
import { buildChartOption } from "../studio/shared/chartOptions";

const tab = ref("single");
const datasources = ref([]);
const datasourceId = ref(null);
const singleSql = ref("select 1 as n");
const fedSql = ref("select * from t1 limit 100");
const sources = ref([{ alias: "t1", datasource_id: null, table: "" }]);
const tables = ref({});
const limit = ref(1000);
const loading = ref(false);
const result = ref(null);
const error = ref("");
const savedOpen = ref(false);
const saved = ref([]);
const planOpen = ref(false);
const plan = ref({ columns: [], rows: [], ms: 0 });
const planError = ref("");
const historyOpen = ref(false);
const runs = ref([]);
const editorRef = ref(null);
const queryTabs = ref([]);
const activeTab = ref(0);
const schemaFilter = ref("");
const schemaLoading = ref(false);
const formatting = ref(false);
const resultView = ref("table");
let tabSeq = 0;
const chartType = ref("table");
const chartDim = ref("");
const chartVal = ref("");

const sqlSchema = computed(() => {
  const out = {};
  for (const table of tables.value[datasourceId.value] || []) {
    const name = table.schema ? `${table.schema}.${table.table}`
      : table.table;
    const columns = (table.columns || []).map((c) => c.name);
    out[name] = columns;
    if (!out[table.table]) out[table.table] = columns;
  }
  return out;
});

const schemaTree = computed(() => {
  const needle = schemaFilter.value.trim().toLowerCase();
  const out = [];
  for (const table of tables.value[datasourceId.value] || []) {
    const name = table.schema ? `${table.schema}.${table.table}`
      : table.table;
    const allColumns = table.columns || [];
    const columns = needle
      ? allColumns.filter((c) => c.name.toLowerCase().includes(needle))
      : allColumns;
    if (needle && !name.toLowerCase().includes(needle) && !columns.length) {
      continue;
    }
    out.push({
      key: `t:${name}`, label: name, type: "table", insert: name,
      children: (needle && !name.toLowerCase().includes(needle)
        ? columns : allColumns).map((c) => ({
        key: `c:${name}:${c.name}`, label: c.name, type: "column",
        insert: c.name,
      })),
    });
  }
  return out;
});

const datasourceName = computed(() => {
  const found = datasources.value.find((d) => d.id === datasourceId.value);
  return found ? found.name : "-";
});

const chartOption = computed(() => {
  if (!result.value || !chartDim.value || !chartVal.value) return null;
  return buildChartOption({
    type: chartType.value,
    rows: result.value.rows || [],
    columns: result.value.columns || [],
    dimension: chartDim.value,
    value: chartVal.value,
  });
});

function fmt(value) {
  return value ? new Date(value).toLocaleString() : "-";
}

async function openPlan() {
  if (!datasourceId.value) {
    ElMessage.error(t("wb.chooseSource"));
    return;
  }
  planOpen.value = true;
  planError.value = "";
  plan.value = { columns: [], rows: [], ms: 0 };
  try {
    plan.value = await api.post("/workbench/explain", {
      datasource_id: datasourceId.value,
      sql: singleSql.value,
    });
  } catch (e) {
    planError.value = errMsg(e);
  }
}

async function openHistory() {
  historyOpen.value = true;
  await loadHistory();
}

async function loadHistory() {
  try {
    runs.value = (await api.get("/query-runs?page_size=50")).items || [];
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function applyRun(row) {
  if (!row.datasource_id) {
    ElMessage.error(t("wb.historyNoSource"));
    return;
  }
  try {
    const detail = await api.get(`/query-runs/${row.id}`);
    tab.value = "single";
    datasourceId.value = row.datasource_id;
    singleSql.value = detail.sql || row.sql_preview;
    historyOpen.value = false;
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

function applyTab(index) {
  const tab = queryTabs.value[index];
  if (!tab) return;
  activeTab.value = index;
  datasourceId.value = tab.datasourceId;
  singleSql.value = tab.sql;
  limit.value = tab.limit;
  result.value = tab.result;
  error.value = tab.error;
  resultView.value = "table";
}

function snapshotTab() {
  const tab = queryTabs.value[activeTab.value];
  if (!tab) return;
  tab.datasourceId = datasourceId.value;
  tab.sql = singleSql.value;
  tab.limit = limit.value;
  tab.result = result.value;
  tab.error = error.value;
}

function activateTab(index) {
  if (index === activeTab.value) return;
  snapshotTab();
  applyTab(index);
}

function addTab() {
  snapshotTab();
  tabSeq += 1;
  const tab = {
    id: `q_${Date.now()}_${tabSeq}`,
    name: t("wb.queryName").replace("{n}", queryTabs.value.length + 1),
    datasourceId: datasourceId.value,
    sql: "select 1 as n",
    limit: limit.value,
    result: null,
    error: "",
  };
  queryTabs.value.push(tab);
  applyTab(queryTabs.value.length - 1);
  nextTick(() => editorRef.value?.focus?.());
}

function closeTab(index) {
  if (queryTabs.value.length <= 1) return;
  const wasActive = index === activeTab.value;
  queryTabs.value.splice(index, 1);
  if (wasActive) {
    applyTab(Math.min(index, queryTabs.value.length - 1));
  } else if (index < activeTab.value) {
    activeTab.value -= 1;
  }
}

function insertSchema(node) {
  if (!node?.insert) return;
  editorRef.value?.insert(`${node.insert} `);
}

async function formatSql() {
  if (!singleSql.value.trim()) return;
  formatting.value = true;
  try {
    const out = await api.post("/workbench/format", {
      sql: singleSql.value,
    });
    singleSql.value = out.sql;
    snapshotTab();
    ElMessage.success(t("wb.formatted"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    formatting.value = false;
  }
}

async function loadDatasources() {
  try {
    const list = await api.get("/datasources");
    datasources.value = list.filter(
      (d) => !d.capabilities || d.capabilities.query);
    if (!datasourceId.value && datasources.value.length) {
      datasourceId.value = datasources.value[0].id;
    }
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function loadTables(id) {
  if (!id) return;
  schemaLoading.value = true;
  try {
    tables.value[id] = await api.get(`/datasources/${id}/tables`);
  } catch (e) {
    tables.value[id] = [];
    ElMessage.error(errMsg(e));
  } finally {
    schemaLoading.value = false;
  }
}

function addSource() {
  const n = sources.value.length + 1;
  sources.value.push({ alias: `t${n}`, datasource_id: null, table: "" });
}

function removeSource(i) {
  if (sources.value.length <= 1) return;
  sources.value.splice(i, 1);
}

async function runSingle() {
  if (!datasourceId.value) {
    ElMessage.error(t("wb.chooseSource"));
    return;
  }
  await run("/workbench/query", {
    datasource_id: datasourceId.value,
    sql: singleSql.value,
    limit: limit.value,
  });
}

async function runFederated() {
  if (sources.value.some((s) => !s.datasource_id || !s.table ||
                                 !s.alias)) {
    ElMessage.error(t("wb.fillSources"));
    return;
  }
  await run("/workbench/federated", {
    sources: sources.value.map((s) => ({
      alias: s.alias, datasource_id: s.datasource_id, table: s.table,
    })),
    sql: fedSql.value,
    limit: limit.value,
  });
}

async function run(path, body) {
  loading.value = true;
  error.value = "";
  result.value = null;
  try {
    result.value = await api.post(path, body);
    chartDim.value = result.value.columns?.[0] || "";
    chartVal.value = result.value.columns?.[result.value.columns.length - 1]
      || "";
    chartType.value = "bar";
    resultView.value = "table";
    if (path === "/workbench/query") snapshotTab();
  } catch (e) {
    error.value = errMsg(e);
  } finally {
    loading.value = false;
  }
}

function exportCsv() {
  if (!result.value) return;
  const cols = result.value.columns;
  const esc = (v) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [cols.map(esc).join(",")];
  for (const row of result.value.rows) {
    lines.push(cols.map((c) => esc(row[c])).join(","));
  }
  const blob = new Blob([lines.join("\n")], {
    type: "text/csv;charset=utf-8",
  });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "query-result.csv";
  a.click();
  URL.revokeObjectURL(a.href);
}

async function loadSaved() {
  try {
    saved.value = (await api.get("/saved-queries")).items || [];
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

function openSaved() {
  savedOpen.value = true;
  loadSaved();
}

async function saveQuery() {
  try {
    const { value } = await ElMessageBox.prompt(
      t("wb.saveQueryPrompt"), t("wb.saveQuery"),
      { inputPattern: /\S+/, inputErrorMessage: t("wb.saveQueryName") });
    await api.post("/saved-queries", {
      name: value.trim(), tab: tab.value,
      datasource_id: tab.value === "single" ? datasourceId.value : null,
      sql: tab.value === "single" ? singleSql.value : fedSql.value,
      sources: tab.value === "federated" ? sources.value : [],
      limit: limit.value,
    });
    ElMessage.success(t("wb.saved"));
    await loadSaved();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

function applySaved(row) {
  tab.value = row.tab;
  limit.value = row.limit || 1000;
  if (row.tab === "single") {
    datasourceId.value = row.datasource_id;
    singleSql.value = row.sql || "";
  } else {
    sources.value = row.sources?.length
      ? row.sources : [{ alias: "t1", datasource_id: null, table: "" }];
    fedSql.value = row.sql || "";
    for (const s of sources.value) {
      if (s.datasource_id) loadTables(s.datasource_id);
    }
  }
  savedOpen.value = false;
  if (row.tab === "single") snapshotTab();
}

async function removeSaved(row) {
  try {
    await ElMessageBox.confirm(t("wb.deleteSavedConfirm"),
                               t("wb.savedQueries"));
    await api.del(`/saved-queries/${row.id}`);
    await loadSaved();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

watch(datasourceId, (id) => {
  if (id) loadTables(id);
});

onMounted(async () => {
  await loadDatasources();
  tabSeq = 1;
  queryTabs.value = [{
    id: `q_${Date.now()}_1`,
    name: t("wb.queryName").replace("{n}", 1),
    datasourceId: datasourceId.value,
    sql: singleSql.value,
    limit: limit.value,
    result: null,
    error: "",
  }];
  activeTab.value = 0;
  for (const s of sources.value) {
    if (s.datasource_id) await loadTables(s.datasource_id);
  }
});
</script>

<style scoped>
.wb-page { background: #f8fafc; border: 1px solid #e5e7eb;
           border-radius: 10px; padding: 14px; }
.head { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.spacer { flex: 1; }
.panel :deep(.el-tabs__header) { margin-bottom: 10px; }
.toolbar { display: flex; align-items: center; gap: 8px; margin: 6px 0; }
.query-tabs { display: flex; align-items: center; gap: 4px;
              border-bottom: 1px solid #e5e7eb; margin-bottom: 8px;
              overflow-x: auto; }
.query-tab { border: 1px solid #e5e7eb; border-bottom: none;
             background: #f8fafc; padding: 5px 10px; font-size: 12px;
             color: #475569; cursor: pointer; display: inline-flex;
             gap: 6px; align-items: center; white-space: nowrap; }
.query-tab.active { background: #fff; color: #1d4ed8; font-weight: 600; }
.tab-close { color: #94a3b8; }
.query-layout { display: grid; grid-template-columns: 220px minmax(0, 1fr);
                gap: 10px; min-height: 360px; }
.schema-panel { border: 1px solid #e5e7eb; background: #fff;
                padding: 6px; overflow: auto; max-height: 460px; }
.schema-head { display: flex; align-items: center;
               justify-content: space-between; margin-bottom: 6px;
               font-size: 12px; }
.schema-panel :deep(.el-tree) { margin-top: 4px; font-size: 12px; }
.query-main { min-width: 0; }
.chart-controls { display: flex; gap: 8px; margin-bottom: 8px;
                  flex-wrap: wrap; }
.inspector-pre { background: #0f172a; color: #e2e8f0; padding: 10px;
                 border-radius: 6px; font-size: 12px; max-height: 380px;
                 overflow: auto; white-space: pre-wrap; }
.hint { font-size: 12px; color: #6b7280; }
.saved-row {
  display: flex; align-items: center; gap: 8px;
  border-bottom: 1px solid #eef2f7; padding: 8px 0;
}
.saved-main { flex: 1; display: flex; flex-direction: column; align-items: flex-start;
  gap: 2px; background: none; border: 0; cursor: pointer;
  text-align: left; padding: 0;
}
.saved-main b { font-size: 13px; }
.saved-main small { color: #64748b; font-size: 11px; }
.federation { display: flex; flex-direction: column; gap: 6px; }
.source-row { display: flex; align-items: center; gap: 6px; }
.result { margin-top: 14px; background: #fff; border: 1px solid #e5e7eb;
          border-radius: 8px; padding: 10px; }
.result-head { display: flex; align-items: center; gap: 10px;
               margin-bottom: 8px; font-size: 12px; color: #475569;
               flex-wrap: wrap; }
.result-chart { height: 360px; width: 100%; }
.hist-row { border-bottom: 1px solid #eef2f7; padding: 10px 2px; cursor: pointer; }
.hist-row:hover { background: #f8fafc; }
.hist-top { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.hist-source { font-size: 12px; color: #334155; }
.hist-meta { font-size: 11px; color: #94a3b8; margin-left: auto; }
.hist-sql { font-family: ui-monospace, Menlo, Consolas, monospace;
            font-size: 12px; color: #1e293b; white-space: nowrap;
            overflow: hidden; text-overflow: ellipsis; }
.hist-error { font-size: 12px; color: #b91c1c; margin-top: 2px; }
</style>
