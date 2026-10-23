<template>
  <div class="page">
    <div class="toolbar">
      <el-input v-model="q" placeholder="搜索规则名" clearable style="width: 220px"
                :prefix-icon="Search" />
      <div class="spacer" />
      <el-button @click="load" :loading="loading">刷新</el-button>
      <el-button type="primary" @click="openCreate">新建规则</el-button>
    </div>

    <el-card class="card" shadow="never">
      <el-table :data="filtered" size="small" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column prop="kind" label="类型" width="120">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ kindLabel(row.kind) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="column" label="字段" width="140" />
        <el-table-column label="数据集" min-width="160">
          <template #default="{ row }">{{ datasetName(row.dataset_id) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link @click="run(row)">执行</el-button>
            <el-button link @click="showResults(row)">结果</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !filtered.length" description="还没有质量规则" />
    </el-card>

    <el-dialog v-model="dialog" title="新建质量规则" width="560px">
      <el-form label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="数据集" required>
          <el-select v-model="form.dataset_id" style="width: 100%" filterable
                     @change="onDataset">
            <el-option v-for="d in datasets" :key="d.id" :value="d.id"
                       :label="`${d.schema}.${d.table}`" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型" required>
          <el-select v-model="form.kind" style="width: 100%">
            <el-option value="not_null" label="非空" />
            <el-option value="unique" label="唯一" />
            <el-option value="row_count" label="行数范围" />
            <el-option value="range" label="数值范围" />
            <el-option value="freshness" label="数据新鲜度" />
            <el-option value="regex" label="正则匹配" />
            <el-option value="accepted_values" label="枚举值" />
            <el-option value="schema" label="字段结构" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.kind !== 'row_count' && form.kind !== 'schema'"
                      label="字段">
          <el-select v-model="form.column_name" style="width: 100%" filterable>
            <el-option v-for="c in columns" :key="c.name" :value="c.name"
                       :label="`${c.name} (${c.type})`" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.kind === 'freshness'" label="最大年龄(小时)">
          <el-input-number v-model="form.max_age_hours" :min="1" />
        </el-form-item>
        <el-form-item v-if="form.kind === 'regex'" label="正则">
          <el-input v-model="form.pattern" placeholder="^[^@]+@[^@]+$" />
        </el-form-item>
        <el-form-item v-if="form.kind === 'regex'" label="允许空值">
          <el-switch v-model="form.allow_null" />
        </el-form-item>
        <el-form-item v-if="form.kind === 'accepted_values'" label="允许值">
          <el-input v-model="form.values_text" placeholder="ok,failed,pending" />
        </el-form-item>
        <el-form-item v-if="form.kind === 'accepted_values'" label="允许空值">
          <el-switch v-model="form.allow_null" />
        </el-form-item>
        <el-form-item v-if="form.kind === 'schema'" label="期望字段">
          <el-input v-model="form.expected_text" placeholder="id,email,created_at" />
        </el-form-item>
        <el-form-item v-if="form.kind === 'schema'" label="允许额外字段">
          <el-switch v-model="form.allow_extra" />
        </el-form-item>
        <template v-if="form.kind === 'range' || form.kind === 'row_count'">
          <el-form-item label="最小值">
            <el-input-number v-model="form.min" />
          </el-form-item>
          <el-form-item label="最大值">
            <el-input-number v-model="form.max" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="create">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="resultDrawer" :title="'结果 · ' + (current.name || '')" size="640px">
      <el-table :data="results" size="small">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="status" label="结果" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'pass' ? 'success' : 'danger'" size="small">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="at" label="时间" width="200" />
        <el-table-column label="详情">
          <template #default="{ row }">
            <span class="mono">{{ JSON.stringify(row.detail) }}</span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!results.length" description="还没有执行结果" />
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { Search } from "@element-plus/icons-vue";
import { api, errMsg } from "../api";

const rows = ref([]);
const datasets = ref([]);
const columns = ref([]);
const results = ref([]);
const loading = ref(false);
const saving = ref(false);
const dialog = ref(false);
const resultDrawer = ref(false);
const current = ref({});
const q = ref("");
const form = reactive({
  name: "", dataset_id: null, kind: "not_null", column_name: "",
  min: null, max: null, max_age_hours: 24, pattern: "", values_text: "",
  expected_text: "", allow_null: true, allow_extra: false,
});

const filtered = computed(() =>
  rows.value.filter((r) => !q.value || r.name.toLowerCase().includes(q.value.toLowerCase()))
);

function kindLabel(k) {
  return {
    not_null: "非空", unique: "唯一", row_count: "行数", range: "范围",
    freshness: "新鲜度", regex: "正则", accepted_values: "枚举",
    schema: "结构",
  }[k] || k;
}
function datasetName(id) {
  const d = datasets.value.find((x) => x.id === id);
  return d ? `${d.schema}.${d.table}` : `#${id}`;
}

async function load() {
  loading.value = true;
  try {
    rows.value = await api.get("/quality/rules");
    datasets.value = await api.get("/catalog/datasets");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  Object.assign(form, {
    name: "", dataset_id: datasets.value[0]?.id ?? null, kind: "not_null",
    column_name: "", min: null, max: null, max_age_hours: 24,
    pattern: "", values_text: "", expected_text: "", allow_null: true,
    allow_extra: false,
  });
  columns.value = [];
  dialog.value = true;
  if (form.dataset_id) onDataset(form.dataset_id);
}

async function onDataset(id) {
  form.column_name = "";
  columns.value = [];
  try {
    const d = await api.datasetDetail(id);
    columns.value = d.columns || [];
    if (columns.value.length) form.column_name = columns.value[0].name;
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function create() {
  if (!form.name || !form.dataset_id) {
    ElMessage.warning("名称和数据集必填");
    return;
  }
  saving.value = true;
  try {
    const config = {};
    if (form.min !== null) config.min = form.min;
    if (form.max !== null) config.max = form.max;
    if (form.kind === "freshness") {
      config.max_age_hours = form.max_age_hours;
    }
    if (form.kind === "regex") {
      config.pattern = form.pattern;
      config.allow_null = form.allow_null;
    }
    if (form.kind === "accepted_values") {
      config.values = form.values_text.split(",")
        .map((x) => x.trim()).filter(Boolean);
      config.allow_null = form.allow_null;
    }
    if (form.kind === "schema") {
      config.expected = form.expected_text.split(",")
        .map((x) => x.trim()).filter(Boolean);
      config.allow_extra = form.allow_extra;
    }
    await api.post("/quality/rules", {
      project_id: 1,
      dataset_id: form.dataset_id,
      name: form.name,
      kind: form.kind,
      column_name: ["row_count", "schema"].includes(form.kind)
        ? null : form.column_name,
      config,
    });
    dialog.value = false;
    await load();
    ElMessage.success("已创建");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

async function run(row) {
  try {
    const r = await api.post(`/quality/rules/${row.id}/run`);
    ElMessage[r.status === "pass" ? "success" : "warning"](
      r.status === "pass" ? "校验通过" : `校验失败：${JSON.stringify(r.detail)}`
    );
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function showResults(row) {
  current.value = row;
  try {
    results.value = await api.get(`/quality/rules/${row.id}/results`);
    resultDrawer.value = true;
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
.mono {
  font-family: Consolas, monospace;
  font-size: 12px;
}
</style>
