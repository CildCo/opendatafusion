<template>
  <div class="page">
    <div class="toolbar">
      <el-select v-model="status" clearable placeholder="全部状态" style="width: 140px"
                 @change="load">
        <el-option value="open" label="未处理" />
        <el-option value="acked" label="已确认" />
        <el-option value="closed" label="已关闭" />
      </el-select>
      <el-select v-model="severity" clearable placeholder="全部级别" style="width: 140px">
        <el-option value="critical" label="严重" />
        <el-option value="warning" label="警告" />
      </el-select>
      <div class="spacer" />
      <el-button @click="load" :loading="loading">刷新</el-button>
    </div>

    <el-card class="card" shadow="never">
      <el-table :data="filtered" size="small" v-loading="loading"
                @row-click="showDetail" row-class-name="clickable">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="severity" label="级别" width="90">
          <template #default="{ row }">
            <el-tag :type="row.severity === 'critical' ? 'danger' : 'warning'"
                    size="small">{{ row.severity }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="220" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'open' ? 'danger' : row.status === 'acked' ? 'warning' : 'info'"
                    size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="200" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link :disabled="row.status !== 'open'" @click.stop="ack(row)">确认</el-button>
            <el-button link :disabled="row.status === 'closed'" @click.stop="close(row)">关闭</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !filtered.length" description="没有告警" />
    </el-card>

    <el-drawer v-model="drawer" :title="current.title || '告警详情'" size="520px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="级别">{{ current.severity }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ statusLabel(current.status) }}</el-descriptions-item>
        <el-descriptions-item label="时间">{{ current.created_at }}</el-descriptions-item>
      </el-descriptions>
      <h4>详情</h4>
      <pre class="detail">{{ JSON.stringify(current.detail, null, 2) }}</pre>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../api";

const rows = ref([]);
const loading = ref(false);
const status = ref("");
const severity = ref("");
const drawer = ref(false);
const current = ref({});

const filtered = computed(() =>
  rows.value.filter((r) => !severity.value || r.severity === severity.value)
);

function statusLabel(s) {
  return { open: "未处理", acked: "已确认", closed: "已关闭" }[s] || s;
}

async function load() {
  loading.value = true;
  try {
    const q = status.value ? `?status=${status.value}` : "";
    rows.value = await api.get("/alerts" + q);
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}
function showDetail(row) {
  current.value = row;
  drawer.value = true;
}
async function ack(row) {
  try {
    await api.post(`/alerts/${row.id}/ack`);
    await load();
    ElMessage.success("已确认");
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}
async function close(row) {
  try {
    await ElMessageBox.confirm("关闭后不再出现在未处理列表，确认？", "关闭告警",
                               { type: "warning" });
    await api.post(`/alerts/${row.id}/close`);
    await load();
    ElMessage.success("已关闭");
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}
onMounted(load);
</script>

<style scoped>
.card {
  border-radius: 0;
  border: 1px solid #e5e7eb;
}
.detail {
  background: #0f172a;
  color: #e2e8f0;
  padding: 14px;
  border-radius: 0;
  font-size: 12px;
  overflow: auto;
}
:deep(.clickable) {
  cursor: pointer;
}
</style>
