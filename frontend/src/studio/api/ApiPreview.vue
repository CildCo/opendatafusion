<template>
  <div class="preview">
    <div class="head">
      <span>预览</span>
      <el-button size="small" :loading="loading" @click="run">运行预览</el-button>
    </div>
    <div v-for="p in params" :key="p.name" class="prow">
      <span>{{ p.name }}{{ p.required ? " *" : "" }}</span>
      <el-input v-model="values[p.name]" size="small"
                :placeholder="p.example || p.type" />
    </div>
    <el-table v-if="rows.length" :data="rows" size="small" height="150">
      <el-table-column v-for="c in columns" :key="c" :prop="c" :label="c" />
    </el-table>
    <div class="meta">
      <el-tag v-if="meta.row_count !== undefined" size="small">
        {{ meta.row_count }} 行 · {{ meta.ms }}ms
      </el-tag>
      <span v-if="error" class="err">{{ error }}</span>
    </div>
    <pre v-if="meta.sql" class="sql">{{ meta.sql }}</pre>
  </div>
</template>

<script setup>
import { reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { api, errMsg } from "../../api";

const props = defineProps({
  assetId: { type: Number, required: true },
  params: { type: Array, default: () => [] },
  content: { type: Object, required: true },
});
const values = reactive({});
const rows = ref([]);
const columns = ref([]);
const meta = ref({});
const error = ref("");
const loading = ref(false);

async function run() {
  loading.value = true;
  error.value = "";
  try {
    const payload = {};
    const filters = props.content.query?.filters || [];
    for (const p of props.params) {
      const v = values[p.name];
      const usedIn = filters.some(
        (f) => f.param === p.name && f.op === "in");
      payload[p.name] = usedIn && typeof v === "string"
        ? v.split(",").map((s) => s.trim()).filter(Boolean)
        : v;
    }
    const r = await api.post(`/apis/${props.assetId}/preview`, {
      params: payload, limit: 100, content: props.content,
    });
    rows.value = r.rows || [];
    columns.value = r.columns || [];
    meta.value = r;
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
.preview { padding: 10px; }
.head { display: flex; justify-content: space-between; align-items: center;
        font-weight: 600; font-size: 13px; margin-bottom: 8px; }
.prow { display: grid; grid-template-columns: 120px 1fr; gap: 6px;
        align-items: center; margin-bottom: 6px; font-size: 12px; }
.meta { display: flex; gap: 8px; margin: 8px 0; align-items: center; }
.err { color: #dc2626; font-size: 12px; }
.sql { background: #0f172a; color: #e2e8f0; padding: 8px; border-radius: 6px;
       font-size: 11px; overflow: auto; max-height: 100px; }
</style>
