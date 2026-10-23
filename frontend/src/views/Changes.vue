<template>
  <div class="page">
    <div class="toolbar">
      <el-select v-model="status" clearable placeholder="全部状态" style="width: 150px"
                 @change="load">
        <el-option value="proposed" label="待批准" />
        <el-option value="applied" label="已执行" />
      </el-select>
      <div class="spacer" />
      <el-button @click="load" :loading="loading">刷新</el-button>
      <el-button type="primary" @click="openCreate">发起变更</el-button>
    </div>

    <el-card class="card" shadow="never">
      <el-table :data="rows" size="small" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="action" label="动作" width="170">
          <template #default="{ row }">{{ actionLabel(row.action) }}</template>
        </el-table-column>
        <el-table-column prop="target" label="目标" width="100" />
        <el-table-column prop="actor" label="发起人" width="130" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'applied' ? 'success' : 'warning'" size="small">
              {{ row.status === "applied" ? "已执行" : "待批准" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="200" />
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button link :disabled="row.status !== 'proposed'" @click="approve(row)">
              批准
            </el-button>
            <el-button link :disabled="row.status !== 'proposed'" @click="apply(row)">
              执行
            </el-button>
            <el-button link :disabled="row.status !== 'proposed'" @click="approveAndApply(row)">
              批准并执行
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !rows.length" description="还没有变更" />
    </el-card>

    <el-dialog v-model="dialog" title="发起变更" width="560px">
      <el-form label-width="90px">
        <el-form-item label="动作" required>
          <el-select v-model="form.action" style="width: 100%" @change="onAction">
            <el-option value="run_flow" label="运行流程" />
            <el-option value="pause_flow" label="停用流程" />
            <el-option value="resume_flow" label="启用流程" />
            <el-option value="rollback_flow" label="回滚流程" />
            <el-option value="publish_interface" label="发布接口" />
            <el-option value="revoke_interface" label="下线接口" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标" required>
          <el-select v-if="isFlowAction" v-model="form.target" style="width: 100%" filterable>
            <el-option v-for="f in flows" :key="f.id" :value="f.id"
                       :label="`${f.name} (#${f.id})`" />
          </el-select>
          <el-select v-else v-model="form.target" style="width: 100%" filterable>
            <el-option v-for="i in interfaces" :key="i.id" :value="i.id"
                       :label="`${i.name} (#${i.id})`" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.action === 'rollback_flow'" label="版本">
          <el-select v-model="form.version" style="width: 100%">
            <el-option v-for="v in versions" :key="v.version" :value="v.version"
                       :label="`版本 ${v.version}`" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.note" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="create">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { api, errMsg } from "../api";

const rows = ref([]);
const flows = ref([]);
const interfaces = ref([]);
const versions = ref([]);
const loading = ref(false);
const saving = ref(false);
const dialog = ref(false);
const status = ref("");
const tokens = reactive({});
const form = reactive({
  action: "pause_flow", target: null, version: null, note: "",
});

const isFlowAction = computed(() =>
  ["run_flow", "pause_flow", "resume_flow", "rollback_flow"].includes(form.action)
);

function actionLabel(a) {
  return {
    run_flow: "运行流程", pause_flow: "停用流程", resume_flow: "启用流程",
    rollback_flow: "回滚流程", publish_interface: "发布接口",
    revoke_interface: "下线接口",
  }[a] || a;
}

async function load() {
  loading.value = true;
  try {
    const q = status.value ? `?status=${status.value}` : "";
    rows.value = await api.get("/changes" + q);
    flows.value = await api.get("/flows");
    interfaces.value = await api.get("/interfaces");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  Object.assign(form, { action: "pause_flow", target: null, version: null, note: "" });
  versions.value = [];
  dialog.value = true;
  onAction();
}

async function onAction() {
  form.target = isFlowAction.value ? flows.value[0]?.id ?? null
                                   : interfaces.value[0]?.id ?? null;
  versions.value = [];
  if (form.action === "rollback_flow" && form.target) {
    versions.value = await api.flowVersions(form.target);
    form.version = versions.value[0]?.version ?? null;
  }
}

async function create() {
  if (!form.target) {
    ElMessage.warning("请选择目标");
    return;
  }
  saving.value = true;
  try {
    await api.post("/changes", {
      project_id: 1,
      action: form.action,
      target: form.target,
      payload: form.action === "rollback_flow"
        ? { version: form.version } : { note: form.note },
    });
    dialog.value = false;
    await load();
    ElMessage.success("已提交");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

async function approve(row) {
  try {
    const a = await api.post(`/changes/${row.id}/approve`, {});
    tokens[row.id] = a.approval_token;
    ElMessage.success("已批准，可执行");
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function apply(row) {
  const token = tokens[row.id];
  if (!token) {
    ElMessage.warning("请先批准该变更");
    return;
  }
  try {
    await api.post(`/changes/${row.id}/apply?approval_token=${encodeURIComponent(token)}`, {});
    delete tokens[row.id];
    await load();
    ElMessage.success("已执行");
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function approveAndApply(row) {
  try {
    const a = await api.post(`/changes/${row.id}/approve`, {});
    await api.post(`/changes/${row.id}/apply?approval_token=${encodeURIComponent(a.approval_token)}`, {});
    await load();
    ElMessage.success("已批准并执行");
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
</style>
