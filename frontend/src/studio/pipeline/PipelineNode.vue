<template>
  <div class="pipe-node" :class="[data.kind, statusClass]">
    <Handle v-if="data.kind !== 'source'" type="target"
            :position="Position.Left" />
    <div class="node-head">
      <span class="node-dot" />
      <b>{{ data.name }}</b>
    </div>
    <div class="node-meta">
      <span>{{ data.kind }}</span>
      <span v-if="runtime" class="node-runtime">
        {{ runtime.out_num || 0 }} rows · {{ runtime.ms || 0 }} ms
      </span>
    </div>
    <Handle v-if="data.kind !== 'sink'" type="source"
            :position="Position.Right" />
  </div>
</template>

<script setup>
import { computed } from "vue";
import { Handle, Position } from "@vue-flow/core";

const props = defineProps({
  data: { type: Object, required: true },
  selected: Boolean,
});

const runtime = computed(() => props.data.runtime || null);
const statusClass = computed(() => {
  const status = runtime.value?.status;
  return status ? `status-${status}` : "";
});
</script>

<style scoped>
.pipe-node {
  min-width: 150px;
  background: #fff;
  border: 1px solid #cbd5e1;
  border-left: 3px solid #2563eb;
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 12px;
  color: #0f172a;
  box-shadow: 0 1px 2px rgb(15 23 42 / 6%);
}
.pipe-node.source { border-left-color: #2563eb; }
.pipe-node.sink { border-left-color: #059669; }
.pipe-node.spark, .pipe-node.flink_sql { border-left-color: #ea580c; }
.pipe-node.status-success { border-color: #16a34a; }
.pipe-node.status-failed { border-color: #dc2626; }
.pipe-node.status-running { border-color: #d97706; }
.node-head { display: flex; align-items: center; gap: 6px; }
.node-head b { font-weight: 600; }
.node-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: #94a3b8; display: inline-block;
}
.status-success .node-dot { background: #16a34a; }
.status-failed .node-dot { background: #dc2626; }
.status-running .node-dot { background: #d97706; }
.status-queued .node-dot { background: #2563eb; }
.node-meta {
  display: flex; justify-content: space-between; gap: 8px;
  margin-top: 3px; color: #64748b; font-size: 11px;
}
.node-runtime { color: #475569; }
</style>
