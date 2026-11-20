<template>
  <svg v-if="values.length > 1" :width="width" :height="height"
       :viewBox="`0 0 ${width} ${height}`" class="sparkline"
       role="img" aria-hidden="true">
    <defs>
      <linearGradient :id="gradientId" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" :stop-color="color" stop-opacity="0.28" />
        <stop offset="100%" :stop-color="color" stop-opacity="0" />
      </linearGradient>
    </defs>
    <path v-if="area" :d="areaPath" :fill="`url(#${gradientId})`" />
    <polyline :points="points" fill="none" :stroke="color"
              stroke-width="1.6" stroke-linejoin="round"
              stroke-linecap="round" />
  </svg>
  <svg v-else :width="width" :height="height"
       :viewBox="`0 0 ${width} ${height}`" class="sparkline empty"
       aria-hidden="true">
    <line :x1="2" :y1="height - 4" :x2="width - 2" :y2="height - 4"
          stroke="#e2e8f0" stroke-width="1" stroke-dasharray="3 3" />
  </svg>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  values: { type: Array, default: () => [] },
  width: { type: Number, default: 120 },
  height: { type: Number, default: 32 },
  tone: { type: String, default: "primary" },
  area: { type: Boolean, default: true },
});

const COLORS = {
  primary: "#1d4ed8",
  success: "#15803d",
  warning: "#b45309",
  danger: "#b91c1c",
  muted: "#64748b",
};
const color = computed(() => COLORS[props.tone] || COLORS.primary);
const gradientId = `spark-${Math.random().toString(36).slice(2, 9)}`;

const scaled = computed(() => {
  const numbers = props.values.map((v) => Number(v) || 0);
  if (!numbers.length) return [];
  const max = Math.max(...numbers);
  const min = Math.min(...numbers);
  const span = max - min || 1;
  const pad = 3;
  const width = props.width - pad * 2;
  const height = props.height - pad * 2;
  const step = numbers.length > 1 ? width / (numbers.length - 1) : width;
  return numbers.map((v, i) => [
    pad + i * step,
    pad + height - ((v - min) / span) * height,
  ]);
});

const points = computed(() =>
  scaled.value.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" "));

const areaPath = computed(() => {
  if (!scaled.value.length) return "";
  const bottom = props.height - 1;
  const first = scaled.value[0];
  const last = scaled.value[scaled.value.length - 1];
  return `M ${first[0].toFixed(1)} ${bottom} L ` +
    scaled.value.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`)
      .join(" L ") +
    ` L ${last[0].toFixed(1)} ${bottom} Z`;
});
</script>

<style scoped>
.sparkline { display: block; overflow: visible; }
</style>
