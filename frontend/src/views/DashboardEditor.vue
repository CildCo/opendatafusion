<template>
  <div class="dash-page">
    <div class="head">
      <el-button link @click="$router.push('/dashboards')">←</el-button>
      <el-input v-model="name" size="small" style="width: 220px"
                @change="rename" />
      <el-tag size="small" :type="published ? 'success' : 'info'">
        {{ published ? "已发布" : "草稿" }}
      </el-tag>
      <div class="spacer" />
      <el-button size="small" @click="save">保存</el-button>
      <el-button size="small" @click="validate">校验</el-button>
      <el-button size="small" :loading="loadingData" @click="refresh">刷新数据</el-button>
      <el-button size="small" type="primary" @click="publish">发布</el-button>
      <el-button size="small" @click="versionsOpen = true">版本</el-button>
      <el-button size="small" :disabled="!published"
                 @click="$router.push(`/dashboards/${id}/run`)">
        运行
      </el-button>
      <ShareDialog kind="dashboards" :asset-id="id"
                   :published="published" />
    </div>

    <div class="body">
      <aside class="palette">
        <div class="label">组件</div>
        <el-button v-for="t in types" :key="t.type" size="small"
                   class="add" @click="add(t)">
          {{ t.label }}
        </el-button>
        <div class="label" style="margin-top: 14px">筛选参数</div>
        <div v-for="(p, i) in content.params" :key="i" class="param-row">
          <el-input v-model="p.name" size="small" placeholder="name"
                    @change="resetParams" />
          <el-select v-model="p.type" size="small" style="width: 88px"
                     @change="resetParams">
            <el-option v-for="t in paramTypes" :key="t" :value="t"
                       :label="t" />
          </el-select>
          <el-input v-model="p.default" size="small" placeholder="默认值"
                    @change="resetParams" />
          <el-button link type="danger" size="small"
                     @click="removeParam(i)">×</el-button>
        </div>
        <el-button size="small" class="add" @click="addParam">
          + 参数
        </el-button>
        <p class="hint">拖动组件标题移动，右下角缩放。</p>
      </aside>

      <main class="canvas">
        <DashboardFilters :params="content.params || []"
                          :value="paramValues"
                          @update:value="setParams"
                          @refresh="refresh" />
        <DashboardGrid :widgets="content.widgets" :data="data"
                       :columns="content.columns"
                       :row-height="content.row_height"
                       :selected-id="selected?.id || ''"
                       @select="selectWidget" @change="dirty = true"
                       @filter="onFilter" />
      </main>

      <aside class="config">
        <template v-if="selected">
          <div class="config-head">
            <h4>{{ selected.type }} 配置</h4>
            <el-button link type="danger" @click="removeWidget">删除</el-button>
          </div>
          <el-form label-width="76px" size="small">
            <el-form-item label="标题">
              <el-input v-model="selected.title" />
            </el-form-item>
            <template v-if="selected.type !== 'text'">
              <el-form-item label="筛选">
                <div class="filter-list">
                  <div v-for="(f, i) in selected.filters || []" :key="i"
                       class="filter-row">
                    <el-select v-model="f.column" size="small" filterable
                               allow-create placeholder="列"
                               style="width: 96px">
                      <el-option v-for="c in filterColumns" :key="c"
                                 :value="c" :label="c" />
                    </el-select>
                    <el-select v-model="f.op" size="small"
                               style="width: 82px">
                      <el-option v-for="op in ops" :key="op" :value="op"
                                 :label="op" />
                    </el-select>
                    <el-select v-model="f.param" size="small"
                               placeholder="参数" style="width: 84px">
                      <el-option v-for="p in content.params" :key="p.name"
                                 :value="p.name" :label="p.name" />
                    </el-select>
                    <el-button link type="danger" size="small"
                               @click="removeFilter(i)">×</el-button>
                  </div>
                  <el-button link size="small"
                             :disabled="!content.params.length"
                             @click="addFilter">+ 条件</el-button>
                </div>
              </el-form-item>
              <el-form-item v-if="['line','bar','pie','table'].includes(selected.type)"
                            label="点击联动">
                <div v-if="selected.emit" class="filter-row">
                  <el-select v-model="selected.emit.param" size="small"
                             placeholder="参数" style="width: 92px">
                    <el-option v-for="p in content.params" :key="p.name"
                               :value="p.name" :label="p.name" />
                  </el-select>
                  <el-select v-if="isChart" :model-value="selected.dimension"
                             size="small" disabled style="width: 92px">
                    <el-option :value="selected.dimension"
                               :label="selected.dimension" />
                  </el-select>
                  <el-select v-else v-model="selected.emit.from" size="small"
                             filterable allow-create placeholder="列"
                             style="width: 92px">
                    <el-option v-for="c in filterColumns" :key="c" :value="c"
                               :label="c" />
                  </el-select>
                  <el-button link type="danger" size="small"
                             @click="selected.emit = null">×</el-button>
                </div>
                <el-button v-else link size="small"
                           :disabled="!content.params.length"
                           @click="enableEmit">启用</el-button>
              </el-form-item>
            </template>
            <template v-if="['card','line','bar','pie'].includes(selected.type)">
              <el-form-item label="指标">
                <el-select v-model="selected.metric_id" filterable clearable
                           style="width: 100%" @change="loadMetric">
                  <el-option v-for="m in metrics" :key="m.id" :value="m.id"
                             :label="m.name" />
                </el-select>
              </el-form-item>
              <el-form-item v-if="['line','bar','pie'].includes(selected.type)"
                            label="维度">
                <el-select v-model="selected.dimension" filterable
                           style="width: 100%" @change="syncEmit">
                  <el-option v-for="d in metricDims" :key="d" :value="d"
                             :label="d" />
                </el-select>
              </el-form-item>
              <el-form-item label="数值列">
                <el-select v-model="selected.value_column" filterable
                           clearable style="width: 100%">
                  <el-option v-for="c in valueOptions" :key="c" :value="c"
                             :label="c" />
                </el-select>
              </el-form-item>
            </template>
            <template v-if="selected.type === 'table'">
              <el-form-item label="数据集">
                <el-select v-model="selected.dataset_id" filterable clearable
                           style="width: 100%"
                           @change="selected.metric_id = null">
                  <el-option v-for="d in datasets" :key="d.id" :value="d.id"
                             :label="d.name" />
                </el-select>
              </el-form-item>
              <el-form-item label="指标">
                <el-select v-model="selected.metric_id" filterable clearable
                           style="width: 100%"
                           @change="selected.dataset_id = null">
                  <el-option v-for="m in metrics" :key="m.id" :value="m.id"
                             :label="m.name" />
                </el-select>
              </el-form-item>
              <el-form-item label="行数">
                <el-input-number v-model="selected.limit" :min="1"
                                 :max="10000" />
              </el-form-item>
            </template>
            <el-form-item v-if="selected.type === 'text'" label="文本">
              <el-input v-model="selected.text" type="textarea" :rows="4" />
            </el-form-item>
            <el-form-item label="位置">
              <div class="layout">
                <el-input-number v-model="selected.x" :min="0"
                                 :max="content.columns - 1" />
                <el-input-number v-model="selected.y" :min="0" />
                <el-input-number v-model="selected.w" :min="1"
                                 :max="content.columns" />
                <el-input-number v-model="selected.h" :min="1" />
              </div>
            </el-form-item>
          </el-form>
        </template>
        <el-empty v-else description="添加或选择组件" :image-size="60" />
      </aside>
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
import DashboardGrid from "../studio/dashboard/DashboardGrid.vue";
import DashboardFilters from "../studio/dashboard/DashboardFilters.vue";
import ShareDialog from "../studio/share/ShareDialog.vue";

