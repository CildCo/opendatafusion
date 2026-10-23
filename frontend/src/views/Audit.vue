<template>
  <div class="page">
    <div class="toolbar">
      <el-input v-model="actor" placeholder="按操作人过滤" clearable style="width: 200px" />
      <el-input v-model="action" placeholder="按动作过滤" clearable style="width: 200px" />
      <div class="spacer" />
      <el-button @click="load" :loading="loading">刷新</el-button>
    </div>

    <el-card class="card" shadow="never">
      <el-table :data="paged" size="small" v-loading="loading"
                @row-click="showDetail" row-class-name="clickable">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="actor" label="操作人" width="150" />
        <el-table-column prop="action" label="动作" width="190" />
        <el-table-column prop="target" label="目标" width="160" />
        <el-table-column prop="at" label="时间" width="200" />
        <el-table-column label="详情">
          <template #default="{ row }">
            <span class="mono">{{ JSON.stringify(row.detail) }}</span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !filtered.length" description="暂无审计记录" />
      <div class="pager">
        <el-pagination v-model:current-page="page" :page-size="pageSize"
                       :total="filtered.length" layout="total, prev, pager, next" small />
      </div>
    </el-card>

    <el-drawer v-model="drawer" title="审计详情" size="520px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="ID">{{ current.id }}</el-descriptions-item>
        <el-descriptions-item label="操作人">{{ current.actor }}</el-descriptions-item>
        <el-descriptions-item label="动作">{{ current.action }}</el-descriptions-item>
        <el-descriptions-item label="目标">{{ current.target }}</el-descriptions-item>
        <el-descriptions-item label="时间">{{ current.at }}</el-descriptions-item>
      </el-descriptions>
      <h4>详情</h4>
      <pre class="detail">{{ JSON.stringify(current.detail, null, 2) }}</pre>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { api, errMsg } from "../api";

const rows = ref([]);
const loading = ref(false);
const actor = ref("");
const action = ref("");
const page = ref(1);
const pageSize = 20;
const drawer = ref(false);
const current = ref({});

const filtered = computed(() =>
  rows.value.filter((r) => {
    const hitA = !actor.value || (r.actor || "").includes(actor.value);
    const hitB = !action.value || (r.action || "").includes(action.value);
    return hitA && hitB;
  })
);
const paged = computed(() =>
  filtered.value.slice((page.value - 1) * pageSize, page.value * pageSize)
);

async function load() {
  loading.value = true;
  try {
    rows.value = await api.get("/audit?limit=500");
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
onMounted(load);
</script>

<style scoped>
.card {
  border-radius: 0;
  border: 1px solid #e5e7eb;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}
.mono {
  font-family: Consolas, monospace;
  font-size: 12px;
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
