<template>
  <div class="page">
    <div class="toolbar">
      <el-button @click="load" :loading="loading">刷新</el-button>
      <el-button type="primary" @click="create">新建管道</el-button>
    </div>

    <el-card class="card" shadow="never">
      <el-table :data="rows" size="small" v-loading="loading"
                row-class-name="clickable" @row-click="open">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column prop="cron" label="调度" width="160" />
        <el-table-column prop="enabled" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
              {{ row.enabled ? "启用" : "停用" }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !rows.length" description="还没有管道" />
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { api, errMsg } from "../api";

const rows = ref([]);
const loading = ref(false);
const router = useRouter();

async function load() {
  loading.value = true;
  try {
    rows.value = await api.get("/pipelines");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

async function create() {
  try {
    const a = await api.post("/pipelines", {
      name: "新建管道",
      content: { nodes: [], edges: [], settings: { batch: 1000 } },
    });
    await load();
    router.push(`/pipelines/${a.id}`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

function open(row) {
  router.push(`/pipelines/${row.id}`);
}

onMounted(load);
</script>

<style scoped>
.card { border-radius: 12px; border: 1px solid #e5e7eb; }
:deep(.clickable) { cursor: pointer; }
</style>