const route = useRoute();
const id = Number(route.params.id);
const name = ref("");
const published = ref(false);
const content = ref({ columns: 12, row_height: 80, params: [],
                      widgets: [] });
const paramValues = ref({});
const paramTypes = ["string", "number", "date", "bool"];
const ops = ["=", "!=", ">", ">=", "<", "<=", "in", "like",
             "is null", "is not null"];
const data = ref({});
const selected = ref(null);
const metrics = ref([]);
const datasets = ref([]);
const metricContent = ref(null);
const loadingData = ref(false);
const versions = ref([]);
const versionsOpen = ref(false);
const dirty = ref(false);
const types = [
  { type: "card", label: "指标卡" },
  { type: "line", label: "折线图" },
  { type: "bar", label: "柱状图" },
  { type: "pie", label: "饼图" },
  { type: "table", label: "表格" },
  { type: "text", label: "文本" },
];

const metricDims = computed(
  () => metricContent.value?.dimensions || []);
const isChart = computed(
  () => ["line", "bar", "pie"].includes(selected.value?.type));
const filterColumns = computed(() => {
  const wid = selected.value?.id;
  return data.value?.[wid]?.columns || [];
});
const valueOptions = computed(() => {
  const m = metricContent.value;
  if (!m) return [];
  const alias = (m.measure || {}).as || "value";
  return [...new Set([...(m.dimensions || []), alias])];
});

