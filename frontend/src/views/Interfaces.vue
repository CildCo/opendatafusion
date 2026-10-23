<template>
  <div class="page">
    <div class="toolbar">
      <el-input v-model="q" placeholder="搜索接口名 / Key" clearable style="width: 240px"
                :prefix-icon="Search" />
      <el-select v-model="statusFilter" clearable placeholder="全部状态" style="width: 140px">
        <el-option :value="1" label="已发布" />
        <el-option :value="0" label="草稿" />
      </el-select>
      <div class="spacer" />
      <el-button @click="load" :loading="loading">刷新</el-button>
      <el-button type="primary" @click="openCreate">新建接口</el-button>
    </div>

    <el-card class="card" shadow="never">
      <el-table :data="paged" size="small" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="key" label="接口 Key" min-width="220">
          <template #default="{ row }">
            <span class="mono">{{ row.key }}</span>
            <el-button link @click="copy(row.key)">复制</el-button>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
              {{ row.status === 1 ? "已发布" : "草稿" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button link @click="openDetail(row)">详情</el-button>
            <el-button v-if="row.status !== 1" link @click="publish(row)">发布</el-button>
            <el-button v-else link @click="revoke(row)">下线</el-button>
            <el-button link :disabled="row.status !== 1" @click="execute(row)">执行</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !filtered.length" description="还没有接口" />
      <div class="pager">
        <el-pagination v-model:current-page="page" :page-size="pageSize"
                       :total="filtered.length" layout="total, prev, pager, next" small />
      </div>
    </el-card>

    <el-dialog v-model="dialog" title="新建接口" width="720px">
      <el-form label-width="90px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="数据源" required>
          <el-select v-model="form.datasource_id" style="width: 100%">
            <el-option v-for="d in datasources" :key="d.id" :value="d.id"
                       :label="`${d.name} (${d.kind})`" />
          </el-select>
        </el-form-item>
        <el-form-item label="SQL" required>
          <el-input v-model="form.sql_text" type="textarea" :rows="7"
                    class="sql" placeholder="select * from t where day = ${day}" />
        </el-form-item>
        <el-form-item label="参数">
          <div class="param-box">
            <div v-for="(p, i) in form.params" :key="i" class="param-row">
              <el-input v-model="p.name" placeholder="名称" style="width: 130px" />
              <el-select v-model="p.type" style="width: 110px">
                <el-option value="string" label="字符串" />
                <el-option value="number" label="数字" />
              </el-select>
              <el-checkbox v-model="p.required">必填</el-checkbox>
              <el-button link type="danger" @click="form.params.splice(i, 1)">删除</el-button>
            </div>
            <el-button link type="primary" @click="addParam">+ 添加参数</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="create">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="drawer" :title="detail.name || '接口详情'" size="700px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="接口 ID">{{ detail.id }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="detail.status === 1 ? 'success' : 'info'" size="small">
            {{ detail.status === 1 ? "已发布" : "草稿" }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="OpenAPI 路径" :span="2">
          <span class="mono">/openapi/{{ detail.key }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="数据源">{{ detail.datasource_id }}</el-descriptions-item>
      </el-descriptions>
      <h4>SQL</h4>
      <pre class="sql-preview">{{ detail.sql }}</pre>
      <h4>参数</h4>
      <el-table :data="detail.params || []" size="small">
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="type" label="类型" width="100" />
        <el-table-column prop="required" label="必填" width="80">
          <template #default="{ row }">{{ row.required ? "是" : "否" }}</template>
        </el-table-column>
      </el-table>
      <div class="actions">
        <el-button v-if="detail.status !== 1" type="primary" @click="publish(detail)">发布</el-button>
        <el-button v-else @click="revoke(detail)">下线</el-button>
        <el-button :disabled="detail.status !== 1" @click="execute(detail)">执行</el-button>
      </div>
    </el-drawer>

    <el-dialog v-model="execDialog" title="执行接口" width="620px">
      <el-form label-width="100px">
        <el-form-item v-for="p in execParams" :key="p.name" :label="p.name">
          <el-input v-model="execValues[p.name]" :placeholder="p.type" />
        </el-form-item>
      </el-form>
      <el-button type="primary" :loading="execLoading" @click="doExecute">执行</el-button>
      <pre class="result">{{ result }}</pre>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Search } from "@element-plus/icons-vue";
import { api, errMsg } from "../api";

const rows = ref([]);
const datasources = ref([]);
const loading = ref(false);
const saving = ref(false);
const dialog = ref(false);
const drawer = ref(false);
const execDialog = ref(false);
const detail = ref({});
const execParams = ref([]);
const execValues = reactive({});
const execLoading = ref(false);
const result = ref("");
const q = ref("");
const statusFilter = ref(null);
const page = ref(1);
const pageSize = 10;

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
    ElMessage.warning("名称、数据源和 SQL 必填");
    return;
  }
  saving.value = true;
  try {
    await api.post("/interfaces", {
      project_id: 1,
      datasource_id: form.datasource_id,
      name: form.name,
      sql_text: form.sql_text,
      params: form.params.filter((p) => p.name),
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

async function openDetail(row) {
  try {
    detail.value = await api.get(`/interfaces/${row.id}`);
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
    ElMessage.success("已发布");
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}
async function revoke(row) {
  try {
    await ElMessageBox.confirm("下线后外部调用将不可用，确认？", "下线确认", { type: "warning" });
    const a = await api.post(`/interfaces/${row.id}/approve?action=revoke`, {});
    await api.post(`/interfaces/${row.id}/revoke?approval_token=${encodeURIComponent(a.approval_token)}`, {});
    await load();
    if (drawer.value && detail.value.id === row.id) await openDetail(row);
    ElMessage.success("已下线");
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
        throw new Error(`参数 ${p.name} 必填`);
      }
      if (v === "" || v === undefined) continue;
      payload[p.name] = p.type === "number" ? Number(v) : v;
    }
    const r = await api.post(`/interfaces/${detail.value.id}/execute`, payload);
    result.value = JSON.stringify(r, null, 2);
  } catch (e) {
    result.value = errMsg(e);
  } finally {
    execLoading.value = false;
  }
}

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success("已复制");
  } catch (e) {
    ElMessage.warning(text);
  }
}

onMounted(load);
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
