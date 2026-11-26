<template>
  <div ref="host" class="app-grid"
       :class="{ design, empty: !components.length, stacked: compact }"
       :style="gridStyle" @click.self="onBlank">
    <div v-for="c in components" v-show="design || visible(c)" :key="c.id"
         class="app-widget" :class="[c.type, {
           selected: selectedId === c.id,
           dimmed: design && !visible(c),
           card: isCard(c),
         }, toneFor(c),
         ]" :style="styleFor(c)" @click.stop="$emit('select', c.id)">
      <div v-if="design && !compact" class="widget-head"
           @pointerdown.stop="startDrag(c, $event)">
        <span class="widget-title">{{ c.title || typeLabel(c.type) }}</span>
        <span class="widget-type">{{ typeLabel(c.type) }}</span>
      </div>
      <div class="widget-body">
        <template v-if="c.type === 'container'">
          <div v-if="c.title" class="container-title">{{ c.title }}</div>
          <AppCanvas :page="nestedPage(c)" :data="data" :params="params"
                     :component-state="componentState" :design="design"
                     :stacked="compact" :selected-id="selectedId"
                     :on-submit="onSubmit" @select="$emit('select', $event)"
                     @drag-start="$emit('drag-start')"
                     @change="$emit('change')"
                     @change-end="$emit('change-end')"
                     @navigate="$emit('navigate', $event)"
                     @row="$emit('row', $event)"
                     @action="$emit('action', $event)"
                     @component-change="forwardChange" />
        </template>
        <template v-else-if="c.type === 'tabs'">
          <template v-if="design">
            <div v-for="tab in c.tabs || []" :key="tab.id"
                 class="tab-section">
              <div class="tab-title">{{ tab.title || tab.id }}</div>
              <AppCanvas :page="tabPage(tab)" :data="data"
                         :params="params"
                         :component-state="componentState" :design="design"
                         :stacked="compact" :selected-id="selectedId"
                         :on-submit="onSubmit"
                         @select="$emit('select', $event)"
                         @drag-start="$emit('drag-start')"
                         @change="$emit('change')"
                         @change-end="$emit('change-end')"
                         @navigate="$emit('navigate', $event)"
                         @row="$emit('row', $event)"
                         @action="$emit('action', $event)"
                         @component-change="forwardChange" />
            </div>
          </template>
          <el-tabs v-else :model-value="tabValue(c)" class="app-tabs"
                   @update:model-value="setTab(c, $event)">
            <el-tab-pane v-for="tab in c.tabs || []" :key="tab.id"
                         :label="tab.title || tab.id" :name="tab.id">
              <AppCanvas :page="tabPage(tab)" :data="data"
                         :params="params"
                         :component-state="componentState"
                         :stacked="compact" :on-submit="onSubmit"
                         @navigate="$emit('navigate', $event)"
                         @row="$emit('row', $event)"
                         @action="$emit('action', $event)"
                         @component-change="forwardChange" />
            </el-tab-pane>
          </el-tabs>
        </template>
        <template v-else-if="c.type === 'modal'">
          <template v-if="design">
            <div class="container-title">{{ modalLabel(c) }}</div>
            <AppCanvas :page="nestedPage(c)" :data="data" :params="params"
                       :component-state="componentState" :design="design"
                       :stacked="compact" :selected-id="selectedId"
                       :on-submit="onSubmit"
                       @select="$emit('select', $event)"
                       @drag-start="$emit('drag-start')"
                       @change="$emit('change')"
                       @change-end="$emit('change-end')"
                       @navigate="$emit('navigate', $event)"
                       @row="$emit('row', $event)"
                       @action="$emit('action', $event)"
                       @component-change="forwardChange" />
          </template>
          <template v-else>
            <el-button type="primary" @click="modalOpen[c.id] = true">
              {{ modalLabel(c) }}
            </el-button>
            <el-dialog v-model="modalOpen[c.id]"
                       :title="c.title || modalLabel(c)" append-to-body>
              <AppCanvas :page="nestedPage(c)" :data="data"
                         :params="params"
                         :component-state="componentState"
                         :stacked="compact" :on-submit="onSubmit"
                         @navigate="$emit('navigate', $event)"
                         @row="$emit('row', $event)"
                         @action="$emit('action', $event)"
                         @component-change="forwardChange" />
            </el-dialog>
          </template>
        </template>
        <AppComponent v-else :component="c" :entry="entryFor(c)"
                      :params="params" :components="componentState"
                      :visual="visualStyle(c)"
                      :on-submit="onSubmit" :design="design"
                      @navigate="$emit('navigate', $event)"
                      @row="$emit('row', { componentId: c.id, row: $event })"
                      @change="$emit('component-change', c.id, $event)"
                      @action="$emit('action', $event)" />
      </div>
      <span v-if="design && !compact && !visible(c)" class="hidden-flag">
        {{ t("aedit.hidden") }}
      </span>
      <span v-if="design && !compact" class="resize"
            @pointerdown.stop="startResize(c, $event)" />
    </div>
    <div v-if="design && !components.length" class="grid-empty">
      {{ t("aedit.canvasEmpty") }}
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { t } from "../../i18n";
import AppComponent from "./AppComponent.vue";
import { highlightTone, isVisible, interpolate,
         visualStyle } from "./bindings";
