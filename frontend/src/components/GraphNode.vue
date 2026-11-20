<template>
  <div class="graph-node" :class="{ active }">
    <handle type="target" :position="Position.Left" />
    <entity-icon :type="data.type" :size="22" />
    <div class="text">
      <div class="name">{{ data.label }}</div>
      <div v-if="data.subtitle" class="sub">{{ data.subtitle }}</div>
    </div>
    <handle type="source" :position="Position.Right" />
  </div>
</template>

<script setup>
import { Handle, Position } from "@vue-flow/core";
import EntityIcon from "./EntityIcon.vue";

defineProps({
  data: { type: Object, default: () => ({}) },
  active: { type: Boolean, default: false },
});
</script>

<style scoped>
.graph-node {
  width: 190px;
  min-height: 52px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #fff;
  border: 1px solid #dbe3ee;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06);
  font-size: 12px;
  color: #0f172a;
}
.graph-node.active { border-color: #1d4ed8; box-shadow: 0 0 0 2px #eff4ff; }
.text { min-width: 0; }
.name {
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sub {
  color: #94a3b8;
  font-size: 11px;
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
