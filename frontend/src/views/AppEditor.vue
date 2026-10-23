<template>
  <div class="app-page">
    <div class="head">
      <el-button link @click="$router.push('/apps')">←</el-button>
      <el-input v-model="name" size="small" style="width: 220px"
                @change="rename" />
      <el-tag size="small" :type="published ? 'success' : 'info'">
        {{ published ? "已发布" : "草稿" }}
      </el-tag>
      <div class="spacer" />
      <el-button size="small" @click="save">保存</el-button>
      <el-button size="small" @click="validate">校验</el-button>
      <el-button size="small" :loading="loadingData" @click="refresh">
        刷新数据
      </el-button>
      <el-button size="small" type="primary" @click="publish">发布</el-button>
      <el-button size="small" @click="versionsOpen = true">版本</el-button>
      <el-button size="small" :disabled="!published"
                 @click="$router.push(`/apps/${id}/run`)">
        运行
      </el-button>
      <ShareDialog kind="apps" :asset-id="id" :published="published" />
    </div>

    <div class="body">
      <aside class="left">
        <div class="section">
          <div class="section-head">
            <span>页面</span>
            <el-button link size="small" @click="addPage">+ 页面</el-button>
          </div>
          <div class="pages">
            <div v-for="p in content.pages" :key="p.id" class="page-row"
                 :class="{ active: p.id === currentId }"
                 @click="currentId = p.id">
              <span class="page-title">{{ p.title || p.id }}</span>
              <el-tag v-if="content.start_page === p.id" size="small"
                      type="success">首页</el-tag>
            </div>
          </div>
          <div v-if="currentPage" class="page-actions">
            <el-input v-model="currentPage.title" size="small"
                      placeholder="页面标题" />
            <el-button link size="small" :disabled="content.start_page ===
              currentPage.id" @click="content.start_page = currentPage.id">
              设为首页
            </el-button>
            <el-button link type="danger" size="small"
                       :disabled="content.pages.length <= 1"
                       @click="removePage">删除页</el-button>
          </div>
        </div>

        <div class="section" v-if="currentPage">
          <div class="section-head">
            <span>页面参数</span>
            <el-button link size="small" @click="addParam">+ 参数</el-button>
          </div>
          <div v-for="(p, i) in currentPage.params" :key="i" class="param">
            <el-input v-model="p.name" size="small" placeholder="name"
                      @change="resetParams" />
            <el-select v-model="p.type" size="small" style="width: 92px"
                       @change="resetParams">
              <el-option v-for="t in paramTypes" :key="t" :value="t"
                         :label="t" />
            </el-select>
            <el-input v-model="p.default" size="small" placeholder="默认值"
                      @change="resetParams" />
            <el-checkbox v-model="p.required" size="small">必填</el-checkbox>
            <el-button link type="danger" size="small"
                       @click="removeParam(i)">×</el-button>
          </div>
          <p class="hint">参数名与数据集的参数名一致时自动传入。</p>
        </div>

        <div class="section" v-if="currentPage">
          <div class="section-head"><span>组件</span></div>
          <div class="palette">
            <el-button v-for="t in types" :key="t.type" size="small"
                       class="add" @click="addComponent(t.type)">
              + {{ t.label }}
            </el-button>
          </div>
          <div class="components">
            <div v-for="c in currentPage.components" :key="c.id"
                 class="comp-row" :class="{ active: c.id === selectedId }"
                 @click="selectComponent(c.id)">
              <span>{{ c.title || typeLabel(c.type) }}</span>
              <span class="comp-type">{{ typeLabel(c.type) }}</span>
            </div>
            <el-empty v-if="!currentPage.components.length"
                      description="还没有组件" :image-size="48" />
          </div>
        </div>
      </aside>

      <main class="canvas" v-loading="loadingData">
        <AppRuntime v-if="currentPage" :key="currentPage.id"
                    :page="currentPage" :data="data" :params="paramValues"
                    :on-submit="submitForm"
                    @update:params="setParams" @refresh="refresh" />
      </main>

      <aside class="config">
        <template v-if="selected">
          <div class="config-head">
            <h4>{{ typeLabel(selected.type) }} 配置</h4>
            <el-button link type="danger" @click="removeComponent">
              删除
            </el-button>
          </div>
          <el-form label-width="76px" size="small">
            <el-form-item label="标题">
              <el-input v-model="selected.title" />
            </el-form-item>
            <template v-if="selected.type === 'text'">
              <el-form-item label="文本">
                <el-input v-model="selected.text" type="textarea"
                          :rows="6" />
              </el-form-item>
            </template>
            <template v-if="selected.type === 'metric'">
              <el-form-item label="指标">
                <el-select v-model="selected.metric_id" filterable clearable
                           style="width: 100%"
                           @change="selectMetric(selected.metric_id)">
                  <el-option v-for="m in metrics" :key="m.id" :value="m.id"
                             :label="m.name" />
                </el-select>
              </el-form-item>
              <el-form-item label="数值列">
                <el-select v-model="selected.value_column" filterable clearable
                           style="width: 100%">
                  <el-option v-for="c in modelColumns" :key="c" :value="c"
                             :label="c" />
                </el-select>
              </el-form-item>
            </template>
            <template v-if="selected.type === 'form'">
              <el-form-item label="数据集">
                <el-select v-model="selected.dataset_id" filterable
                           style="width: 100%"
                           @change="selectFormDataset(selected.dataset_id)">
                  <el-option v-for="d in datasets" :key="d.id" :value="d.id"
                             :label="d.name" />
                </el-select>
              </el-form-item>
              <el-form-item label="模式">
                <el-select v-model="selected.mode" style="width: 100%"
                           @change="onFormModeChange">
                  <el-option value="insert" label="新增" />
                  <el-option value="update" label="更新" />
                  <el-option value="delete" label="删除" />
                </el-select>
              </el-form-item>
              <el-form-item label="可提交角色">
                <el-select :model-value="selected.allow_roles || []"
                           multiple clearable placeholder="默认全部"
                           style="width: 100%"
                           @update:model-value="setRoles">
                  <el-option v-for="r in formRoles" :key="r" :value="r"
                             :label="r" />
                </el-select>
              </el-form-item>
              <el-form-item v-if="['update','delete'].includes(selected.mode)"
                            label="主键">
                <el-select v-model="selected.key" filterable
                           allow-create style="width: 100%">
                  <el-option v-for="c in formColumns" :key="c" :value="c"
                             :label="c" />
                </el-select>
              </el-form-item>
              <el-form-item label="字段">
                <div class="filter-list">
                  <div v-for="(f, i) in selected.fields || []" :key="i"
                       class="field-row">
                    <el-select v-model="f.column" size="small" filterable
                               allow-create placeholder="列"
                               style="width: 88px">
                      <el-option v-for="c in formColumns" :key="c" :value="c"
                                 :label="c" />
                    </el-select>
                    <el-input v-model="f.label" size="small"
                              placeholder="标签" style="width: 70px" />
                    <el-select v-model="f.widget" size="small"
                               style="width: 84px">
                      <el-option v-for="w in formWidgets" :key="w"
                                 :value="w" :label="w" />
                    </el-select>
                    <el-checkbox v-model="f.required" size="small">
                      必填
                    </el-checkbox>
                    <el-button link type="danger" size="small"
                               @click="removeField(i)">×</el-button>
                    <el-input v-if="f.widget === 'select'" size="small"
                              :model-value="(f.options || []).join(',')"
                              placeholder="选项,逗号分隔"
                              @update:model-value="setOptions(f, $event)" />
                  </div>
                  <el-button link size="small" @click="addField">
                    + 字段
                  </el-button>
                  <p v-if="selected.mode === 'delete'" class="hint">
                    删除表单只能包含主键字段。
                  </p>
                </div>
              </el-form-item>
              <el-form-item label="按钮">
                <el-input v-model="selected.submit_text"
                          placeholder="提交" />
              </el-form-item>
              <el-form-item label="成功提示">
                <el-input v-model="selected.success_message"
                          placeholder="提交成功" />
              </el-form-item>
            </template>
            <template v-if="selected.type === 'table'">
              <el-form-item label="数据集">
                <el-select v-model="selected.dataset_id" filterable clearable
                           style="width: 100%"
                           @change="selectDataset(selected.dataset_id)">
                  <el-option v-for="d in datasets" :key="d.id" :value="d.id"
                             :label="d.name" />
                </el-select>
              </el-form-item>
              <el-form-item label="指标">
                <el-select v-model="selected.metric_id" filterable clearable
                           style="width: 100%"
                           @change="selectMetric(selected.metric_id)">
                  <el-option v-for="m in metrics" :key="m.id" :value="m.id"
                             :label="m.name" />
                </el-select>
              </el-form-item>
              <el-form-item label="列">
                <el-input v-model="columnsText"
                          placeholder="留空显示全部，逗号分隔" />
              </el-form-item>
              <el-form-item label="行数">
                <el-input-number v-model="selected.limit" :min="1"
                                 :max="10000" />
              </el-form-item>
            </template>
          </el-form>
          <p class="hint">组件引用已发布的数据集 / 指标；保存后发布生效。</p>
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
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../api";
import AppRuntime from "../studio/app/AppRuntime.vue";
import ShareDialog from "../studio/share/ShareDialog.vue";