async function load() {
  const a = await api.get(`/dashboards/${id}`);
  name.value = a.name;
  published.value = Boolean(a.published);
  const selId = selected.value?.id;
  const draft = a.draft || {};
  content.value = {
    columns: draft.columns || 12,
    row_height: draft.row_height || 80,
    params: draft.params || [],
    widgets: draft.widgets || [],
  };
  resetParams();
  selected.value = selId
    ? content.value.widgets.find((w) => w.id === selId) || null
    : null;
  metrics.value = (await api.get("/metrics")).filter((m) => m.published);
  datasets.value = (await api.get("/datasets")).filter((d) => d.published);
  if (selected.value) await loadMetric();
  if (content.value.widgets.length) await refresh();
}

function add(t) {
  const y = content.value.widgets.reduce(
    (m, w) => Math.max(m, w.y + w.h), 0);
  const widget = {
    id: `w_${Date.now()}_${content.value.widgets.length}`,
    type: t.type,
    title: t.label,
    x: 0, y, w: t.type === "card" || t.type === "text" ? 3 : 6,
    h: t.type === "card" || t.type === "text" ? 2 : 4,
    filters: [],
  };
  if (["card", "line", "bar", "pie"].includes(t.type)) {
    widget.metric_id = metrics.value[0]?.id || null;
    if (["line", "bar", "pie"].includes(t.type)) widget.dimension = "";
  }
  if (t.type === "table") {
    widget.dataset_id = datasets.value[0]?.id || null;
    widget.limit = 100;
  }
  if (t.type === "text") widget.text = "文本";
  content.value.widgets.push(widget);
  selected.value = widget;
  dirty.value = true;
  loadMetric();
}

function selectWidget(w) {
  selected.value = w;
  loadMetric();
}

function removeWidget() {
  if (!selected.value) return;
  const id = selected.value.id;
  content.value.widgets = content.value.widgets.filter((w) => w.id !== id);
  delete data.value[id];
  selected.value = null;
  dirty.value = true;
}

