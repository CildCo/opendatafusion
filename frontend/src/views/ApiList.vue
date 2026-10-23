<template>
  <div class="page">
    <div class="toolbar">
      <el-input v-model="q" placeholder="搜索接口名 / Key" clearable
                style="width: 260px" />
      <div class="spacer" />
      <el-button @click="load" :loading="loading">刷新</el-button>
      <el-button type="primary" @click="create">新建接口</el-button>
    </div>
    <el-card shadow="never">
      <el-table :data="filtered" size="small" v-loading="loading">
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column prop="key" label="接口 Key" min-width="240">
          <template #default="{ row }">
            <span class="mono">{{ row.key }}</span>
            <el-button link @click="copy(row.key)">复制</el-button>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
              {{ row.enabled ? "已发布" : "草稿" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button link @click="$router.push(`/apis/${row.id}`)">
              编辑
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !filtered.length" description="还没有接口" />
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
    rows.value = await api.get("/apis");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

async function create() {
  try {
    const { value } = await ElMessageBox.prompt("接口名称", "新建接口", {
      inputPattern: /\S+/, inputErrorMessage: "名称必填",
    });
    const r = await api.post("/apis", { name: value });
    router.push(`/apis/${r.id}`);
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success("已复制");
  } catch (e) {
    ElMessage.error("复制失败");
  }
}

onMounted(load);
</script>

<style scoped>
.toolbar { display: flex; gap: 10px; margin-bottom: 12px; align-items: center; }
.spacer { flex: 1; }
.mono { font-family: ui-monospace, monospace; font-size: 12px; }
</style>
