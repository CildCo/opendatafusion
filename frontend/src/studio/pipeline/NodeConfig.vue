<template>
  <div v-if="node" class="config">
    <h4>{{ node.data.name }}</h4>
    <el-input v-model="node.data.name" size="small" @change="$emit('update')" />
    <el-divider />

    <template v-if="node.data.kind === 'source'">
      <el-form label-width="70px" size="small">
        <el-form-item label="数据源">
          <el-select v-model="cfg.datasource_id" style="width: 100%"
                     @change="loadTables(true)">
            <el-option v-for="d in datasources" :key="d.id" :value="d.id"
                       :label="d.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="表">
          <el-select v-model="cfg.table" filterable style="width: 100%"
                     @change="onTable">
            <el-option v-for="t in tables" :key="t.table"
                       :value="t.table" :label="`${t.schema}.${t.table}`" />
          </el-select>
        </el-form-item>
        <el-form-item label="主键">
          <el-select v-model="cfg.pk" filterable allow-create style="width: 100%">
            <el-option v-for="c in columns" :key="c.name" :value="c.name"
                       :label="c.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="增量列">
          <el-select v-model="cfg.cursor_column" clearable filterable
                     allow-create style="width: 100%">
            <el-option v-for="c in columns" :key="c.name" :value="c.name"
                       :label="c.name" />
          </el-select>
        </el-form-item>
      </el-form>
    </template>

    <template v-else-if="node.data.kind === 'filter'">
      <div v-for="(c, i) in cfg.conditions" :key="i" class="row">
        <el-input v-model="c.column" size="small" placeholder="列" />
        <el-select v-model="c.op" size="small" style="width: 80px">
          <el-option v-for="op in ['>','>=','<','<=','=','!=']" :key="op"
                     :value="op" :label="op" />
        </el-select>
        <el-input v-model="c.value" size="small" placeholder="值" />
        <el-button link type="danger"
                   @click="cfg.conditions.splice(i, 1)">×</el-button>
      </div>
      <el-button link type="primary"
                 @click="cfg.conditions.push({ column: '', op: '=', value: '' })">
        + 条件
      </el-button>
    </template>

    <template v-else-if="node.data.kind === 'select'">
      <div v-for="(c, i) in cfg.columns" :key="i" class="row">
        <el-input v-model="c.column" size="small" placeholder="列" />
        <el-input v-model="c.as" size="small" placeholder="别名" />
        <el-button link type="danger"
                   @click="cfg.columns.splice(i, 1)">×</el-button>
      </div>
      <el-button link type="primary"
                 @click="cfg.columns.push({ column: '', as: '' })">+ 列</el-button>
    </template>

    <template v-else-if="node.data.kind === 'rename'">
      <div v-for="(c, i) in cfg.pairs" :key="i" class="row">
        <el-input v-model="c.from" size="small" placeholder="原名" />
        <el-input v-model="c.to" size="small" placeholder="新名" />
        <el-button link type="danger"
                   @click="cfg.pairs.splice(i, 1)">×</el-button>
      </div>
      <el-button link type="primary"
                 @click="cfg.pairs.push({ from: '', to: '' })">+ 重命名</el-button>
    </template>

    <template v-else-if="node.data.kind === 'cast'">
      <div v-for="(c, i) in cfg.pairs" :key="i" class="row">
        <el-input v-model="c.column" size="small" placeholder="列" />
        <el-select v-model="c.type" size="small" style="width: 110px">
          <el-option value="text" label="文本" />
          <el-option value="int" label="整数" />
          <el-option value="float" label="小数" />
          <el-option value="bool" label="布尔" />
        </el-select>
        <el-button link type="danger"
                   @click="cfg.pairs.splice(i, 1)">×</el-button>
      </div>
      <el-button link type="primary"
                 @click="cfg.pairs.push({ column: '', type: 'text' })">+ 转换</el-button>
    </template>

    <template v-else-if="node.data.kind === 'join'">
      <el-form label-width="70px" size="small">
        <el-form-item label="连接类型">
          <el-select v-model="cfg.how" style="width: 100%">
            <el-option value="inner" label="inner" />
            <el-option value="left" label="left" />
            <el-option value="right" label="right" />
            <el-option value="full" label="full" />
          </el-select>
        </el-form-item>
        <el-form-item label="后缀">
          <el-input v-model="cfg.suffix" placeholder="_right" />
        </el-form-item>
      </el-form>
      <div v-for="(p, i) in cfg.on" :key="i" class="row">
        <el-input v-model="p.left" placeholder="左键" />
        <el-input v-model="p.right" placeholder="右键" />
        <el-button link type="danger" @click="cfg.on.splice(i, 1)">×</el-button>
      </div>
      <el-button link type="primary"
                 @click="cfg.on.push({ left: '', right: '' })">+ 关联键</el-button>
    </template>

    <template v-else-if="node.data.kind === 'aggregate'">
      <el-select v-model="cfg.group_by" multiple filterable allow-create
                 placeholder="分组列" style="width: 100%" />
      <div v-for="(a, i) in cfg.aggregates" :key="i" class="row">
        <el-input v-model="a.column" placeholder="列" />
        <el-select v-model="a.agg" style="width: 100px">
          <el-option v-for="x in ['sum','count','avg','min','max']"
                     :key="x" :value="x" :label="x" />
        </el-select>
        <el-input v-model="a.as" placeholder="别名" />
        <el-button link type="danger"
                   @click="cfg.aggregates.splice(i, 1)">×</el-button>
      </div>
      <el-button link type="primary"
                 @click="cfg.aggregates.push({ column: '', agg: 'sum', as: '' })">
        + 聚合
      </el-button>
    </template>

    <template v-else-if="node.data.kind === 'union'">
      <el-checkbox v-model="cfg.all">UNION ALL</el-checkbox>
      <div v-for="(c, i) in cfg.columns" :key="i" class="row">
        <el-input v-model="c.name" placeholder="输出列" />
        <el-input v-model="c.left" placeholder="左列" />
        <el-input v-model="c.right" placeholder="右列" />
        <el-button link type="danger"
                   @click="cfg.columns.splice(i, 1)">×</el-button>
      </div>
      <el-button link type="primary"
                 @click="cfg.columns.push({ name: '', left: '', right: '' })">
        + 列对齐
      </el-button>
    </template>

    <template v-else-if="node.data.kind === 'dedupe'">
      <el-select v-model="cfg.keys" multiple filterable allow-create
                 placeholder="去重键" style="width: 100%" />
      <el-form label-width="70px" size="small" style="margin-top: 8px">
        <el-form-item label="保留">
          <el-select v-model="cfg.keep" style="width: 100%">
            <el-option value="first" label="first" />
            <el-option value="last" label="last" />
          </el-select>
        </el-form-item>
        <el-form-item label="排序列">
          <el-input v-model="cfg.order_by.column" placeholder="可选" />
        </el-form-item>
        <el-form-item label="方向">
          <el-select v-model="cfg.order_by.dir" style="width: 100%">
            <el-option value="asc" label="asc" />
            <el-option value="desc" label="desc" />
          </el-select>
        </el-form-item>
      </el-form>
    </template>

    <template v-else-if="node.data.kind === 'quality'">
      <div v-for="(r, i) in cfg.rules" :key="i" class="row">
        <el-input v-model="r.column" placeholder="列" />
        <el-select v-model="r.op" style="width: 80px">
          <el-option v-for="op in ['>','>=','<','<=','=','!=']" :key="op"
                     :value="op" :label="op" />
        </el-select>
        <el-input v-model="r.value" placeholder="值" />
        <el-button link type="danger" @click="cfg.rules.splice(i, 1)">×</el-button>
      </div>
      <el-button link type="primary"
                 @click="cfg.rules.push({ column: '', op: '>', value: '' })">
        + 规则
      </el-button>
      <el-form label-width="70px" size="small" style="margin-top: 8px">
        <el-form-item label="失败策略">
          <el-select v-model="cfg.on_fail" style="width: 100%">
            <el-option value="fail" label="fail" />
            <el-option value="quarantine" label="quarantine" />
          </el-select>
        </el-form-item>
      </el-form>
    </template>

    <template v-else-if="node.data.kind === 'sink'">
      <el-form label-width="70px" size="small">
        <el-form-item label="数据源">
          <el-select v-model="cfg.datasource_id" style="width: 100%"
                     @change="loadTables(true)">
            <el-option v-for="d in datasources" :key="d.id" :value="d.id"
                       :label="d.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="表">
          <el-select v-model="cfg.table" filterable style="width: 100%"
                     @change="onTable">
            <el-option v-for="t in tables" :key="t.table"
                       :value="t.table" :label="`${t.schema}.${t.table}`" />
          </el-select>
        </el-form-item>
        <el-form-item label="模式">
          <el-select v-model="cfg.mode" style="width: 100%">
            <el-option value="upsert" label="upsert" />
            <el-option value="append" label="append" />
          </el-select>
        </el-form-item>
        <el-form-item label="主键">
          <el-select v-model="cfg.pk" multiple filterable allow-create
                     style="width: 100%">
            <el-option v-for="c in columns" :key="c.name" :value="c.name"
                       :label="c.name" />
          </el-select>
        </el-form-item>
      </el-form>
    </template>

    <el-divider />
    <el-form label-width="70px" size="small">
      <el-form-item label="出错策略">
        <el-select v-model="cfg.on_error" clearable style="width: 100%">
          <el-option value="fail" label="fail" />
          <el-option value="skip" label="skip" />
          <el-option value="quarantine" label="quarantine" />
        </el-select>
      </el-form-item>
    </el-form>
  </div>
  <el-empty v-else description="选择画布上的节点进行配置" />