import { getRole } from "../../api";
import { cellWidthFor, gridStyleFor, maxGridBottom,
         resolveGridCollisions } from "../shared/grid";

const props = defineProps({
  page: { type: Object, required: true },
  data: { type: Object, default: () => ({}) },
  params: { type: Object, default: () => ({}) },
  componentState: { type: Object, default: () => ({}) },
  selectedId: { type: String, default: "" },
  onSubmit: { type: Function, default: null },
  design: Boolean,
  stacked: { type: Boolean, default: null },
  columns: { type: Number, default: 12 },
  rowHeight: { type: Number, default: 72 },
});
const emit = defineEmits([
  "select", "change", "change-end", "drag-start", "navigate", "row",
  "action", "component-change",
]);

const host = ref(null);
const width = ref(960);
let observer = null;
let drag = null;

const components = computed(() => props.page?.components || []);
const compact = computed(() => props.stacked === null
  ? width.value < 720 : props.stacked);
const cellWidth = computed(
  () => cellWidthFor(width.value, props.columns));
const gridStyle = computed(() => (compact.value
  ? { backgroundSize: "100% 24px", minHeight: "0" }
  : {
    backgroundSize: `100% ${props.rowHeight}px`,
    minHeight: `${Math.max(420, (maxBottom.value + 1) * props.rowHeight)}px`,
  }));
const maxBottom = computed(() => maxGridBottom(
  components.value, layoutOf));
const activeTabs = reactive({});
const modalOpen = reactive({});

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
  return isVisible(c, props.params, getRole() || "viewer");
}

function layoutOf(c) {
  return c.layout || { x: 0, y: 0, w: 12, h: 2 };
}

function toneFor(c) {
  const tone = highlightTone(c, props.params);
  return tone ? `tone-${tone}` : "";
}

function styleFor(c) {
  const layout = layoutOf(c);
  if (compact.value) {
    return {
      position: "static",
      width: "100%",
      height: "auto",
      minHeight: `${Math.max(48, layout.h * props.rowHeight)}px`,
      order: layout.y * 100 + layout.x,
      ...visualStyle(c),
    };
  }
  return { ...gridStyleFor(layout, cellWidth.value, props.rowHeight),
           ...visualStyle(c) };
}

function nestedPage(comp) {
  return { params: props.page?.params || [],
           components: comp.children || [] };
}

function tabPage(tab) {
  return { params: props.page?.params || [],
           components: tab.components || [] };
}

function tabValue(comp) {
  return activeTabs[comp.id] || comp.tabs?.[0]?.id || "";
}

function setTab(comp, value) {
  activeTabs[comp.id] = value;
}

function modalLabel(comp) {
  return interpolate(comp.label || t("acomp.open"), props.params, {
    components: props.componentState,
  });
}

function forwardChange(componentId, values) {
  emit("component-change", componentId, values);
}

function onBlank() {
  if (props.design) emit("select", "");
}

function resolveCollisions(moved) {
  resolveGridCollisions(components.value, moved, layoutOf);
}

function ensureLayout(c) {
  if (!c.layout) c.layout = { x: 0, y: 0, w: 6, h: 2 };
  return c.layout;
}

function startDrag(c, event) {
  if (!props.design || compact.value) return;
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
  if (!props.design || compact.value) return;
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
.app-widget.tone-info { border-color: #93c5fd; background: #eff6ff; }
.app-widget.tone-success { border-color: #86efac; background: #f0fdf4; }
.app-widget.tone-warning { border-color: #fcd34d; background: #fffbeb; }
.app-widget.tone-danger { border-color: #fca5a5; background: #fef2f2; }
.app-grid.stacked {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 0;
  background-image: none;
}
.app-grid.stacked .app-widget { overflow: visible; }
.app-grid.stacked .widget-body { height: auto; overflow: visible; }
.container-title {
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 8px;
}
.tab-section { margin-bottom: 12px; }
.tab-title {
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  padding: 4px 8px;
  background: #eef2f7;
  border-radius: 4px;
  margin-bottom: 8px;
}
.app-tabs { min-height: 40px; }
.app-tabs :deep(.el-tabs__content) { overflow: visible; }
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
