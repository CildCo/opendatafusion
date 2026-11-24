<template>
  <div class="widget" :class="{ selected }" @click="$emit('select', widget)">
    <div class="head"
         @pointerdown="readonly ? null : $emit('drag-start', $event)">
      <span>{{ widget.title || widget.type }}</span>
      <span class="type">{{ widget.type }}</span>
    </div>
    <div class="body">
      <el-alert v-if="data && data.error" :title="data.error" type="error"
                :closable="false" />
      <template v-else-if="widget.type === 'text'">
        <div class="text">{{ data?.text || widget.text }}</div>
      </template>
      <template v-else-if="widget.type === 'card'">
        <div class="value" @click.stop="onCardClick">
          {{ cardValue }}
          <span v-if="cardDelta !== null" class="delta"
                :class="{ down: cardDelta < 0 }">
            {{ cardDelta > 0 ? "+" : "" }}{{ cardDelta }}%
          </span>
        </div>
      </template>
      <template v-else-if="widget.type === 'table'">
        <el-table :data="data?.rows || []" size="small" height="100%"
                  @row-click="onRowClick">
          <el-table-column v-for="c in data?.columns || []" :key="c"
                           :prop="c" :label="c" />
        </el-table>
      </template>
      <el-table v-else-if="widget.type === 'pivot'" :data="pivot.rows"
                size="small" height="100%">
        <el-table-column v-for="c in pivot.columns" :key="c"
                         :prop="c" :label="c" />
      </el-table>
      <ChartView v-else-if="chartOption" :option="chartOption"
                 @click="onChartClick" />
    </div>
    <div v-if="!readonly" class="resize"
         @pointerdown.stop="$emit('resize-start', $event)" />
  </div>
</template>

<script setup>
import { computed } from "vue";
import ChartView from "./ChartView.vue";
import { t } from "../../i18n";

const props = defineProps({
  widget: { type: Object, required: true },
  data: { type: Object, default: null },
  selected: Boolean,
  readonly: Boolean,
  drillable: Boolean,
});
const emit = defineEmits(["select", "drag-start", "resize-start", "filter",
                          "drill"]);

function emitFilter(value) {
  const e = props.widget.emit;
  if (!e || value === null || value === undefined) return;
  emit("filter", { param: e.param, value });
}
function onRowClick(row) {
  const e = props.widget.emit;
  if (e) emitFilter(row[e.from]);
  if (!props.drillable || !props.widget.metric_id) return;
  const dimension = props.widget.drill_dimension || e?.from || null;
  if (!dimension) return;
  emit("drill", { widget: props.widget, dimension,
                  value: row[dimension] });
}
function onChartClick(p) {
  emitFilter(p?.name);
  if (!props.drillable || !props.widget.metric_id
      || !props.widget.dimension) return;
  if (p?.seriesName === t("dash.previous")) return;
  emit("drill", { widget: props.widget, dimension: props.widget.dimension,
                  value: p?.name });
}

function onCardClick() {
  if (!props.drillable || !props.widget.metric_id) return;
  emit("drill", { widget: props.widget, dimension: null, value: null });
}

const cardValue = computed(() => {
  const row = (props.data?.rows || [])[0] || {};
  const cols = props.data?.columns || [];
  const col = props.widget.value_column || cols[cols.length - 1] || "value";
  return row[col] ?? "-";
});

const cardDelta = computed(() => {
  const row = (props.data?.rows || [])[0] || {};
  const cols = props.data?.columns || [];
  const col = props.widget.value_column || cols[cols.length - 1] || "value";
  const value = row[`${col}_delta_pct`];
  return typeof value === "number" ? value : null;
});

const pivot = computed(() => {
  const rows = props.data?.rows || [];
  const rowDim = props.widget.row_dimension;
  const colDim = props.widget.column_dimension;
  const cols = props.data?.columns || [];
  const value = props.widget.value_column
    || cols[cols.length - 1] || "value";
  if (!rowDim || !colDim || !rows.length) {
    return { rows: [], columns: [] };
  }
  const colValues = [];
  for (const row of rows) {
    if (!colValues.includes(row[colDim])) colValues.push(row[colDim]);
  }
  const map = new Map();
  for (const row of rows) {
    const key = row[rowDim];
    if (!map.has(key)) {
      const item = { [rowDim]: key };
      for (const c of colValues) item[c] = null;
      map.set(key, item);
    }
    map.get(key)[row[colDim]] = row[value];
  }
  return { rows: [...map.values()], columns: [rowDim, ...colValues] };
});

const chartOption = computed(() => {
  const rows = props.data?.rows || [];
  const dim = props.widget.dimension;
  const cols = props.data?.columns || [];
  const val = props.widget.value_column || cols[cols.length - 1] || "value";
  if (!dim || !rows.length) return null;
  const labels = rows.map((r) => r[dim]);
  const values = rows.map((r) => r[val]);
  if (props.widget.type === "pie") {
    return {
      tooltip: { trigger: "item" },
      series: [{
        type: "pie", radius: "65%",
        data: rows.map((r) => ({ name: r[dim], value: r[val] })),
      }],
    };
  }
  const series = {
    name: t("dash.current"),
    type: props.widget.type === "area" ? "line" : props.widget.type,
    data: values, smooth: true,
  };
  if (props.widget.type === "area") series.areaStyle = {};
  const previousKey = `${val}_previous`;
  const hasPrevious = rows.some(
    (r) => r[previousKey] !== null && r[previousKey] !== undefined);
  const allSeries = [series];
  if (hasPrevious) {
    allSeries.push({
      name: t("dash.previous"),
      type: props.widget.type === "area" ? "line" : props.widget.type,
      data: rows.map((r) => r[previousKey]),
      smooth: true,
      lineStyle: { type: "dashed" },
      itemStyle: { opacity: 0.7 },
      areaStyle: props.widget.type === "area" ? { opacity: 0.15 } : undefined,
    });
  }
  return {
    tooltip: { trigger: "axis" },
    legend: hasPrevious ? {} : undefined,
    grid: { left: 40, right: 16, top: hasPrevious ? 44 : 24, bottom: 28 },
    xAxis: { type: "category", data: labels },
    yAxis: { type: "value" },
    series: allSeries,
  };
});
</script>

<style scoped>
.widget { position: absolute; background: #fff; border: 1px solid #e5e7eb;
          border-radius: 0; overflow: hidden; display: flex;
          flex-direction: column; }
.widget.selected { border-color: #3b82f6; outline: 2px solid var(--odf-accent); outline-offset: -2px; }
.head { display: flex; justify-content: space-between; padding: 8px 10px;
        font-size: 13px; font-weight: 600; cursor: move; background: #f8fafc;
        border-bottom: 1px solid #e5e7eb; touch-action: none; }
.type { color: #6b7280; font-weight: 400; font-size: 11px; }
.body { flex: 1; min-height: 0; overflow: hidden; padding: 6px; }
.value { font-size: 32px; font-weight: 700; padding: 12px; color: #0f172a; }
.delta { font-size: 13px; font-weight: 600; margin-left: 8px; color: #15803d; }
.delta.down { color: #b91c1c; }
.text { padding: 10px; font-size: 13px; color: #334155; white-space: pre-wrap; }
.resize { position: absolute; right: 0; bottom: 0; width: 14px; height: 14px;
          cursor: nwse-resize; touch-action: none;
          background: linear-gradient(135deg, transparent 50%, #6b7280 50%); }
</style>
