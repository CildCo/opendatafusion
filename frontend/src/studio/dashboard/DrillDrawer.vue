<template>
  <el-drawer :model-value="modelValue" :title="title" size="760px"
             @update:model-value="$emit('update:modelValue', $event)">
    <div class="head">
      <el-tag v-if="dimension" size="small" type="info">
        {{ dimension }} = {{ value }}
      </el-tag>
      <span class="muted">{{ t("drill.hint") }}</span>
      <div class="spacer" />
      <el-button size="small" :disabled="!rows.length" @click="download">
        {{ t("drill.export") }}
      </el-button>
      <el-button size="small" :loading="loading" @click="load">
        {{ t("drill.refresh") }}
      </el-button>
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table v-else :data="rows" size="small" height="calc(100vh - 220px)"
              v-loading="loading">
      <el-table-column v-for="c in columns" :key="c" :prop="c"
                       :label="c" min-width="120" show-overflow-tooltip />
    </el-table>
    <div class="stats">
      {{ t("drill.rows").replace("{count}", rowCount)
        .replace("{ms}", ms) }}
    </div>
  </el-drawer>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { api, errMsg } from "../../api";
import { t } from "../../i18n";

const props = defineProps({
  modelValue: Boolean,
  assetId: { type: Number, required: true },
  widget: { type: Object, default: null },
  dimension: { type: String, default: null },
  value: { type: [String, Number], default: null },
  params: { type: Object, default: () => ({}) },
});
defineEmits(["update:modelValue"]);
const loading = ref(false);
const error = ref("");
const columns = ref([]);
const rows = ref([]);
const rowCount = ref(0);
const ms = ref(0);

const title = computed(() => {
  const base = t("drill.title");
  return props.widget?.title ? `${base} · ${props.widget.title}` : base;
});

async function load() {
  if (!props.widget) return;
  loading.value = true;
  error.value = "";
  try {
    const r = await api.post(`/dashboards/${props.assetId}/drill`, {
      widget_id: props.widget.id,
      dimension: props.dimension,
      value: props.value,
      params: props.params || {},
      limit: 1000,
    });
    columns.value = r.columns || [];
    rows.value = r.rows || [];
    rowCount.value = r.row_count || 0;
    ms.value = r.ms || 0;
  } catch (e) {
    error.value = errMsg(e);
  } finally {
    loading.value = false;
  }
}

function download() {
  try {
    const header = columns.value.join(",");
    const body = rows.value.map((row) =>
      columns.value.map((c) => {
        const value = row[c];
        const text = value === null || value === undefined ? "" : String(value);
        return `"${text.replace(/"/g, '""')}"`;
      }).join(",")).join("\n");
    const blob = new Blob([`${header}\n${body}`], {
      type: "text/csv;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `drill-${props.widget?.id || "rows"}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    ElMessage.error(t("drill.exportFailed"));
  }
}

watch(() => props.modelValue, (open) => {
  if (open) load();
});
</script>

<style scoped>
.head { display: flex; gap: 8px; align-items: center; margin-bottom: 10px; }
.spacer { flex: 1; }
.muted { font-size: 12px; color: #6b7280; }
.stats { margin-top: 8px; font-size: 12px; color: #475569; }
</style>
