<template>
  <div ref="host" class="grid" :style="gridStyle">
    <DashboardWidget v-for="w in widgets" :key="w.id" :widget="w"
                     :data="data?.[w.id]" :selected="selectedId === w.id"
                     :readonly="readonly" :drillable="drillable"
                     :style="styleFor(w)"
                     @select="$emit('select', w)"
                     @drag-start="startDrag(w, $event)"
                     @resize-start="startResize(w, $event)"
                     @filter="$emit('filter', $event)"
                     @drill="$emit('drill', $event)"
                     @interact="$emit('interact', $event)" />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import DashboardWidget from "./DashboardWidget.vue";
import { cellWidthFor, gridStyleFor, maxGridBottom,
         resolveGridCollisions } from "../shared/grid";

const props = defineProps({
  widgets: { type: Array, default: () => [] },
  data: { type: Object, default: null },
  columns: { type: Number, default: 12 },
  rowHeight: { type: Number, default: 80 },
  selectedId: { type: String, default: "" },
  readonly: Boolean,
  drillable: Boolean,
});
const emit = defineEmits(["select", "change", "change-end", "drag-start",
                          "filter", "drill", "interact"]);
const host = ref(null);
const width = ref(960);
let observer = null;
let drag = null;

const cellWidth = computed(
  () => cellWidthFor(width.value, props.columns));
const gridStyle = computed(() => ({
  backgroundSize: `100% ${props.rowHeight}px`,
  minHeight: `${Math.max(520, (maxGridBottom(
    props.widgets, (item) => item) + 1) * props.rowHeight)}px`,
}));

function styleFor(w) {
  return gridStyleFor(w, cellWidth.value, props.rowHeight);
}

function resolveCollisions(moved) {
  resolveGridCollisions(props.widgets, moved, (item) => item);
}

function startDrag(w, event) {
  event.preventDefault();
  emit("drag-start");
  const sx = event.clientX;
  const sy = event.clientY;
  const ox = w.x;
  const oy = w.y;
  drag = (e) => {
    w.x = Math.max(0, ox + Math.round((e.clientX - sx) / cellWidth.value));
    w.y = Math.max(0, oy + Math.round((e.clientY - sy) / props.rowHeight));
    w.x = Math.min(w.x, props.columns - w.w);
    resolveCollisions(w);
    emit("change");
  };
  bind();
}

function startResize(w, event) {
  event.preventDefault();
  emit("drag-start");
  const sx = event.clientX;
  const sy = event.clientY;
  const ow = w.w;
  const oh = w.h;
  drag = (e) => {
    w.w = Math.max(1, ow + Math.round((e.clientX - sx) / cellWidth.value));
    w.h = Math.max(1, oh + Math.round((e.clientY - sy) / props.rowHeight));
    w.w = Math.min(w.w, props.columns - w.x);
    resolveCollisions(w);
    emit("change");
  };
  bind();
}

function bind() {
  window.addEventListener("pointermove", onMove);
  window.addEventListener("pointerup", stop);
}
function onMove(e) { if (drag) drag(e); }
function stop() {
  if (drag) {
    drag = null;
    emit("change-end");
  }
  window.removeEventListener("pointermove", onMove);
  window.removeEventListener("pointerup", stop);
}

onMounted(() => {
  width.value = host.value?.clientWidth || 960;
  observer = new ResizeObserver(() => {
    width.value = host.value?.clientWidth || width.value;
  });
  observer.observe(host.value);
});
onBeforeUnmount(() => {
  stop();
  if (observer) observer.disconnect();
});
</script>

<style scoped>
.grid { position: relative; min-height: 520px;
        background-color: #f8fafc;
        background-image: linear-gradient(#eef2f7 1px, transparent 1px); }
</style>
