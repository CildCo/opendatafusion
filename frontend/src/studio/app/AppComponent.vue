<template>
  <div class="app-component" :class="`type-${component.type}`">
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <template v-else-if="component.type === 'form'">
      <AppForm :component="component" :on-submit="onSubmit" />
    </template>
    <div v-else-if="component.type === 'heading'" class="heading">
      {{ text }}
    </div>
    <div v-else-if="component.type === 'text'" class="text">{{ text }}</div>
    <el-divider v-else-if="component.type === 'divider'" />
    <el-image v-else-if="component.type === 'image'" :src="component.url"
              :alt="component.alt || ''" fit="cover" class="image">
      <template #error>
        <div class="image-fallback">{{ component.alt || component.url }}</div>
      </template>
    </el-image>
    <el-button v-else-if="component.type === 'button'" type="primary"
               @click="act">
      {{ label }}
    </el-button>
    <el-progress v-else-if="component.type === 'progress'"
                 :percentage="percentage" :stroke-width="14"
                 :status="percentage >= 100 ? 'success' : ''" />
    <div v-else-if="component.type === 'metric'" class="value">
      {{ metricValue() }}
    </div>
    <template v-else-if="component.type === 'table'">
      <el-table :data="entry?.rows || []" size="small" border stripe
                @row-click="$emit('row', $event)">
        <el-table-column v-for="col in tableColumns()" :key="col" :prop="col"
                         :label="col" min-width="110"
                         show-overflow-tooltip />
      </el-table>
      <div class="count">
        {{ t("acomp.total") }} {{ entry?.row_count || 0 }}
        {{ t("acomp.rows") }}
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { t } from "../../i18n";
import AppForm from "./AppForm.vue";
import { interpolate, progressValue } from "./bindings";

const props = defineProps({
  component: { type: Object, required: true },
  entry: { type: Object, default: null },
  params: { type: Object, default: () => ({}) },
  onSubmit: { type: Function, default: null },
  design: Boolean,
});
const emit = defineEmits(["navigate", "row"]);

const error = computed(() => props.entry?.error || "");
const text = computed(() => interpolate(
  props.component.text ?? props.entry?.text ?? "",
  props.params, { keepMissing: props.design }));
const label = computed(() => interpolate(
  props.component.label || props.component.text || t("acomp.open"),
  props.params, { keepMissing: props.design }));
const percentage = computed(() =>
  progressValue(props.component, props.params));

function metricValue() {
  const row = props.entry?.rows?.[0] || {};
  const cols = props.entry?.columns || [];
  const col = props.component.value_column || cols[cols.length - 1]
    || "value";
  const value = row[col];
  if (value === null || value === undefined) return "-";
  return typeof value === "number"
    ? value.toLocaleString("zh-CN") : value;
}

function tableColumns() {
  return props.component.columns?.length ? props.component.columns
    : (props.entry?.columns || []);
}

function act() {
  if (props.design) return;
  if (props.component.target_page) {
    emit("navigate", props.component.target_page);
  } else if (props.component.url) {
    window.open(props.component.url, "_blank", "noopener,noreferrer");
  }
}
</script>

<style scoped>
.app-component { min-height: 20px; }
.heading { font-size: 22px; font-weight: 700; color: #0f172a;
           line-height: 1.35; }
.text { font-size: 13px; color: #334155; white-space: pre-wrap;
        line-height: 1.65; }
.value { font-size: 30px; font-weight: 700; color: #0f172a; }
.count { font-size: 11px; color: #6b7280; margin-top: 6px; }
.image { width: 100%; height: 100%; min-height: 80px; border-radius: 4px;
         background: #f1f5f9; }
.image-fallback { display: flex; align-items: center; justify-content: center;
                  height: 100%; min-height: 80px; padding: 8px;
                  font-size: 12px; color: #64748b; }
</style>
