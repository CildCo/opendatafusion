<template>
  <div class="page">
    <div class="toolbar">
      <el-input v-model="q" placeholder="搜索应用名 / Key" clearable
                style="width: 260px" />
      <div class="spacer" />
      <el-button @click="load" :loading="loading">刷新</el-button>
      <el-button type="primary" @click="create">新建应用</el-button>
    </div>
    <el-card shadow="never">
      <el-table :data="filtered" size="small" v-loading="loading">
        <el-table-column prop="name" label="名称" min-width="180" />
        <el-table-column prop="key" label="Key" min-width="240">
          <template #default="{ row }">
            <span class="mono">{{ row.key }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.published ? 'success' : 'info'" size="small">
              {{ row.published ? "已发布" : "草稿" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170">
          <template #default="{ row }">
            <el-button link @click="$router.push(`/apps/${row.id}`)">
              编辑
            </el-button>
            <el-button link :disabled="!row.published"
                       @click="$router.push(`/apps/${row.id}/run`)">
              运行
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !filtered.length"
                description="还没有数据应用" />
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../api";

const router = useRouter();
const rows = ref([]);
const q = ref("");
const loading = ref(false);
const filtered = computed(() => rows.value.filter(
  (r) => !q.value || (r.name + r.key).toLowerCase()
    .includes(q.value.toLowerCase())));

async function load() {
  loading.value = true;
  try {
    rows.value = await api.get("/apps");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

async function create() {
  try {
    const { value } = await ElMessageBox.prompt("应用名称", "新建应用", {
      inputPattern: /\S+/, inputErrorMessage: "名称必填",
    });
    const r = await api.post("/apps", { name: value });
    router.push(`/apps/${r.id}`);
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

onMounted(load);
</script>

<style scoped>
.toolbar { display: flex; gap: 10px; margin-bottom: 12px; align-items: center; }
.spacer { flex: 1; }
.mono { font-family: ui-monospace, monospace; font-size: 11px; }
</style>
