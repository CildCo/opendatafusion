<template>
  <div class="page">
    <div class="toolbar">
      <el-tag size="small" type="info">跨项目访问</el-tag>
      <div class="spacer" />
      <el-button size="small" @click="loadAll" :loading="loading">刷新</el-button>
    </div>

    <el-card shadow="never">
      <el-tabs v-model="tab">
        <el-tab-pane label="接口目录" name="catalog">
          <el-table :data="catalog" size="small" empty-text="没有已发布接口">
            <el-table-column prop="name" label="接口" min-width="180" />
            <el-table-column prop="key" label="Key" min-width="220">
              <template #default="{ row }">
                <span class="mono">{{ row.key }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="owner_project" label="所属项目"
                             width="150" />
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button v-if="!row.owned" link type="primary"
                           @click="openRequest(row)">申请访问</el-button>
                <span v-else class="hint">本项目</span>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="我的申请" name="outgoing">
          <el-table :data="outgoing" size="small" empty-text="没有申请">
            <el-table-column prop="asset_name" label="接口" min-width="160" />
            <el-table-column prop="owner_project" label="所属项目"
                             width="140" />
            <el-table-column prop="note" label="说明" min-width="180" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="statusTone(row.status)">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="申请时间" width="170">
              <template #default="{ row }">{{ fmt(row.created_at) }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="待审批" name="incoming">
          <el-table :data="incoming" size="small"
                    empty-text="没有待审批申请">
            <el-table-column prop="asset_name" label="接口" min-width="160" />
            <el-table-column prop="grantee_project" label="申请项目"
                             width="140" />
            <el-table-column prop="requested_by" label="申请人" width="110" />
            <el-table-column prop="note" label="说明" min-width="180" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="statusTone(row.status)">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="130">
              <template #default="{ row }">
                <template v-if="row.status === 'pending'">
                  <el-button link type="primary"
                             @click="decide(row, true)">通过</el-button>
                  <el-button link type="danger"
                             @click="decide(row, false)">拒绝</el-button>
                </template>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="授权管理" name="grants">
          <el-table :data="grants" size="small" empty-text="还没有授权">
            <el-table-column prop="asset_name" label="接口" min-width="180" />
            <el-table-column prop="grantee_project" label="授权项目"
                             width="150" />
            <el-table-column prop="granted_by" label="授权人" width="120" />
            <el-table-column label="授权时间" width="170">
              <template #default="{ row }">{{ fmt(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="90">
              <template #default="{ row }">
                <el-button link type="danger"
                           @click="revoke(row)">撤销</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog v-model="requestOpen" title="申请接口访问" width="480px">
      <p class="hint">
        接口：{{ target?.name }}（{{ target?.owner_project }}）
      </p>
      <el-input v-model="note" type="textarea" :rows="3"
                placeholder="用途说明（可选）" />
      <template #footer>
        <el-button @click="requestOpen = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitRequest">
          提交申请
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../api";

const tab = ref("catalog");
const catalog = ref([]);
const outgoing = ref([]);
const incoming = ref([]);
const grants = ref([]);
const loading = ref(false);
const saving = ref(false);
const requestOpen = ref(false);
const target = ref(null);
const note = ref("");

function fmt(v) {
  if (!v) return "-";
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? v : d.toLocaleString("zh-CN");
}
function statusTone(s) {
  return { approved: "success", pending: "warning",
           rejected: "danger" }[s] || "info";
}

async function loadAll() {
  loading.value = true;
  try {
    const [c, o, i, g] = await Promise.all([
      api.get("/api-catalog"),
      api.get("/api-requests?direction=outgoing"),
      api.get("/api-requests?direction=incoming"),
      api.get("/api-grants"),
    ]);
    catalog.value = c;
    outgoing.value = o;
    incoming.value = i;
    grants.value = g;
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

function openRequest(row) {
  target.value = row;
  note.value = "";
  requestOpen.value = true;
}

async function submitRequest() {
  saving.value = true;
  try {
    await api.post("/api-requests", {
      asset_id: target.value.id, note: note.value,
    });
    ElMessage.success("申请已提交");
    requestOpen.value = false;
    await loadAll();
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

async function decide(row, approve) {
  try {
    await ElMessageBox.confirm(
      `${approve ? "通过" : "拒绝"}「${row.asset_name}」来自`
      + `「${row.grantee_project}」的申请？`, "审批确认");
    await api.post(`/api-requests/${row.id}/${approve ? "approve"
      : "reject"}`);
    ElMessage.success(approve ? "已通过" : "已拒绝");
    await loadAll();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

async function revoke(row) {
  try {
    await ElMessageBox.confirm(
      `撤销「${row.grantee_project}」对「${row.asset_name}」的访问？`,
      "撤销授权");
    await api.del(`/api-grants/${row.id}`);
    ElMessage.success("已撤销");
    await loadAll();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

onMounted(loadAll);
</script>

<style scoped>
.toolbar { display: flex; gap: 10px; align-items: center;
           margin-bottom: 12px; }
.title { font-size: 16px; font-weight: 700; color: #0f172a; }
.spacer { flex: 1; }
.mono { font-family: ui-monospace, monospace; font-size: 11px; }
.hint { color: #6b7280; font-size: 12px; }
</style>
