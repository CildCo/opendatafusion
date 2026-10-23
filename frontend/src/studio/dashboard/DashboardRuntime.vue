<template>
  <div class="runtime">
    <DashboardFilters :params="content.params || []" :value="params"
                      @update:value="$emit('update:params', $event)"
                      @refresh="$emit('refresh')" />
    <DashboardGrid :widgets="content.widgets || []" :data="data"
                   :columns="content.columns || 12"
                   :row-height="content.row_height || 80"
                   :selected-id="''" readonly @filter="onFilter" />
  </div>
</template>

<script setup>
import DashboardFilters from "./DashboardFilters.vue";
import DashboardGrid from "./DashboardGrid.vue";

const props = defineProps({
  content: { type: Object, required: true },
  data: { type: Object, default: () => ({}) },
  params: { type: Object, default: () => ({}) },
});
const emit = defineEmits(["update:params", "refresh"]);

function onFilter({ param, value }) {
  emit("update:params", { ...props.params, [param]: value });
  emit("refresh");
}
</script>

<style scoped>
.runtime { min-height: 200px; }
</style>
