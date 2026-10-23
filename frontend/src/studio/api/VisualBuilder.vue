<template>
  <div class="visual">
    <el-form label-width="86px" size="small">
      <el-form-item label="数据源">
        <el-select v-model="q.datasource_id" style="width: 100%"
                   @change="loadTables(true)">
          <el-option v-for="d in datasources" :key="d.id" :value="d.id"
                     :label="d.name" />
        </el-select>
      </el-form-item>
      <el-form-item label="表">
        <el-select v-model="q.table" filterable style="width: 100%"
                   @change="pickTable">
          <el-option v-for="t in tables" :key="tableValue(t)"
                     :value="tableValue(t)" :label="tableValue(t)" />
        </el-select>
      </el-form-item>
    </el-form>

    <h4>字段</h4>
    <div v-for="(s, i) in q.select" :key="i" class="row">
      <el-select v-model="s.column" filterable style="width: 160px">
        <el-option v-for="c in columns" :key="c" :value="c" :label="c" />
        <el-option value="*" label="*" />
      </el-select>
      <el-select v-model="s.agg" clearable placeholder="聚合"
                 style="width: 100px">
        <el-option v-for="a in aggs" :key="a" :value="a" :label="a" />
      </el-select>
      <el-input v-model="s.as" placeholder="别名" style="width: 120px" />
      <el-button link type="danger" @click="q.select.splice(i, 1)">×</el-button>
    </div>
    <el-button link type="primary" @click="q.select.push({ column: '' })">
      + 字段
    </el-button>

    <h4>过滤</h4>
    <div v-for="(f, i) in q.filters" :key="i" class="row">
      <el-select v-model="f.column" filterable style="width: 140px">
        <el-option v-for="c in columns" :key="c" :value="c" :label="c" />
      </el-select>
      <el-select v-model="f.op" style="width: 110px">
        <el-option v-for="o in ops" :key="o" :value="o" :label="o" />
      </el-select>
      <el-input v-if="f.op === 'in'" :model-value="inText(f)"
                placeholder="用逗号分隔"
                style="width: 160px"
                @update:model-value="setIn(f, $event)" />
      <el-select v-else-if="!isNull(f.op)" v-model="f.param" clearable
                 placeholder="参数" style="width: 120px">
        <el-option v-for="p in params" :key="p.name" :value="p.name"
                   :label="p.name" />
      </el-select>
      <el-input v-if="!isNull(f.op) && !f.param"
                v-model="f.value" placeholder="固定值" style="width: 120px" />
      <el-button link type="danger" @click="q.filters.splice(i, 1)">×</el-button>
    </div>
    <el-button link type="primary"
               @click="q.filters.push({ column: '', op: '=', value: '' })">
      + 过滤
    </el-button>

    <h4>分组 / 排序 / 行数</h4>
    <el-select v-model="q.group_by" multiple filterable
               placeholder="分组字段" style="width: 100%">
      <el-option v-for="c in columns" :key="c" :value="c" :label="c" />
    </el-select>
    <div v-for="(o, i) in q.order_by" :key="i" class="row" style="margin-top: 8px">
      <el-select v-model="o.column" filterable style="width: 160px">
        <el-option v-for="c in orderColumns" :key="c" :value="c" :label="c" />
      </el-select>
      <el-select v-model="o.dir" style="width: 100px">
        <el-option value="asc" label="升序" />
        <el-option value="desc" label="降序" />
      </el-select>
      <el-button link type="danger" @click="q.order_by.splice(i, 1)">×</el-button>
    </div>
    <el-button link type="primary"
               @click="q.order_by.push({ column: '', dir: 'asc' })">
      + 排序
    </el-button>
    <el-form label-width="86px" size="small" style="margin-top: 12px">
      <el-form-item label="最大行数">
        <el-input-number v-model="q.limit" :min="1" :max="10000" />
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { api } from "../../api";

const props = defineProps({
  content: { type: Object, required: true },
  datasources: { type: Array, default: () => [] },
});
const q = computed(() => props.content.query);
const params = computed(() => props.content.params || []);
const tables = ref([]);
const columns = ref([]);
const aggs = ["sum", "count", "avg", "min", "max"];
const ops = ["=", "!=", ">", ">=", "<", "<=", "in", "like",
             "is null", "is not null"];

const orderColumns = computed(() => {
  const aliases = (q.value.select || []).map((s) => s.as).filter(Boolean);
  return [...new Set([...columns.value, ...aliases])];
});

function isNull(op) { return op === "is null" || op === "is not null"; }
function inText(f) {
  return Array.isArray(f.value) ? f.value.join(", ") : (f.value || "");
}
function setIn(f, text) {
  f.value = text.split(",").map((s) => s.trim()).filter(Boolean);
}
function tableValue(t) {
  return t.schema && t.schema !== "public" && t.schema !== "main"
    ? `${t.schema}.${t.table}` : t.table;
}

async function loadTables(clear = true) {
  if (clear) {
    q.value.table = "";
    columns.value = [];
  }
  if (!q.value.datasource_id) return;
  tables.value = await api.tablesOf(q.value.datasource_id);
  if (!clear) pickTable();
}

function pickTable() {
  const t = tables.value.find((x) => tableValue(x) === q.value.table
    || `${x.schema}.${x.table}` === q.value.table
    || x.table === q.value.table);
  columns.value = t ? (t.columns || []).map((c) => c.name) : [];
}

watch(() => q.value.datasource_id, (v) => { if (v) loadTables(false); },
      { immediate: true });
</script>

<style scoped>
.visual { padding: 12px; }
.row { display: flex; gap: 6px; margin-bottom: 6px; align-items: center; }
h4 { margin: 16px 6px 8px; font-size: 13px; color: #374151; }
</style>
