<template>
  <div class="runtime">
    <DashboardFilters :params="content.params || []" :value="params"
                      @update:value="$emit('update:params', $event)"
                      @refresh="$emit('refresh')" @reset="resetParams" />
    <DashboardGrid :widgets="content.widgets || []" :data="data"
                   :columns="content.columns || 12"
                   :row-height="content.row_height || 80"
                   :selected-id="''" readonly :drillable="drillable"
                   @filter="onFilter" @drill="onDrill"
                   @interact="onInteract" />
    <drill-drawer v-if="drillable && assetId" v-model="drillOpen"
                  :asset-id="assetId" :widget="drill.widget"
                  :dimension="drill.dimension" :value="drill.value"
                  :params="params" />
  </div>
</template>

<script setup>
import { ref } from "vue";
import DashboardFilters from "./DashboardFilters.vue";
import DashboardGrid from "./DashboardGrid.vue";
import DrillDrawer from "./DrillDrawer.vue";

const props = defineProps({
  content: { type: Object, required: true },
  data: { type: Object, default: () => ({}) },
  params: { type: Object, default: () => ({}) },
  assetId: { type: Number, default: null },
  drillable: Boolean,
});
const emit = defineEmits(["update:params", "refresh", "navigate"]);
const drillOpen = ref(false);
const drill = ref({ widget: null, dimension: null, value: null });

function resetParams() {
  const defaults = {};
  for (const param of props.content.params || []) {
    if (param.name) defaults[param.name] = param.default ?? "";
  }
  emit("update:params", defaults);
  emit("refresh");
}

function onFilter({ param, value }) {
  emit("update:params", { ...props.params, [param]: value });
  emit("refresh");
}

function onInteract({ url }) {
  if (!url) return;
  if (String(url).startsWith("http://") || String(url).startsWith("https://")) {
    window.open(url, "_blank", "noopener,noreferrer");
    return;
  }
  emit("navigate", url);
}

function onDrill(context) {
  drill.value = context;
  drillOpen.value = true;
}
</script>

<style scoped>
.runtime { min-height: 200px; }
</style>
