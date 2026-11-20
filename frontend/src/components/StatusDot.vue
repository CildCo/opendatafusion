<template>
  <span class="status-dot" :class="tone" :title="label || status">
    <i class="dot" />
    <span v-if="label !== ''" class="text">{{ label ?? status }}</span>
  </span>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  status: { type: [String, Number, Boolean], default: "" },
  label: { type: String, default: null },
  tone: { type: String, default: "" },
});

const TONES = {
  success: ["success", "pass", "passed", "ok", "running", "enabled",
            "active", "applied", "published", "1", "true", "running",
            "completed", "finished", "ready"],
  warning: ["pending", "queued", "acked", "paused", "waiting", "warning",
            "scheduled", "retrying", "in_progress"],
  danger: ["failed", "fail", "error", "critical", "rejected", "cancelled",
           "canceled", "timeout", "skipped"],
  info: ["closed", "disabled", "withdrawn", "unknown", "idle", "0", "false",
         "draft", "stopped"],
};

const tone = computed(() => {
  if (props.tone) return props.tone;
  const value = String(props.status).toLowerCase();
  for (const [name, values] of Object.entries(TONES)) {
    if (values.includes(value)) return name;
  }
  return "info";
});
</script>

<style scoped>
.status-dot {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #475569;
  line-height: 1;
}
.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #94a3b8;
  flex: none;
}
.success .dot { background: #15803d; }
.warning .dot { background: #b45309; }
.danger .dot { background: #b91c1c; }
.info .dot { background: #94a3b8; }
.status-dot.success .text { color: #15803d; }
.status-dot.warning .text { color: #b45309; }
.status-dot.danger .text { color: #b91c1c; }
</style>
