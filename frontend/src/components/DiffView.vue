<template>
  <div class="diff-view">
    <div v-for="change in changes" :key="change.key" class="diff-row">
      <div class="diff-key">{{ change.key }}</div>
      <div class="diff-pair">
        <div class="side before">{{ display(change.published) }}</div>
        <span class="arrow">→</span>
        <div class="side after">{{ display(change.draft) }}</div>
      </div>
    </div>
    <empty-state v-if="!changes.length" :title="emptyText" />
  </div>
</template>

<script setup>
import EmptyState from "./EmptyState.vue";

defineProps({
  changes: { type: Array, default: () => [] },
  emptyText: { type: String, default: "" },
});

function display(value) {
  if (value === null || value === undefined || value === "") return "∅";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
</script>

<style scoped>
.diff-view { display: flex; flex-direction: column; gap: 8px; }
.diff-row {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 8px 10px;
  background: #fff;
}
.diff-key {
  font-family: Consolas, "Courier New", monospace;
  font-size: 11px;
  color: #64748b;
  margin-bottom: 6px;
}
.diff-pair {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 8px;
  align-items: center;
}
.side {
  font-family: Consolas, "Courier New", monospace;
  font-size: 12px;
  padding: 6px 8px;
  border-radius: 6px;
  word-break: break-all;
}
.before { background: #fef2f2; color: #b91c1c; }
.after { background: #f0fdf4; color: #15803d; }
.arrow { color: #94a3b8; }
</style>
