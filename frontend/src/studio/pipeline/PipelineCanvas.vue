<template>
  <div class="canvas-wrap" @dragover.prevent @drop.prevent="onDrop">
    <NodePalette @add="add" />
    <VueFlow v-model:nodes="nodes" v-model:edges="edges"
             :node-types="nodeTypes" multi-selection-key-code="Shift"
             :default-viewport="{ zoom: 0.9 }" fit-view-on-init
             @connect="onConnect" @node-click="onNodeClick"
             @nodes-delete="notify" @edges-delete="notify"
             @node-drag-stop="notify">
      <Background />
      <Controls />
      <MiniMap />
    </VueFlow>
    <el-button class="layout-btn" size="small" @click="autoLayout">
      {{ t("ped.autoLayout") }}
    </el-button>
  </div>
</template>

<script setup>
import { markRaw, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useVueFlow, VueFlow } from "@vue-flow/core";
import { Background } from "@vue-flow/background";
import { Controls } from "@vue-flow/controls";
import { MiniMap } from "@vue-flow/minimap";
import "@vue-flow/core/dist/style.css";
import "@vue-flow/core/dist/theme-default.css";
import NodePalette from "./NodePalette.vue";
import PipelineNode from "./PipelineNode.vue";
import { newNode, toFlowEdges, toFlowNodes } from "./nodes";
import { t } from "../../i18n";

const props = defineProps({
  content: { type: Object, default: () => ({}) },
  runtime: { type: Object, default: null },
});
const emit = defineEmits(["select", "change"]);
const nodeTypes = { pipeline: markRaw(PipelineNode) };
let clipboard = null;
let internal = false;

function notify() {
  internal = true;
  emit("change");
}
const nodes = ref(toFlowNodes(props.content.nodes));
const edges = ref(toFlowEdges(props.content.edges));

function syncRuntime() {
  const map = props.runtime || {};
  for (const node of nodes.value) {
    node.data = { ...node.data, runtime: map[node.id] || null };
  }
}

watch(() => props.content, (c) => {
  if (internal) {
    internal = false;
    syncRuntime();
    return;
  }
  nodes.value = toFlowNodes(c.nodes);
  edges.value = toFlowEdges(c.edges);
  syncRuntime();
  emit("select", null);
}, { deep: true });
watch(() => props.runtime, syncRuntime, { deep: true });

function add(type, position) {
  const node = newNode(type, nodes.value.length);
  if (position) node.position = position;
  nodes.value = [...nodes.value, node];
  notify();
}

const { screenToFlowCoordinate } = useVueFlow();

function onDrop(event) {
  const kind = event.dataTransfer.getData("application/x-odf-node");
  if (!kind) return;
  const position = screenToFlowCoordinate({
    x: event.clientX, y: event.clientY,
  });
  add(kind, position);
}

function selectedIds() {
  return new Set(nodes.value.filter((node) => node.selected)
    .map((node) => node.id));
}

function copySelection() {
  const ids = selectedIds();
  if (!ids.size) return false;
  const picked = nodes.value.filter((node) => ids.has(node.id))
    .map((node) => ({
      id: node.id,
      position: { ...node.position },
      data: {
        kind: node.data.kind,
        name: node.data.name,
        config: JSON.parse(JSON.stringify(node.data.config || {})),
      },
    }));
  const links = edges.value.filter((edge) => ids.has(edge.source)
    && ids.has(edge.target)).map((edge) => ({
      source: edge.source, target: edge.target,
      data: edge.data ? { ...edge.data } : {},
    }));
  clipboard = { nodes: picked, edges: links };
  return true;
}