const route = useRoute();
const id = Number(route.params.id);
const name = ref("");
const published = ref(false);
const content = ref({ start_page: "p1", pages: [] });
const currentId = ref("");
const selectedId = ref("");
const data = ref({});
const paramValues = ref({});
const loadingData = ref(false);
const versions = ref([]);
const versionsOpen = ref(false);
const datasets = ref([]);
const metrics = ref([]);
const modelColumns = ref([]);
const paramTypes = ["string", "number", "date", "bool"];
const types = [
  { type: "text", label: "文本" },
  { type: "metric", label: "指标卡" },
  { type: "table", label: "表格" },
  { type: "form", label: "表单" },
];
const formWidgets = ["input", "textarea", "number", "date", "select",
                     "checkbox"];
const formRoles = ["viewer", "editor", "approver", "admin"];
const formColumns = ref([]);

const currentPage = computed(() =>
  content.value.pages?.find((p) => p.id === currentId.value) || null);
const selected = computed(() =>
  currentPage.value?.components?.find((c) => c.id === selectedId.value)
  || null);
const columnsText = computed({
  get: () => (selected.value?.columns || []).join(", "),
  set: (v) => {
    if (selected.value) {
      selected.value.columns = String(v || "").split(",")
        .map((s) => s.trim()).filter(Boolean);
    }
  },
});

