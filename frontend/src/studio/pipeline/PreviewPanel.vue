<template>
  <div class="preview">
    <div class="bar">
      <span>{{ nodeId ? "预览节点 " + nodeId : "选择画布节点后预览" }}</span>
      <el-button size="small" :disabled="!nodeId" :loading="loading"
                 @click="run">运行预览</el-button>
    </div>
    <el-table v-if="rows.length" :data="rows" size="small" height="140">
      <el-table-column v-for="c in columns" :key="c" :prop="c" :label="c" />
    </el-table>
    <el-empty v-else description="暂无预览结果" :image-size="60" />
    <div class="stats">
      <el-tag v-for="(s, k) in stats" :key="k" size="small"
              :type="s.status === 'success' ? 'success' : 'danger'">
        {{ k }} · {{ s.rows }} 行 · {{ s.ms }}ms
      </el-tag>
      <span v-if="error" class="err">{{ error }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { api, errMsg } from "../../api";

const props = defineProps({
  assetId: { type: Number, required: true },
  nodeId: { type: String, default: "" },
  contentFn: { type: Function, default: null },
});
const loading = ref(false);
const rows = ref([]);
const columns = ref([]);
const stats = ref({});
const error = ref("");

watch(() => props.nodeId, () => {
  rows.value = [];
  columns.value = [];
  stats.value = {};
  error.value = "";
});

async function run() {
  if (!props.nodeId) return;
  loading.value = true;
  error.value = "";
  try {
    const body = { node_id: props.nodeId, limit: 100 };
    if (props.contentFn) body.content = props.contentFn();
    const r = await api.post(`/pipelines/${props.assetId}/preview`, body);
    rows.value = r.rows || [];
    columns.value = rows.value.length ? Object.keys(rows.value[0]) : [];
    stats.value = r.node_stats || {};
  } catch (e) {
    error.value = errMsg(e);
    ElMessage.error(error.value);
  } finally {
    loading.value = false;
  }
}

defineExpose({ run });
</script>

<style scoped>
.preview { padding: 10px 12px; }
.bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
}
.stats { display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }
.err { color: #dc2626; font-size: 12px; }
</style>
