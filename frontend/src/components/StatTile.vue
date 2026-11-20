<template>
  <div class="stat-tile" :class="tone">
    <div class="head">
      <entity-icon v-if="icon" :type="icon" :size="18" />
      <span class="label">{{ label }}</span>
    </div>
    <div class="body">
      <strong class="value">{{ value }}</strong>
      <span v-if="delta !== null && delta !== undefined" class="delta"
            :class="delta >= 0 ? 'up' : 'down'">
        {{ delta >= 0 ? "▲" : "▼" }} {{ Math.abs(delta) }}%
      </span>
    </div>
    <div class="foot">
      <span v-if="hint" class="hint">{{ hint }}</span>
      <sparkline v-if="values.length" :values="values" :tone="sparkTone"
                 :width="96" :height="26" />
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import EntityIcon from "./EntityIcon.vue";
import Sparkline from "./Sparkline.vue";

const props = defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], default: "-" },
  hint: { type: String, default: "" },
  delta: { type: Number, default: null },
  tone: { type: String, default: "" },
  icon: { type: String, default: "" },
  values: { type: Array, default: () => [] },
});

const sparkTone = computed(() => (
  { danger: "danger", warning: "warning", success: "success" }[props.tone]
  || "primary"));
</script>

<style scoped>
.stat-tile {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}
.head { display: flex; align-items: center; gap: 8px; }
.label { color: #64748b; font-size: 12px; letter-spacing: 0.02em; }
.body { display: flex; align-items: baseline; gap: 8px; }
.value { font-size: 26px; line-height: 1.1; color: #0f172a; }
.delta { font-size: 11px; }
.delta.up { color: #15803d; }
.delta.down { color: #b91c1c; }
.foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-height: 26px;
}
.hint { color: #94a3b8; font-size: 11px; }
.stat-tile.danger { border-color: #fecaca; }
.stat-tile.warning { border-color: #fde68a; }
.stat-tile.success { border-color: #bbf7d0; }
</style>