function typeLabel(type) {
  return (types.find((t) => t.type === type) || {}).label || type;
}

function resetParams() {
  const values = {};
  for (const p of currentPage.value?.params || []) {
    if (!p.name) continue;
    values[p.name] = p.default ?? "";
  }
  paramValues.value = values;
}

async function load() {
  const a = await api.get(`/apps/${id}`);
  name.value = a.name;
  published.value = Boolean(a.published_version);
  content.value = a.draft || { start_page: "p1", pages: [] };
  if (!content.value.pages?.length) {
    content.value = {
      start_page: "p1",
      pages: [{ id: "p1", title: "页面 1", params: [], components: [] }],
    };
  }
  if (!content.value.pages.some((p) => p.id === currentId.value)) {
    currentId.value = content.value.start_page
      || content.value.pages[0].id;
  }
  await loadOptions();
  resetParams();
  if (currentPage.value?.components.length) await refresh();
  await loadModel();
}

async function loadOptions() {
  const ds = await api.get("/datasets");
  const ms = await api.get("/metrics");
  datasets.value = ds.filter((d) => d.published);
  metrics.value = ms.filter((m) => m.published);
}

watch(currentId, async () => {
  selectedId.value = "";
  resetParams();
  data.value = {};
  modelColumns.value = [];
  if (currentPage.value?.components.length) await refresh();
});

function setParams(p) {
  paramValues.value = { ...p };
  refresh();
}

async function refresh() {
  if (!currentPage.value) return;
  loadingData.value = true;
  try {
    const r = await api.post(`/apps/${id}/data`, {
      page_id: currentPage.value.id,
      params: paramValues.value,
      limit: 100,
      content: content.value,
    });
    data.value = r.components || {};
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loadingData.value = false;
  }
}

function addPage() {
  ElMessageBox.prompt("页面标题", "新建页面", {
    inputPattern: /\S+/, inputErrorMessage: "标题必填",
  }).then(({ value }) => {
    const pid = `p_${Date.now().toString(36)}`;
    content.value.pages.push({
      id: pid, title: value, params: [], components: [],
    });
    currentId.value = pid;
  }).catch(() => {});
}

