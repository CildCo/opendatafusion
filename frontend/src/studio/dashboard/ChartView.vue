<template>
  <div ref="host" class="chart"></div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as echarts from "echarts";

const props = defineProps({ option: { type: Object, required: true } });
const emit = defineEmits(["click"]);
const host = ref(null);
let chart = null;
let observer = null;

onMounted(() => {
  chart = echarts.init(host.value);
  chart.setOption(props.option);
  chart.on("click", (p) => emit("click", p));
  observer = new ResizeObserver(() => chart && chart.resize());
  observer.observe(host.value);
});
watch(() => props.option, (o) => chart && chart.setOption(o, true),
      { deep: true });
onBeforeUnmount(() => {
  if (observer) observer.disconnect();
  if (chart) chart.dispose();
});
</script>

<style scoped>
.chart { width: 100%; height: 100%; min-height: 80px; }
</style>
