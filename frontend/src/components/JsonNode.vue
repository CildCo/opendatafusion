<template>
  <div class="json-node">
    <details v-if="container" :open="depth < 2">
      <summary>
        <span v-if="name" class="key">{{ name }}</span>
        <span class="meta">{{ summary }}</span>
      </summary>
      <div class="children">
        <json-node v-for="(child, key) in entries" :key="key"
                   :name="String(key)" :value="child" :depth="depth + 1" />
      </div>
    </details>
    <div v-else class="leaf">
      <span v-if="name" class="key">{{ name }}</span>
      <span class="val" :class="kind">{{ display }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

defineOptions({ name: "JsonNode" });

const props = defineProps({
  name: { type: String, default: "" },
  value: { type: null, default: null },
  depth: { type: Number, default: 0 },
});

const container = computed(() => (
  props.value !== null && typeof props.value === "object"));

const entries = computed(() => {
  if (!container.value) return {};
  return Array.isArray(props.value) ? { ...props.value } : props.value;
});

const summary = computed(() => {
  if (Array.isArray(props.value)) return `[ ${props.value.length} ]`;
  const count = Object.keys(props.value || {}).length;
  return `{ ${count} }`;
});

const kind = computed(() => {
  if (props.value === null) return "null";
  return typeof props.value;
});

const display = computed(() => {
  if (props.value === null) return "null";
  if (typeof props.value === "string") return `"${props.value}"`;
  return String(props.value);
});
</script>

<style scoped>
.json-node { font-family: Consolas, "Courier New", monospace; font-size: 12px; }
details { margin: 1px 0; }
summary {
  cursor: pointer;
  color: #475569;
  padding: 1px 0;
  list-style: none;
}
summary::before {
  content: "▸";
  display: inline-block;
  width: 12px;
  color: #94a3b8;
  transition: transform 0.12s;
}
details[open] > summary::before { transform: rotate(90deg); }
.key { color: #475569; margin-right: 6px; }
.meta { color: #94a3b8; font-size: 11px; }
.children {
  margin-left: 14px;
  border-left: 1px dashed #e2e8f0;
  padding-left: 8px;
}
.leaf { padding: 1px 0 1px 12px; }
.val { word-break: break-all; }
.val.string { color: #047857; }
.val.number { color: #1d4ed8; }
.val.boolean { color: #b45309; }
.val.null { color: #94a3b8; }
</style>
