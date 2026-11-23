<template>
  <el-drawer :model-value="modelValue" :title="t('lin.title')" size="720px"
             @update:model-value="$emit('update:modelValue', $event)"
             @open="load">
    <div v-loading="loading" class="lineage-body">
      <template v-if="data.nodes.length">
        <graph-canvas :nodes="data.nodes" :edges="data.edges" :height="320" />
        <div class="section-title">{{ t("lin.columnLineage") }}</div>
        <el-table v-if="data.column_edges.length" :data="data.column_edges"
                  size="small" border max-height="320">
          <el-table-column prop="from" :label="t('lin.from')" min-width="150"
                           show-overflow-tooltip />
          <el-table-column prop="from_column" :label="t('lin.fromColumn')"
                           min-width="120" />
          <el-table-column prop="to" :label="t('lin.to')" min-width="150"
                           show-overflow-tooltip />
          <el-table-column prop="to_column" :label="t('lin.toColumn')"
                           min-width="120" />
        </el-table>
        <el-empty v-else :description="t('lin.noColumns')" :image-size="60" />
      </template>
      <el-empty v-else-if="!loading" :description="t('lin.empty')"
                :image-size="80" />
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, watch } from "vue";
import { api } from "../api";
import { t } from "../i18n";
import GraphCanvas from "./GraphCanvas.vue";

const props = defineProps({
  modelValue: Boolean,
  assetId: { type: Number, default: 0 },
});
defineEmits(["update:modelValue"]);

const loading = ref(false);
const data = ref({ nodes: [], edges: [], column_edges: [] });

async function load() {
  data.value = { nodes: [], edges: [], column_edges: [] };
  if (!props.assetId) return;
  loading.value = true;
  try {
    data.value = await api.get(`/assets/${props.assetId}/lineage`);
  } catch {
    data.value = { nodes: [], edges: [], column_edges: [] };
  } finally {
    loading.value = false;
  }
}

watch(() => props.assetId, () => {
  if (props.modelValue) load();
});
</script>

<style scoped>
.lineage-body { min-height: 200px; }
.section-title { margin: 18px 0 8px; font-weight: 600; font-size: 13px; }
</style>