async function loadMetric() {
  metricContent.value = null;
  const mid = selected.value?.metric_id;
  const wid = selected.value?.id;
  if (!mid) return;
  try {
    const m = await api.get(`/metrics/${mid}`);
    if (!selected.value || selected.value.id !== wid
        || selected.value.metric_id !== mid) return;
    const content = m.published || m.draft;
    metricContent.value = content;
    const dims = content?.dimensions || [];
    const alias = (content?.measure || {}).as || "value";
    const cols = [...dims, alias];
    if (!selected.value.value_column
        || !cols.includes(selected.value.value_column)) {
      selected.value.value_column = alias;
    }
    if (selected.value.dimension
        && !dims.includes(selected.value.dimension)) {
      selected.value.dimension = "";
    }
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function refresh() {
  loadingData.value = true;
  try {
    const r = await api.post(`/dashboards/${id}/data`, {
      limit: 100, params: paramValues.value, content: content.value,
    });
    data.value = r.widgets || {};
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loadingData.value = false;
  }
}

function resetParams() {
  const values = {};
  for (const p of content.value.params || []) {
    if (p.name) values[p.name] = p.default ?? "";
  }
  paramValues.value = values;
}

function setParams(p) {
  paramValues.value = { ...p };
}

function onFilter({ param, value }) {
  if (!param) return;
  paramValues.value = { ...paramValues.value, [param]: value };
  refresh();
}

function addParam() {
  const used = new Set((content.value.params || []).map((p) => p.name));
  let n = (content.value.params || []).length + 1;
  while (used.has(`p${n}`)) n += 1;
  content.value.params = content.value.params || [];
  content.value.params.push({ name: `p${n}`, type: "string",
                              default: "", required: false });
  resetParams();
}

function removeParam(i) {
  const p = content.value.params[i];
  content.value.params.splice(i, 1);
  for (const w of content.value.widgets) {
    w.filters = (w.filters || []).filter((f) => f.param !== p.name);
    if (w.emit?.param === p.name) w.emit = null;
  }
  resetParams();
}

function addFilter() {
  if (!selected.value) return;
  selected.value.filters = selected.value.filters || [];
  selected.value.filters.push({
    column: filterColumns.value[0] || "",
    op: "=",
    param: content.value.params[0]?.name || "",
  });
}

function removeFilter(i) {
  selected.value.filters.splice(i, 1);
}

function enableEmit() {
  if (!selected.value) return;
  selected.value.emit = {
    param: content.value.params[0]?.name || "",
    from: isChart.value
      ? (selected.value.dimension || "")
      : (filterColumns.value[0] || ""),
  };
}

function syncEmit() {
  if (selected.value?.emit && isChart.value) {
    selected.value.emit.from = selected.value.dimension || "";
  }
}

async function save() {
  try {
    await api.put(`/dashboards/${id}/draft`, { content: content.value });
    dirty.value = false;
    ElMessage.success("已保存草稿");
    return true;
  } catch (e) {
    ElMessage.error(errMsg(e));
    return false;
  }
}

async function rename() {
  try {
    await api.put(`/dashboards/${id}`, { name: name.value });
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function validate() {
  try {
    const r = await api.post(`/dashboards/${id}/validate`,
                             { content: content.value });
    if (r.valid) ElMessage.success("校验通过");
    else ElMessage.error(r.errors.map((e) => e.message).join("; "));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function publish() {
  const ok = await save();
  if (!ok) return;
  try {
    await api.applyChange("publish_dashboard", id);
    await load();
    ElMessage.success("已发布");
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function loadVersions() {
  versions.value = await api.get(`/dashboards/${id}/versions`);
}

async function rollback(row) {
  try {
    await ElMessageBox.confirm(`回滚到版本 ${row.version}？`, "回滚确认");
    await api.applyChange("rollback_dashboard", id, { version: row.version });
    await load();
    await loadVersions();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

onMounted(load);
</script>

<style scoped>
.dash-page { height: calc(100vh - 104px); display: flex; flex-direction: column;
             background: #f8fafc; border: 1px solid #e5e7eb;
             border-radius: 10px; overflow: hidden; }
.head { height: 52px; display: flex; align-items: center; gap: 8px;
        padding: 0 12px; background: #fff; border-bottom: 1px solid #e5e7eb; }
.spacer { flex: 1; }
.body { flex: 1; display: grid; grid-template-columns: 200px 1fr 340px;
        min-height: 0; }
.palette { background: #fff; border-right: 1px solid #e5e7eb; padding: 10px; }
.palette .label { font-size: 13px; font-weight: 600; margin-bottom: 8px; }
.palette .add { width: 100%; margin: 0 0 6px; }
.hint { color: #6b7280; font-size: 11px; margin-top: 10px; }
.canvas { overflow: auto; padding: 10px; }
.config { background: #fff; border-left: 1px solid #e5e7eb; overflow: auto;
          padding: 12px; }
.config-head { display: flex; justify-content: space-between; align-items: center; }
h4 { margin: 0 0 12px; font-size: 13px; }
.layout { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; }
.param-row { display: flex; gap: 3px; align-items: center;
             margin-bottom: 4px; flex-wrap: wrap; }
.param-row :deep(.el-input) { width: 78px; }
.filter-list { width: 100%; }
.filter-row { display: flex; gap: 3px; align-items: center;
              margin-bottom: 4px; flex-wrap: wrap; }
</style>