</template>

<script setup>
import { ref, watch } from "vue";
import { api } from "../../api";

const props = defineProps({
  node: { type: Object, default: null },
  datasources: { type: Array, default: () => [] },
});
const emit = defineEmits(["update"]);
const tables = ref([]);
const columns = ref([]);
const cfg = ref({});

function reset() {
  if (!props.node) {
    cfg.value = {};
    tables.value = [];
    columns.value = [];
    return;
  }
  const kind = props.node.data.kind;
  const c = JSON.parse(JSON.stringify(props.node.data.config || {}));
  if (kind === "filter") c.conditions = c.conditions || [];
  if (kind === "select") c.columns = c.columns || [];
  if (kind === "rename") {
    c.pairs = Object.entries(c.mapping || {}).map(([from, to]) => ({ from, to }));
  }
  if (kind === "cast") {
    c.pairs = Object.entries(c.mapping || {})
      .map(([column, type]) => ({ column, type }));
  }
  if (kind === "sink" && !Array.isArray(c.pk)) {
    c.pk = c.pk ? [c.pk] : ["id"];
  }
  if (kind === "join") c.on = c.on || [];
  if (kind === "aggregate") {
    c.group_by = c.group_by || [];
    c.aggregates = c.aggregates || [];
  }
  if (kind === "union") {
    c.columns = c.columns || [];
    if (c.all === undefined) c.all = true;
  }
  if (kind === "dedupe") {
    c.keys = c.keys || [];
    c.keep = c.keep || "first";
    c.order_by = c.order_by || { column: "", dir: "asc" };
  }
  if (kind === "quality") {
    c.rules = c.rules || [];
    c.on_fail = c.on_fail || "fail";
  }
  cfg.value = c;
  props.node.data.config = cfg.value;
  if ((kind === "source" || kind === "sink") && cfg.value.datasource_id) {
    loadTables(false);
  } else {
    tables.value = [];
    columns.value = [];
  }
}
watch(() => props.node && props.node.id, reset, { immediate: true });

async function loadTables(clear = true) {
  if (!cfg.value.datasource_id) return;
  tables.value = await api.tablesOf(cfg.value.datasource_id);
  if (clear) {
    cfg.value.table = "";
    columns.value = [];
  } else {
    const t = tables.value.find((x) => x.table === cfg.value.table);
    columns.value = t ? t.columns || [] : [];
  }
  emit("update");
}

function onTable(name) {
  const t = tables.value.find((x) => x.table === name);
  columns.value = t ? t.columns || [] : [];
  emit("update");
}
</script>

<style scoped>
.config { padding: 12px; }
.row { display: flex; gap: 6px; margin-bottom: 6px; align-items: center; }
</style>