async function removePage() {
  if (!currentPage.value || content.value.pages.length <= 1) return;
  try {
    await ElMessageBox.confirm(`删除页面「${currentPage.value.title}」？`,
                               "删除确认");
    const pid = currentPage.value.id;
    content.value.pages = content.value.pages.filter((p) => p.id !== pid);
    if (content.value.start_page === pid) {
      content.value.start_page = content.value.pages[0].id;
    }
    currentId.value = content.value.pages[0].id;
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

function addParam() {
  if (!currentPage.value) return;
  const used = new Set((currentPage.value.params || [])
    .map((p) => p.name));
  let n = currentPage.value.params.length + 1;
  while (used.has(`p${n}`)) n += 1;
  currentPage.value.params = currentPage.value.params || [];
  currentPage.value.params.push({
    name: `p${n}`, type: "string", required: false,
    default: "", example: "",
  });
  resetParams();
}

function removeParam(i) {
  currentPage.value.params.splice(i, 1);
  resetParams();
}

async function addComponent(type) {
  if (!currentPage.value) return;
  const c = {
    id: `c_${Date.now().toString(36)}_${Math.random()
      .toString(36).slice(2, 5)}`,
    type,
    title: typeLabel(type),
  };
  if (type === "text") c.text = "说明文本";
  if (type === "metric") {
    c.metric_id = metrics.value[0]?.id || null;
    c.value_column = "";
  }
  if (type === "table") {
    c.dataset_id = datasets.value[0]?.id || null;
    c.limit = 100;
    c.columns = [];
  }
  if (type === "form") {
    c.dataset_id = datasets.value[0]?.id || null;
    c.mode = "insert";
    c.key = "";
    c.fields = [];
    c.submit_text = "提交";
    c.success_message = "提交成功";
  }
  currentPage.value.components.push(c);
  selectedId.value = c.id;
  if (type === "metric") await loadModel();
  if (type === "table" && c.dataset_id) await chooseDataset(c.dataset_id);
  if (type === "form" && c.dataset_id) await loadFormSchema(c.dataset_id);
  await refresh();
}

function selectComponent(cid) {
  selectedId.value = cid;
  loadModel();
  if (selected.value?.type === "form" && selected.value.dataset_id) {
    loadFormSchema(selected.value.dataset_id);
  }
}

function removeComponent() {
  if (!selected.value) return;
  const cid = selected.value.id;
  currentPage.value.components = currentPage.value.components
    .filter((c) => c.id !== cid);
  delete data.value[cid];
  selectedId.value = "";
  modelColumns.value = [];
}

async function loadModel() {
  modelColumns.value = [];
  const c = selected.value;
  if (!c || !c.metric_id) return;
  try {
    const m = await api.get(`/metrics/${c.metric_id}`);
    const mc = m.published || m.draft || {};
    const dims = mc.dimensions || [];
    const alias = (mc.measure || {}).as || "value";
    const cols = [...dims, alias];
    modelColumns.value = cols;
    if (!c.value_column || !cols.includes(c.value_column)) {
      c.value_column = alias;
    }
    if (c.type === "table") {
      c.columns = (c.columns || []).filter((x) => cols.includes(x));
    }
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function selectDataset(datasetId) {
  await chooseDataset(datasetId);
  await refresh();
}

async function selectMetric(metricId) {
  if (selected.value) selected.value.dataset_id = null;
  await loadModel();
  await refresh();
}

async function chooseDataset(datasetId) {
  const c = selected.value;
  if (!c || !datasetId) return;
  c.metric_id = null;
  try {
    const d = await api.get(`/datasets/${datasetId}`);
    const dc = d.published || d.draft || {};
    const cols = (dc.query?.select || [])
      .map((s) => s.as || s.column);
    c.columns = (c.columns || []).filter((x) => cols.includes(x));
    if (!currentPage.value.params) currentPage.value.params = [];
    for (const p of dc.params || []) {
      if (!p.name) continue;
      if (!currentPage.value.params.some((x) => x.name === p.name)) {
        currentPage.value.params.push({
          name: p.name, type: p.type || "string",
          required: Boolean(p.required),
          default: p.default ?? "", example: p.example ?? "",
        });
      }
    }
    resetParams();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function loadFormSchema(datasetId, prune = false) {
  if (!datasetId) {
    formColumns.value = [];
    return;
  }
  try {
    const r = await api.get(
      `/apps/${id}/form-schema?dataset_id=${encodeURIComponent(datasetId)}`);
    formColumns.value = r.columns || [];
    if (prune && selected.value?.type === "form") {
      selected.value.fields = (selected.value.fields || [])
        .filter((f) => formColumns.value.includes(f.column));
    }
  } catch (e) {
    formColumns.value = [];
    ElMessage.error(errMsg(e));
  }
}

async function selectFormDataset(datasetId) {
  await loadFormSchema(datasetId, true);
  const c = selected.value;
  if (c && c.key && !formColumns.value.includes(c.key)) c.key = "";
  if (c?.mode === "delete") onFormModeChange("delete");
}

function setRoles(v) {
  if (selected.value) {
    selected.value.allow_roles = v?.length ? v : undefined;
  }
}

function onFormModeChange(mode) {
  const c = selected.value;
  if (!c || mode !== "delete") return;
  const key = c.key && formColumns.value.includes(c.key)
    ? c.key : (formColumns.value[0] || "");
  c.key = key;
  c.fields = c.fields || [];
  if (key && !c.fields.some((f) => f.column === key)) {
    c.fields.push({ column: key, label: "", widget: "input",
                    required: true });
  }
}

function addField() {
  if (!selected.value) return;
  selected.value.fields = selected.value.fields || [];
  selected.value.fields.push({
    column: formColumns.value[0] || "",
    label: "",
    widget: "input",
    required: false,
  });
}

function removeField(i) {
  selected.value.fields.splice(i, 1);
}

function setOptions(field, text) {
  field.options = String(text || "").split(",")
    .map((x) => x.trim()).filter(Boolean);
}

async function submitForm(componentId, values) {
  if (!(await save())) throw new Error("请先保存草稿");
  await api.post(`/apps/${id}/submit`, {
    component_id: componentId,
    values,
  });
  await refresh();
}

async function save() {
  try {
    await api.put(`/apps/${id}/draft`, { content: content.value });
    ElMessage.success("已保存草稿");
    return true;
  } catch (e) {
    ElMessage.error(errMsg(e));
    return false;
  }
}

async function rename() {
  try {
    await api.put(`/apps/${id}`, { name: name.value });
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function validate() {
  try {
    const r = await api.post(`/apps/${id}/validate`,
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
    await api.applyChange("publish_app", id);
    await load();
    ElMessage.success("已发布");
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function loadVersions() {
  versions.value = await api.get(`/apps/${id}/versions`);
}

async function rollback(row) {
  try {
    await ElMessageBox.confirm(`回滚到版本 ${row.version}？`, "回滚确认");
    await api.applyChange("rollback_app", id, { version: row.version });
    await load();
    await loadVersions();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

onMounted(load);
</script>

<style scoped>
.app-page { height: calc(100vh - 104px); display: flex; flex-direction: column;
            background: #f8fafc; border: 1px solid #e5e7eb;
            border-radius: 10px; overflow: hidden; }
.head { height: 52px; display: flex; align-items: center; gap: 8px;
        padding: 0 12px; background: #fff; border-bottom: 1px solid #e5e7eb; }
.spacer { flex: 1; }
.body { flex: 1; display: grid; grid-template-columns: 280px 1fr 320px;
        min-height: 0; }
.left { background: #fff; border-right: 1px solid #e5e7eb; overflow: auto;
        padding: 10px; }
.section { margin-bottom: 16px; }
.section-head { display: flex; justify-content: space-between;
                align-items: center; font-size: 12px; font-weight: 600;
                color: #334155; margin-bottom: 6px; }
.pages { display: flex; flex-direction: column; gap: 3px; }
.page-row { display: flex; justify-content: space-between; align-items: center;
            padding: 6px 8px; border-radius: 6px; cursor: pointer;
            font-size: 12px; color: #475569; }
.page-row:hover { background: #f1f5f9; }
.page-row.active { background: #eff6ff; color: #1d4ed8; font-weight: 600; }
.page-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.page-actions { display: flex; gap: 4px; align-items: center; margin-top: 6px;
                flex-wrap: wrap; }
.param { display: flex; gap: 3px; align-items: center; margin-bottom: 4px;
         flex-wrap: wrap; }
.param :deep(.el-input) { width: 74px; }
.palette { display: flex; flex-direction: column; gap: 4px; }
.palette .add { width: 100%; margin: 0; }
.components { margin-top: 8px; display: flex; flex-direction: column; gap: 2px; }
.comp-row { display: flex; justify-content: space-between; padding: 6px 8px;
            border-radius: 6px; cursor: pointer; font-size: 12px;
            color: #475569; }
.comp-row:hover { background: #f1f5f9; }
.comp-row.active { background: #eff6ff; color: #1d4ed8; font-weight: 600; }
.comp-type { color: #6b7280; font-size: 11px; }
.hint { color: #6b7280; font-size: 11px; margin: 8px 0 0; }
.canvas { overflow: auto; padding: 14px; }
.config { background: #fff; border-left: 1px solid #e5e7eb; overflow: auto;
          padding: 12px; }
.config-head { display: flex; justify-content: space-between; align-items: center; }
h4 { margin: 0 0 12px; font-size: 13px; }
</style>
