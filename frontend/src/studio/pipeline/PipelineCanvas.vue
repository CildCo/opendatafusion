<template>
  <div class="canvas-wrap">
    <NodePalette @add="add" />
    <VueFlow v-model:nodes="nodes" v-model:edges="edges"
             :default-viewport="{ zoom: 0.9 }" fit-view-on-init
             @connect="onConnect" @node-click="onNodeClick"
             @nodes-delete="$emit('change')" @edges-delete="$emit('change')"
             @node-drag-stop="$emit('change')">
      <Background />
      <Controls />
      <MiniMap />
    </VueFlow>
  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { VueFlow } from "@vue-flow/core";
import { Background } from "@vue-flow/background";
import { Controls } from "@vue-flow/controls";
import { MiniMap } from "@vue-flow/minimap";
import "@vue-flow/core/dist/style.css";
import "@vue-flow/core/dist/theme-default.css";
import NodePalette from "./NodePalette.vue";
import { newNode, toFlowEdges, toFlowNodes } from "./nodes";

const props = defineProps({ content: { type: Object, default: () => ({}) } });
const emit = defineEmits(["select", "change"]);
const nodes = ref(toFlowNodes(props.content.nodes));
const edges = ref(toFlowEdges(props.content.edges));

watch(() => props.content, (c) => {
  nodes.value = toFlowNodes(c.nodes);
  edges.value = toFlowEdges(c.edges);
}, { deep: true });

function add(type) {
  nodes.value = [...nodes.value, newNode(type, nodes.value.length)];
  emit("change");
}

function onConnect(params) {
  edges.value = [...edges.value, { ...params, id: `e${Date.now()}` }];
  emit("change");
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

defineExpose({ serialize });
</script>

<style scoped>
.canvas-wrap { height: 100%; position: relative; }
</style>
