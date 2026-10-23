<template>
  <div class="page">
    <div class="toolbar">
      <el-input v-model="q" placeholder="搜索流程名" clearable style="width: 220px"
                :prefix-icon="Search" />
      <el-select v-model="statusFilter" clearable placeholder="全部状态" style="width: 140px">
        <el-option :value="1" label="启用" />
        <el-option :value="0" label="停用" />
      </el-select>
      <div class="spacer" />
      <el-button @click="load" :loading="loading">刷新</el-button>
      <el-button type="primary" @click="openCreate">新建流程</el-button>
    </div>

    <el-card class="card" shadow="never">
      <el-table :data="paged" size="small" v-loading="loading"
                @row-click="openDetail" row-class-name="clickable">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column prop="cron" label="调度" width="150" />
        <el-table-column prop="version" label="版本" width="80" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
              {{ row.status === 1 ? "启用" : "停用" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button link @click.stop="toggle(row)">
              {{ row.status === 1 ? "停用" : "启用" }}
            </el-button>
            <el-button link :disabled="row.status !== 1" @click.stop="run(row)">运行</el-button>
            <el-button link @click.stop="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !filtered.length" description="还没有流程" />
      <div class="pager">
        <el-pagination v-model:current-page="page" :page-size="pageSize"
                       :total="filtered.length" layout="total, prev, pager, next" small />
      </div>
    </el-card>

    <el-dialog v-model="dialog" title="新建流程" width="680px">
      <el-form label-width="110px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="例如：访客信息同步" />
        </el-form-item>
        <el-form-item label="调度">
          <el-select v-model="form.cronPreset" style="width: 200px" @change="onCronPreset">
            <el-option value="0 */5 * * * ?" label="每 5 分钟" />
            <el-option value="0 0 * * * ?" label="每小时" />
            <el-option value="0 0 2 * * ?" label="每天 02:00" />
            <el-option value="custom" label="自定义" />
          </el-select>
          <el-input v-if="form.cronPreset === 'custom'" v-model="form.cron"
                    style="width: 220px; margin-left: 10px"
                    placeholder="0 */5 * * * ?" />
        </el-form-item>
        <el-divider content-position="left">来源</el-divider>
        <el-form-item label="数据源">
          <el-select v-model="form.source_ds_id" style="width: 100%"
                     @change="loadSourceTables">
            <el-option v-for="d in datasources" :key="d.id" :value="d.id"
                       :label="`${d.name} (${d.kind})`" />
          </el-select>
        </el-form-item>
        <el-form-item label="表">
          <el-select v-model="form.source_table" style="width: 100%"
                     filterable @change="onSourceTable">
            <el-option v-for="t in sourceTables" :key="t.table" :value="tableValue(t)"
                       :label="`${t.schema}.${t.table}`" />
          </el-select>
        </el-form-item>
        <el-divider content-position="left">目标</el-divider>
        <el-form-item label="数据源">
          <el-select v-model="form.sink_ds_id" style="width: 100%"
                     @change="loadSinkTables">
            <el-option v-for="d in datasources" :key="d.id" :value="d.id"
                       :label="`${d.name} (${d.kind})`" />
          </el-select>
        </el-form-item>
        <el-form-item label="表">
          <el-select v-model="form.sink_table" style="width: 100%" filterable>
            <el-option v-for="t in sinkTables" :key="t.table" :value="tableValue(t)"
                       :label="`${t.schema}.${t.table}`" />
          </el-select>
        </el-form-item>
        <el-form-item label="主键">
          <el-select v-model="form.pk" style="width: 100%" filterable allow-create>
            <el-option v-for="c in sourceColumns" :key="c.name" :value="c.name"
                       :label="`${c.name} (${c.type})`" />
          </el-select>
        </el-form-item>
        <el-form-item label="增量列">
          <el-select v-model="form.cursor_column" style="width: 100%" clearable
                     filterable allow-create>
            <el-option v-for="c in sourceColumns" :key="c.name" :value="c.name"
                       :label="`${c.name} (${c.type})`" />
          </el-select>
          <div class="hint">留空表示全量；建议选时间或自增列</div>
        </el-form-item>
        <el-form-item label="批量">
          <el-input-number v-model="form.batch" :min="1" :step="100" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="create">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="drawer" :title="current.name || '流程详情'" size="720px">
      <el-tabs v-model="tab">
        <el-tab-pane label="概览" name="overview">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="流程 ID">{{ current.id }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="current.status === 1 ? 'success' : 'info'" size="small">
                {{ current.status === 1 ? "启用" : "停用" }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="调度">{{ current.cron }}</el-descriptions-item>
            <el-descriptions-item label="当前版本">{{ current.version }}</el-descriptions-item>
            <el-descriptions-item label="来源" :span="2">
              {{ dag.source_table }} ← 数据源 {{ dag.source_ds_id }}
            </el-descriptions-item>
            <el-descriptions-item label="目标" :span="2">
              {{ dag.sink_table }} ← 数据源 {{ dag.sink_ds_id }}
            </el-descriptions-item>
            <el-descriptions-item label="主键">{{ dag.pk }}</el-descriptions-item>
            <el-descriptions-item label="增量列">{{ dag.cursor_column || "全量" }}</el-descriptions-item>
          </el-descriptions>
          <div class="actions">
            <el-button type="primary" :disabled="current.status !== 1" @click="run(current)">
              运行一次
            </el-button>
            <el-button @click="toggle(current)">
              {{ current.status === 1 ? "停用" : "启用" }}
            </el-button>
            <el-button @click="refreshDetail">刷新</el-button>
          </div>
        </el-tab-pane>

        <el-tab-pane label="版本" name="versions">
          <el-table :data="versions" size="small">
            <el-table-column prop="version" label="版本" width="80" />
            <el-table-column prop="created_by" label="创建人" width="140" />
            <el-table-column prop="created_at" label="时间" />
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button link :disabled="row.version === current.version"
                           @click="rollback(row)">回滚到此</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="运行记录" name="runs">
          <el-table :data="runs" size="small">
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="runType(row.status)" size="small">
                  {{ runLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="in" label="输入" width="90" />
            <el-table-column prop="out" label="输出" width="90" />
            <el-table-column prop="err" label="错误" width="80" />
            <el-table-column prop="cursor" label="游标" />
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="作业队列" name="jobs">
          <el-table :data="jobs" size="small">
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="status" label="状态" width="100" />
            <el-table-column prop="attempts" label="尝试" width="70" />
            <el-table-column prop="run_at" label="计划时间" width="200" />
            <el-table-column prop="last_error" label="最后错误" />
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
  return { 0: "排队", 1: "运行中", 2: "成功", 3: "失败", 4: "跳过" }[s] || s;
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

function tableValue(t) {
  return t.schema && t.schema !== "main" && t.schema !== "public"
    ? `${t.schema}.${t.table}` : t.table;
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
  const t = sourceTables.value.find((x) => tableValue(x) === name);
  sourceColumns.value = t ? t.columns || [] : [];
  if (sourceColumns.value.length && !form.pk) form.pk = sourceColumns.value[0].name;
}

async function create() {
  if (!form.name || !form.source_table || !form.sink_table) {
    ElMessage.warning("名称、来源表和目标表必填");
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
    ElMessage.success("已创建");
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
    ElMessage.success("已加入执行队列");
    if (drawer.value && current.value.id === row.id) await pollDetail();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function toggle(row) {
  const action = row.status === 1 ? "pause_flow" : "resume_flow";
  try {
    await ElMessageBox.confirm(
      action === "pause_flow" ? "停用后调度将不再触发，确认？" : "启用后会按 cron 调度，确认？",
      "变更确认", { type: "warning" }
    );
    await api.applyChange(action, row.id);
    await load();
    if (drawer.value) await pollDetail();
    ElMessage.success("已生效");
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

async function rollback(row) {
  try {
    await ElMessageBox.confirm(`回滚到版本 ${row.version}？`, "回滚确认", { type: "warning" });
    await api.applyChange("rollback_flow", current.value.id, { version: row.version });
    await pollDetail();
    ElMessage.success("已回滚");
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
