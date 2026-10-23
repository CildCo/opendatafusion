<template>
  <div class="runtime">
    <h3 v-if="page.title">{{ page.title }}</h3>
    <div v-if="page.params?.length" class="filters">
      <div v-for="p in page.params" :key="p.name" class="filter">
        <span>{{ p.name }}</span>
        <el-select v-if="p.type === 'bool'" v-model="values[p.name]"
                   size="small" style="width: 110px"
                   @change="$emit('update:params', { ...values })">
          <el-option label="全部" :value="''" />
          <el-option label="是" :value="true" />
          <el-option label="否" :value="false" />
        </el-select>
        <el-input v-else v-model="values[p.name]" size="small"
                  style="width: 150px"
                  :placeholder="p.example || p.type"
                  @change="$emit('update:params', { ...values })" />
      </div>
      <el-button type="primary" size="small" @click="$emit('refresh')">
        查询
      </el-button>
    </div>
    <div v-for="c in page.components" :key="c.id" class="component">
      <div class="title">{{ c.title || c.type }}</div>
      <el-alert v-if="data?.[c.id]?.error" :title="data[c.id].error"
                type="error" :closable="false" />
      <template v-else-if="c.type === 'form'">
        <AppForm :component="c" :on-submit="onSubmit" />
      </template>
      <template v-else-if="c.type === 'text'">
        <div class="text">{{ data?.[c.id]?.text ?? c.text }}</div>
      </template>
      <template v-else-if="c.type === 'metric'">
        <div class="value">{{ metricValue(c) }}</div>
      </template>
      <template v-else-if="c.type === 'table'">
        <el-table :data="data?.[c.id]?.rows || []" size="small"
                  border stripe @row-click="openDetail">
          <el-table-column v-for="col in tableColumns(c)" :key="col"
                           :prop="col" :label="col" min-width="110"
                           show-overflow-tooltip />
        </el-table>
        <div class="count">共 {{ data?.[c.id]?.row_count || 0 }} 行</div>
      </template>
    </div>
    <el-empty v-if="!page.components?.length"
              description="还没有组件，从左侧添加" />
    <el-drawer v-model="detailOpen" title="详情" size="420px">
      <el-descriptions :column="1" border>
        <el-descriptions-item v-for="(v, k) in detailRow" :key="k"
                              :label="k">{{ v }}</el-descriptions-item>
      </el-descriptions>
    </el-drawer>
  </div>
</template>

<script setup>
import { reactive, ref, watch } from "vue";
import AppForm from "./AppForm.vue";

const props = defineProps({
  page: { type: Object, required: true },
  data: { type: Object, default: () => ({}) },
  params: { type: Object, default: () => ({}) },
  onSubmit: { type: Function, default: null },
});
defineEmits(["update:params", "refresh"]);
const values = reactive({ ...props.params });
const detailOpen = ref(false);
const detailRow = ref({});

watch(() => props.params, (next) => {
  Object.keys(values).forEach((k) => delete values[k]);
  Object.assign(values, next || {});
}, { deep: true });

function metricValue(c) {
  const d = props.data?.[c.id];
  const row = d?.rows?.[0] || {};
  const cols = d?.columns || [];
  const col = c.value_column || cols[cols.length - 1] || "value";
  const value = row[col];
  if (value === null || value === undefined) return "-";
  return typeof value === "number"
    ? value.toLocaleString("zh-CN") : value;
}
function tableColumns(c) {
  return c.columns?.length ? c.columns
    : (props.data?.[c.id]?.columns || []);
}
function openDetail(row) {
  detailRow.value = row;
  detailOpen.value = true;
}
</script>

<style scoped>
.runtime { padding: 4px; }
.filters { display: flex; gap: 10px; align-items: flex-end; flex-wrap: wrap;
           margin-bottom: 14px; padding: 10px; background: #f8fafc;
           border: 1px solid #e5e7eb; border-radius: 0; }
.filter { display: flex; flex-direction: column; gap: 4px;
          font-size: 12px; color: #475569; }
.component { background: #fff; border: 1px solid #e5e7eb;
             border-radius: 0; padding: 12px; margin-bottom: 12px; }
.title { font-weight: 600; font-size: 13px; margin-bottom: 8px;
         color: #0f172a; }
.value { font-size: 30px; font-weight: 700; color: #0f172a; }
.text { font-size: 13px; color: #334155; white-space: pre-wrap; }
.count { font-size: 11px; color: #6b7280; margin-top: 6px; }
</style>
