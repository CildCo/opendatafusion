<template>
  <div class="wb-page">
    <div class="head">
      <el-tag size="small" type="info">只读</el-tag>
      <div class="spacer" />
      <el-button size="small" @click="loadDatasources">刷新数据源</el-button>
    </div>

    <el-tabs v-model="tab" class="panel">
      <el-tab-pane label="单源查询" name="single">
        <div class="toolbar">
          <el-select v-model="datasourceId" placeholder="选择数据源"
                     size="small" style="width: 220px">
            <el-option v-for="d in datasources" :key="d.id" :value="d.id"
                       :label="`${d.name} (${d.kind})`" />
          </el-select>
          <span class="hint">行数上限</span>
          <el-input-number v-model="limit" :min="1" :max="10000"
                           size="small" :controls="false"
                           style="width: 90px" />
          <div class="spacer" />
          <el-button type="primary" size="small" :loading="loading"
                     @click="runSingle">执行</el-button>
        </div>
        <SqlEditor v-model="singleSql" />
      </el-tab-pane>

      <el-tab-pane label="跨源查询" name="federated">
        <div class="federation">
          <div v-for="(s, i) in sources" :key="i" class="source-row">
            <el-input v-model="s.alias" size="small" placeholder="别名"
                      style="width: 100px" />
            <el-select v-model="s.datasource_id" size="small"
                       placeholder="数据源" style="width: 190px"
                       @change="loadTables(s.datasource_id)">
              <el-option v-for="d in datasources" :key="d.id" :value="d.id"
                         :label="d.name" />
            </el-select>
            <el-select v-model="s.table" size="small" filterable
                       placeholder="表" style="width: 220px">
              <el-option v-for="t in tables[s.datasource_id] || []"
                         :key="(t.schema ? t.schema + '.' : '') + t.table"
                         :value="(t.schema ? t.schema + '.' : '') + t.table"
                         :label="(t.schema ? t.schema + '.' : '') + t.table" />
            </el-select>
            <el-button link type="danger" size="small"
                       @click="removeSource(i)">×</el-button>
          </div>
          <el-button size="small" :disabled="sources.length >= 4"
                     @click="addSource">+ 数据源</el-button>
          <span class="hint">
            每个表会物化到 DuckDB，单源最多 2 万行；最多 4 个源。
          </span>
        </div>
        <div class="toolbar">
          <span class="hint">行数上限</span>
          <el-input-number v-model="limit" :min="1" :max="10000"
                           size="small" :controls="false"
                           style="width: 90px" />
          <div class="spacer" />
          <el-button type="primary" size="small" :loading="loading"
                     @click="runFederated">执行</el-button>
        </div>
        <SqlEditor v-model="fedSql" />
      </el-tab-pane>
    </el-tabs>

    <div v-if="error" class="result">
      <el-alert :title="error" type="error" :closable="false" />
    </div>
    <div v-else-if="result" class="result">
      <div class="result-head">
        <span>{{ result.row_count }} 行 · {{ result.ms }} ms</span>
        <el-tag v-if="result.truncated" size="small" type="warning">
          已截断
        </el-tag>
        <div class="spacer" />
        <el-button size="small" @click="exportCsv">导出 CSV</el-button>
      </div>
      <el-table :data="result.rows" size="small" height="380" border>
        <el-table-column v-for="c in result.columns" :key="c" :prop="c"
                         :label="c" min-width="130" show-overflow-tooltip />
      </el-table>
    </div>
    <el-empty v-else description="执行一条查询查看结果" />
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { api, errMsg } from "../api";
import SqlEditor from "../studio/api/SqlEditor.vue";

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

async function loadDatasources() {
  try {
    datasources.value = await api.get("/datasources");
    if (!datasourceId.value && datasources.value.length) {
      datasourceId.value = datasources.value[0].id;
    }
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function loadTables(id) {
  if (!id) return;
  try {
    tables.value[id] = await api.get(`/datasources/${id}/tables`);
  } catch (e) {
    tables.value[id] = [];
    ElMessage.error(errMsg(e));
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
    ElMessage.error("请选择数据源");
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
    ElMessage.error("请完整填写每个数据源的别名、数据源和表");
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

onMounted(async () => {
  await loadDatasources();
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
.hint { font-size: 12px; color: #6b7280; }
.federation { display: flex; flex-direction: column; gap: 6px; }
.source-row { display: flex; align-items: center; gap: 6px; }
.result { margin-top: 14px; background: #fff; border: 1px solid #e5e7eb;
          border-radius: 8px; padding: 10px; }
.result-head { display: flex; align-items: center; gap: 10px;
               margin-bottom: 8px; font-size: 12px; color: #475569; }
</style>
