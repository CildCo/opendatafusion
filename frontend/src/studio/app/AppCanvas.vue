<template>
  <div ref="host" class="app-grid" :class="{ design, empty: !components.length }"
       :style="gridStyle" @click.self="onBlank">
    <div v-for="c in components" v-show="design || visible(c)" :key="c.id"
         class="app-widget" :class="[c.type, {
           selected: selectedId === c.id,
           dimmed: design && !visible(c),
           card: isCard(c),
         }]" :style="styleFor(c)" @click.stop="$emit('select', c.id)">
      <div v-if="design" class="widget-head"
           @pointerdown.stop="startDrag(c, $event)">
        <span class="widget-title">{{ c.title || typeLabel(c.type) }}</span>
        <span class="widget-type">{{ typeLabel(c.type) }}</span>
      </div>
      <div class="widget-body">
        <AppComponent :component="c" :entry="entryFor(c)" :params="params"
                      :on-submit="onSubmit" :design="design"
                      @navigate="$emit('navigate', $event)"
                      @row="$emit('row', $event)" />
      </div>
      <span v-if="design && !visible(c)" class="hidden-flag">
        {{ t("aedit.hidden") }}
      </span>
      <span v-if="design" class="resize"
            @pointerdown.stop="startResize(c, $event)" />
    </div>
    <div v-if="design && !components.length" class="grid-empty">
      {{ t("aedit.canvasEmpty") }}
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { t } from "../../i18n";
import AppComponent from "./AppComponent.vue";
import { isVisible } from "./bindings";

const props = defineProps({
  page: { type: Object, required: true },
  data: { type: Object, default: () => ({}) },
  params: { type: Object, default: () => ({}) },
  selectedId: { type: String, default: "" },
  onSubmit: { type: Function, default: null },
  design: Boolean,
  columns: { type: Number, default: 12 },
  rowHeight: { type: Number, default: 72 },
});
const emit = defineEmits([
  "select", "change", "change-end", "drag-start", "navigate", "row",
]);

const host = ref(null);
const width = ref(960);
let observer = null;
let drag = null;

const components = computed(() => props.page?.components || []);
const cellWidth = computed(
  () => Math.max(32, (width.value - 8) / props.columns));
const gridStyle = computed(() => ({
  backgroundSize: `100% ${props.rowHeight}px`,
  minHeight: `${Math.max(420, (maxBottom.value + 1) * props.rowHeight)}px`,
}));
const maxBottom = computed(() => components.value.reduce(
  (m, c) => Math.max(m, (c.layout?.y || 0) + (c.layout?.h || 1)), 0));

const LABELS = {
  text: "aedit.compText",
  heading: "aedit.compHheading",
  divider: "aedit.compDivider",
  image: "aedit.compImage",
  button: "aedit.compButton",
  progress: "aedit.compProgress",
  metric: "aedit.compMetric",
  table: "aedit.compTable",
  form: "aedit.compForm",
};

function typeLabel(type) {
  return LABELS[type] ? t(LABELS[type]) : type;
}

function isCard(c) {
  return !["text", "heading", "divider"].includes(c.type);
}

function entryFor(c) {
  return props.data?.[c.id] || null;
}

function visible(c) {
  return isVisible(c, props.params);
}

function layoutOf(c) {
  return c.layout || { x: 0, y: 0, w: 12, h: 2 };
}

function styleFor(c) {
  const l = layoutOf(c);
  return {
    left: `${l.x * cellWidth.value + 4}px`,
    top: `${l.y * props.rowHeight + 4}px`,
    width: `${l.w * cellWidth.value - 8}px`,
    height: `${l.h * props.rowHeight - 8}px`,
  };
}

function onBlank() {
  if (props.design) emit("select", "");
}

