<template>
  <div class="model-page">
    <div class="head">
      <el-button link @click="$router.push('/metrics')">←</el-button>
      <el-input v-model="name" size="small" style="width: 220px"
                @change="rename" />
      <el-tag size="small" :type="published ? 'success' : 'info'">
        {{ published ? "已发布" : "草稿" }}
      </el-tag>
      <div class="spacer" />
      <el-button size="small" @click="save">保存</el-button>
      <el-button size="small" @click="validate">校验</el-button>
      <el-button size="small" :loading="querying" @click="preview">预览</el-button>
      <el-button size="small" type="primary" @click="publish">发布</el-button>
      <el-button size="small" @click="versionsOpen = true">版本</el-button>
    </div>

    <div class="body">
      <aside class="form">
        <el-form label-width="86px" size="small">
          <el-form-item label="数据集">
            <el-select v-model="content.dataset_id" filterable
                       style="width: 100%" @change="loadSchema">
              <el-option v-for="d in datasets" :key="d.id" :value="d.id"
                         :label="d.name" />
            </el-select>
          </el-form-item>
          <el-form-item label="聚合">
            <el-select v-model="content.measure.agg" style="width: 100%">
              <el-option v-for="a in aggs" :key="a" :value="a" :label="a" />
            </el-select>
          </el-form-item>
          <el-form-item label="度量列">
            <el-select v-model="content.measure.column" filterable
                       style="width: 100%">
              <el-option v-for="c in columnOptions" :key="c" :value="c"
                         :label="c" />
            </el-select>
          </el-form-item>
          <el-form-item label="输出名">
            <el-input v-model="content.measure.as" />
          </el-form-item>
          <el-form-item label="维度">
            <el-select v-model="content.dimensions" multiple filterable
                       style="width: 100%">
              <el-option v-for="c in columns" :key="c" :value="c" :label="c" />
            </el-select>
          </el-form-item>
        </el-form>

        <h4>过滤</h4>
        <div v-for="(f, i) in content.filters" :key="i" class="row">
          <el-select v-model="f.column" filterable style="width: 130px">
            <el-option v-for="c in columns" :key="c" :value="c" :label="c" />
          </el-select>
          <el-select v-model="f.op" style="width: 90px">
            <el-option v-for="op in ['=','!=','>','>=','<','<=','like']"
                       :key="op" :value="op" :label="op" />
          </el-select>
          <el-input v-model="f.value" placeholder="值" />
          <el-button link type="danger"
                     @click="content.filters.splice(i, 1)">×</el-button>
        </div>
        <el-button link type="primary"
                   @click="content.filters.push({ column: '', op: '=', value: '' })">
          + 过滤
        </el-button>

        <h4>格式</h4>
        <el-form label-width="86px" size="small">
          <el-form-item label="类型">
            <el-select v-model="content.format.type" style="width: 100%">
              <el-option value="number" label="数字" />
              <el-option value="percent" label="百分比" />
              <el-option value="currency" label="金额" />
            </el-select>
          </el-form-item>
          <el-form-item label="单位">
            <el-input v-model="content.format.unit" />
          </el-form-item>
          <el-form-item label="小数位">
            <el-input-number v-model="content.format.decimals" :min="0" :max="6" />
          </el-form-item>
        </el-form>
        <p v-if="!publishedDatasets.length" class="hint">
          先发布一个数据集，指标才能引用它。
        </p>
      </aside>

      <main class="result">
        <el-table v-if="rows.length" :data="rows" size="small" height="420">
          <el-table-column v-for="c in resultColumns" :key="c" :prop="c"
                           :label="c" />
        </el-table>
        <el-empty v-else description="预览后显示聚合结果" :image-size="70" />
        <div v-if="stats" class="stats">{{ stats }}</div>
        <pre v-if="sql" class="sql">{{ sql }}</pre>
      </main>
    </div>

    <el-drawer v-model="versionsOpen" title="版本" size="480px"
               @open="loadVersions">
      <el-table :data="versions" size="small">
        <el-table-column prop="version" label="版本" width="70" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="created_by" label="创建人" />
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button link :disabled="row.current || row.status === 'draft'"
                       @click="rollback(row)">回滚</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../api";