function pasteSelection() {
  if (!clipboard) return false;
  const stamp = Date.now().toString(36);
  const mapping = new Map();
  const pasted = clipboard.nodes.map((node, index) => {
    const id = `${node.data.kind}_${stamp}_${index}`;
    mapping.set(node.id, id);
    return {
      id,
      type: "pipeline",
      position: { x: node.position.x + 40, y: node.position.y + 40 },
      selected: true,
      data: {
        kind: node.data.kind,
        name: `${node.data.name} copy`,
        config: JSON.parse(JSON.stringify(node.data.config || {})),
        runtime: null,
      },
    };
  });
  const links = clipboard.edges.map((edge, index) => ({
    id: `copy_${stamp}_${index}`,
    source: mapping.get(edge.source),
    target: mapping.get(edge.target),
    data: edge.data,
  }));
  nodes.value = [...nodes.value.map((n) => ({ ...n, selected: false })),
                 ...pasted];
  edges.value = [...edges.value, ...links];
  notify();
  return true;
}

function autoLayout() {
  const incoming = new Map(nodes.value.map((node) => [node.id, 0]));
  const next = new Map(nodes.value.map((node) => [node.id, []]));
  for (const edge of edges.value) {
    if (!incoming.has(edge.source) || !incoming.has(edge.target)) continue;
    next.get(edge.source).push(edge.target);
    incoming.set(edge.target, (incoming.get(edge.target) || 0) + 1);
  }
  const level = new Map();
  const queue = nodes.value.filter((node) => !incoming.get(node.id))
    .map((node) => node.id);
  if (!queue.length && nodes.value.length) queue.push(nodes.value[0].id);
  for (const id of queue) level.set(id, 0);
  let guard = 0;
  while (queue.length && guard < nodes.value.length * nodes.value.length + 10) {
    guard += 1;
    const id = queue.shift();
    for (const target of next.get(id) || []) {
      const candidate = (level.get(id) || 0) + 1;
      if (!level.has(target) || level.get(target) < candidate) {
        level.set(target, candidate);
        queue.push(target);
      }
    }
  }
  const rows = new Map();
  for (const node of nodes.value) {
    const depth = level.get(node.id) || 0;
    const index = rows.get(depth) || 0;
    rows.set(depth, index + 1);
    node.position = { x: 80 + depth * 250, y: 60 + index * 110 };
  }
  notify();
}

function onKey(event) {
  const target = event.target;
  if (target && target.closest &&
      target.closest('input, textarea, select, [contenteditable="true"], '
                     + '.cm-editor')) {
    return;
  }
  if (!(event.ctrlKey || event.metaKey)) return;
  const key = String(event.key || "").toLowerCase();
  if (key === "c" && copySelection()) {
    event.preventDefault();
  } else if (key === "v" && pasteSelection()) {
    event.preventDefault();
  }
}

onMounted(() => window.addEventListener("keydown", onKey));
onBeforeUnmount(() => window.removeEventListener("keydown", onKey));
function onConnect(params) {
  edges.value = [...edges.value, { ...params, id: `e${Date.now()}` }];
  notify();
}

function onNodeClick({ node }) {
  emit("select", node);
}

function serialize(settings = {}) {
  const kinds = Object.fromEntries(
    nodes.value.map((n) => [n.id, n.data.kind]));
  const assigned = {};
  const edgeRows = edges.value.map((e) => {
    const row = { from: e.source, to: e.target };
    const kind = kinds[e.target];
    if (kind === "join" || kind === "union") {
      const used = assigned[e.target] || new Set();
      let port = e.data?.to_port;
      if (!port || !["left", "right"].includes(port) || used.has(port)) {
        port = used.has("left") ? "right" : "left";
      }
      used.add(port);
      assigned[e.target] = used;
      row.to_port = port;
    }
    return row;
  });
  return {
    nodes: nodes.value.map((n) => ({
      id: n.id,
      type: n.data.kind,
      name: n.data.name,
      config: JSON.parse(JSON.stringify(n.data.config || {})),
      position: n.position,
    })),
    edges: edgeRows,
    settings,
  };
}

defineExpose({ serialize, autoLayout, copySelection, pasteSelection, notify });
</script>

<style scoped>
.canvas-wrap { height: 100%; position: relative; }
.layout-btn { position: absolute; z-index: 6; right: 12px; top: 10px; }
</style>
