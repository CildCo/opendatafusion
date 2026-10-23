<template>
  <div class="page">
    <el-tabs v-model="tab" @tab-change="go">
      <el-tab-pane label="数据集" name="datasets" />
      <el-tab-pane label="指标" name="metrics" />
    </el-tabs>
    <div class="toolbar">
      <el-input v-model="q" placeholder="搜索名称 / Key" clearable
                style="width: 260px" />
      <div class="spacer" />
      <el-button @click="load" :loading="loading">刷新</el-button>
      <el-button type="primary" @click="create">
        新建{{ tab === "datasets" ? "数据集" : "指标" }}
      </el-button>
    </div>
    <el-card shadow="never">
      <el-table :data="filtered" size="small" v-loading="loading">
        <el-table-column prop="name" label="名称" min-width="160" />
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
        <el-table-column label="操作" width="110">
          <template #default="{ row }">
            <el-button link @click="$router.push(`/${tab}/${row.id}`)">
              编辑
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !filtered.length" description="还没有模型" />
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../api";

const route = useRoute();
const router = useRouter();
const tab = ref(route.path.startsWith("/metrics") ? "metrics" : "datasets");
const rows = ref([]);
const q = ref("");
const loading = ref(false);
const filtered = computed(() => rows.value.filter(
  (r) => !q.value || (r.name + r.key).toLowerCase()
    .includes(q.value.toLowerCase())));

async function load() {
  loading.value = true;
  try {
    rows.value = await api.get(`/${tab.value}`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

function go() {
  router.push(`/${tab.value}`);
}

async function create() {
  try {
    const { value } = await ElMessageBox.prompt("名称", "新建", {
      inputPattern: /\S+/, inputErrorMessage: "名称必填",
    });
    const r = await api.post(`/${tab.value}`, { name: value });
    router.push(`/${tab.value}/${r.id}`);
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

watch(() => route.path, () => {
  tab.value = route.path.startsWith("/metrics") ? "metrics" : "datasets";
  load();
});
onMounted(load);
</script>

<style scoped>
.toolbar { display: flex; gap: 10px; margin: 12px 0; align-items: center; }
.spacer { flex: 1; }
.mono { font-family: ui-monospace, monospace; font-size: 11px; }
</style>
