<template>
  <div class="page">
    <div class="toolbar">
      <el-input v-model="q" placeholder="搜索工具" clearable
                style="width: 240px" />
      <div class="spacer" />
      <el-button @click="load" :loading="loading">刷新</el-button>
    </div>
    <el-card shadow="never">
      <el-table :data="filtered" size="small" v-loading="loading">
        <el-table-column prop="name" label="工具" width="220" />
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag :type="row.write ? 'warning' : 'success'" size="small">
              {{ row.write ? "变更" : "只读" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="说明" min-width="260" />
        <el-table-column label="参数" min-width="320">
          <template #default="{ row }">
            <span class="mono">
              {{ row.parameters.map(p => p.name + ":" + p.type
                 + (p.required ? "" : "?")).join(", ") }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { api, errMsg } from "../api";

const rows = ref([]);
const q = ref("");
const loading = ref(false);
const filtered = computed(() => rows.value.filter(
  (r) => !q.value || (r.name + r.description).toLowerCase()
    .includes(q.value.toLowerCase())));

async function load() {
  loading.value = true;
  try {
    rows.value = await api.get("/mcp/tools");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}
onMounted(load);
</script>

<style scoped>
.toolbar { display: flex; gap: 10px; margin-bottom: 12px; align-items: center; }
.spacer { flex: 1; }
.mono { font-family: ui-monospace, monospace; font-size: 11px; }
</style>