const route = useRoute();
const id = Number(route.params.id);
const name = ref("");
const published = ref(false);
const datasets = ref([]);
const columns = ref([]);
const rows = ref([]);
const resultColumns = ref([]);
const stats = ref("");
const sql = ref("");
const querying = ref(false);
const versions = ref([]);
const versionsOpen = ref(false);
const aggs = ["sum", "count", "avg", "min", "max"];
const content = ref({
  dataset_id: null,
  measure: { agg: "sum", column: "", as: "value" },
  dimensions: [],
  filters: [],
  format: { type: "number", unit: "", decimals: 2 },
});
const publishedDatasets = computed(
  () => datasets.value.filter((d) => d.published));
const columnOptions = computed(() => {
  if (content.value.measure.agg === "count") return ["*", ...columns.value];
  return columns.value;
});

async function load() {
  const a = await api.get(`/metrics/${id}`);
  name.value = a.name;
  published.value = Boolean(a.published);
  const draft = a.draft || {};
  content.value = {
    dataset_id: draft.dataset_id || null,
    measure: { agg: "sum", column: "", as: "value",
               ...(draft.measure || {}) },
    dimensions: draft.dimensions || [],
    filters: draft.filters || [],
    format: { type: "number", unit: "", decimals: 2,
              ...(draft.format || {}) },
  };
  datasets.value = (await api.get("/datasets")).filter((d) => d.published);
  if (content.value.dataset_id) await loadSchema();
}

async function loadSchema() {
  columns.value = [];
  if (!content.value.dataset_id) return;
  try {
    const s = await api.get(`/datasets/${content.value.dataset_id}/schema`);
    columns.value = s.columns.map((c) => c.name);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function save() {
  try {
    await api.put(`/metrics/${id}/draft`, { content: content.value });
    ElMessage.success("已保存草稿");
    return true;
  } catch (e) {
    ElMessage.error(errMsg(e));
    return false;
  }
}

async function rename() {
  try {
    await api.put(`/metrics/${id}`, { name: name.value });
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function validate() {
  try {
    const r = await api.post(`/metrics/${id}/validate`,
                             { content: content.value });
    if (r.valid) ElMessage.success("校验通过");
    else ElMessage.error(r.errors.map((e) => e.message).join("; "));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function preview() {
  querying.value = true;
  try {
    const r = await api.post(`/metrics/${id}/query`, {
      limit: 100, content: content.value,
    });
    rows.value = r.rows || [];
    resultColumns.value = r.columns || [];
    stats.value = `${r.row_count} 行 · ${r.ms}ms`;
    sql.value = r.sql || "";
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    querying.value = false;
  }
}

async function publish() {
  const ok = await save();
  if (!ok) return;
  try {
    await api.applyChange("publish_metric", id);
    await load();
    ElMessage.success("已发布");
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function loadVersions() {
  versions.value = await api.get(`/metrics/${id}/versions`);
}

async function rollback(row) {
  try {
    await ElMessageBox.confirm(`回滚到版本 ${row.version}？`, "回滚确认");
    await api.applyChange("rollback_metric", id, { version: row.version });
    await load();
    await loadVersions();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

onMounted(load);
</script>

<style scoped>
.model-page { height: calc(100vh - 104px); display: flex; flex-direction: column;
              background: #f8fafc; border: 1px solid #e5e7eb;
              border-radius: 10px; overflow: hidden; }
.head { height: 52px; display: flex; align-items: center; gap: 8px;
        padding: 0 12px; background: #fff; border-bottom: 1px solid #e5e7eb; }
.spacer { flex: 1; }
.body { flex: 1; display: grid; grid-template-columns: 420px 1fr;
        min-height: 0; }
.form { background: #fff; border-right: 1px solid #e5e7eb; overflow: auto;
        padding: 12px; }
.result { overflow: auto; padding: 12px; }
.row { display: flex; gap: 6px; margin-bottom: 6px; align-items: center; }
h4 { margin: 14px 0 8px; font-size: 13px; color: #374151; }
.stats { margin-top: 8px; font-size: 12px; color: #475569; }
.sql { background: #0f172a; color: #e2e8f0; padding: 8px; border-radius: 6px;
       font-size: 11px; white-space: pre-wrap; }
.hint { color: #b45309; font-size: 12px; }
</style>
