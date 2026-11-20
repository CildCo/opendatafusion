<template>
  <div class="graph-wrap" :style="{ height: `${height}px` }">
    <VueFlow v-if="nodes.length" :nodes="flowNodes" :edges="flowEdges"
             :node-types="nodeTypes" :nodes-connectable="false"
             :nodes-draggable="true" :min-zoom="0.3" :max-zoom="1.6"
             fit-view-on-init @node-click="onClick">
      <Background pattern-color="#e2e8f0" :gap="18" />
      <Controls :show-interactive="false" />
    </VueFlow>
    <empty-state v-else :title="emptyText" />
  </div>
</template>

<script setup>
import { computed, markRaw } from "vue";
import { MarkerType, VueFlow } from "@vue-flow/core";
import { Background } from "@vue-flow/background";
import { Controls } from "@vue-flow/controls";
import "@vue-flow/core/dist/style.css";
import "@vue-flow/core/dist/theme-default.css";
import EmptyState from "./EmptyState.vue";
import GraphNode from "./GraphNode.vue";

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  edges: { type: Array, default: () => [] },
  height: { type: Number, default: 380 },
  emptyText: { type: String, default: "" },
});
const emit = defineEmits(["select"]);

const nodeTypes = { odf: markRaw(GraphNode) };

const NODE_WIDTH = 190;
const NODE_GAP_X = 260;
const NODE_GAP_Y = 88;

function layout(items, links) {
  const ids = items.map((n) => n.id);
  const incoming = new Map(ids.map((id) => [id, 0]));
  const next = new Map(ids.map((id) => [id, []]));
  for (const edge of links) {
    if (next.has(edge.from) && incoming.has(edge.to)) {
      next.get(edge.from).push(edge.to);
      incoming.set(edge.to, (incoming.get(edge.to) || 0) + 1);
    }
  }
  const level = new Map();
  const queue = ids.filter((id) => !incoming.get(id));
  if (!queue.length && ids.length) queue.push(ids[0]);
  for (const id of queue) level.set(id, 0);
  let guard = 0;
  while (queue.length && guard < ids.length * ids.length + 10) {
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
  const groups = new Map();
  for (const item of items) {
    const l = level.has(item.id) ? level.get(item.id) : 0;
    if (!groups.has(l)) groups.set(l, []);
    groups.get(l).push(item.id);
  }
  const positions = new Map();
  for (const [l, idsInLevel] of groups) {
    const offset = ((groups.get(Math.max(...groups.keys()))?.length || 1)
      - idsInLevel.length) / 2;
    idsInLevel.forEach((id, index) => {
      positions.set(id, {
        x: 40 + l * NODE_GAP_X,
        y: 40 + (index + Math.max(0, offset)) * NODE_GAP_Y,
      });
    });
  }
  return positions;
}

const flowNodes = computed(() => {
  const links = props.edges.map((e) => ({ from: e.from, to: e.to }));
  const positions = layout(props.nodes, links);
  return props.nodes.map((node) => ({
    id: node.id,
    type: "odf",
    position: positions.get(node.id) || { x: 40, y: 40 },
    data: {
      label: node.name || node.label || node.id,
      type: node.type || "table",
      subtitle: node.subtitle ?? (node.type || ""),
    },
  }));
});

const flowEdges = computed(() => {
  const seen = new Set();
  const out = [];
  for (const edge of props.edges) {
    const key = `${edge.from}->${edge.to}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({
      id: key,
      source: edge.from,
      target: edge.to,
      type: "smoothstep",
      animated: false,
      style: { stroke: "#94a3b8", strokeWidth: 1.4 },
      markerEnd: { type: MarkerType.ArrowClosed, color: "#94a3b8",
                   width: 16, height: 16 },
    });
  }
  return out;
});

function onClick(event) {
  emit("select", event.node?.id);
}
</script>

<style scoped>
.graph-wrap {
  width: 100%;
  background: #fbfcfe;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
  position: relative;
}
:deep(.vue-flow__edge-path) { transition: stroke 0.15s; }
</style>