function resolveCollisions(moved) {
  const others = components.value
    .filter((item) => item.id !== moved.id && item.layout)
    .sort((a, b) => a.layout.y - b.layout.y || a.layout.x - b.layout.x);
  let floor = moved.layout.y + moved.layout.h;
  for (const item of others) {
    const l = item.layout;
    const xOverlap = moved.layout.x < l.x + l.w
      && l.x < moved.layout.x + moved.layout.w;
    if (!xOverlap) continue;
    if (l.y < floor && l.y + l.h > moved.layout.y) l.y = floor;
    floor = Math.max(floor, l.y + l.h);
  }
}

function ensureLayout(c) {
  if (!c.layout) c.layout = { x: 0, y: 0, w: 6, h: 2 };
  return c.layout;
}

function startDrag(c, event) {
  if (!props.design) return;
  event.preventDefault();
  emit("drag-start");
  const l = ensureLayout(c);
  const sx = event.clientX;
  const sy = event.clientY;
  const ox = l.x;
  const oy = l.y;
  drag = (e) => {
    l.x = Math.max(0, ox + Math.round((e.clientX - sx) / cellWidth.value));
    l.y = Math.max(0, oy + Math.round((e.clientY - sy) / props.rowHeight));
    l.x = Math.min(l.x, props.columns - l.w);
    resolveCollisions(c);
    emit("change");
  };
  bind();
}

function startResize(c, event) {
  if (!props.design) return;
  event.preventDefault();
  event.stopPropagation();
  emit("drag-start");
  const l = ensureLayout(c);
  const sx = event.clientX;
  const sy = event.clientY;
  const ow = l.w;
  const oh = l.h;
  drag = (e) => {
    l.w = Math.max(1, ow + Math.round((e.clientX - sx) / cellWidth.value));
    l.h = Math.max(1, oh + Math.round((e.clientY - sy) / props.rowHeight));
    l.w = Math.min(l.w, props.columns - l.x);
    resolveCollisions(c);
    emit("change");
  };
  bind();
}

function bind() {
  window.addEventListener("pointermove", onMove);
  window.addEventListener("pointerup", stop);
}
function onMove(e) {
  if (drag) drag(e);
}
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
  if (host.value) observer.observe(host.value);
});
onBeforeUnmount(() => {
  stop();
  if (observer) observer.disconnect();
});
</script>

<style scoped>
.app-grid {
  position: relative;
  background-color: #f8fafc;
  background-image: linear-gradient(#eef2f7 1px, transparent 1px);
  min-height: 420px;
  padding-bottom: 4px;
}
.app-widget {
  position: absolute;
  box-sizing: border-box;
  overflow: hidden;
  border: 1px solid transparent;
  border-radius: 6px;
}
.app-widget.card {
  background: #fff;
  border-color: #e5e7eb;
  padding: 10px 12px;
}
.app-widget.selected {
  border-color: #2563eb;
  box-shadow: 0 0 0 1px #2563eb;
}
.app-widget.dimmed .widget-body { opacity: 0.35; }
.widget-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 11px;
  color: #64748b;
  background: #f1f5f9;
  margin: -10px -12px 8px;
  padding: 3px 8px;
  cursor: move;
  user-select: none;
}
.app-widget:not(.card) .widget-head {
  margin: 0 0 4px;
  background: #eef2f7;
  border-radius: 4px;
}
.widget-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
  color: #475569;
}
.widget-type { flex: none; color: #94a3b8; }
.widget-body { height: 100%; overflow: auto; }
.app-grid.design .app-widget.card .widget-body {
  height: calc(100% - 25px);
}
.resize {
  position: absolute;
  right: 2px;
  bottom: 2px;
  width: 12px;
  height: 12px;
  cursor: nwse-resize;
  background: linear-gradient(135deg, transparent 45%, #94a3b8 45%,
    #94a3b8 55%, transparent 55%, transparent 70%, #94a3b8 70%,
    #94a3b8 80%, transparent 80%);
}
.hidden-flag {
  position: absolute;
  top: 2px;
  right: 8px;
  font-size: 10px;
  color: #b45309;
  background: #fef3c7;
  border-radius: 3px;
  padding: 0 4px;
}
.grid-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  font-size: 12px;
  pointer-events: none;
}
</style>
