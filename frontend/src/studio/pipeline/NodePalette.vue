<template>
  <div class="palette">
    <el-button v-for="(d, k) in defs" :key="k" size="small"
               @click="$emit('add', k)">{{ labelOf(k, d) }}</el-button>
  </div>
</template>

<script setup>
import { NODE_DEFS as defs } from "./nodes";
import { t } from "../../i18n";

defineEmits(["add"]);

const LABEL_KEYS = {
  source: "npal.source", filter: "npal.filter", select: "npal.select",
  rename: "npal.rename", cast: "npal.cast", join: "npal.join",
  aggregate: "npal.aggregate", union: "npal.union", dedupe: "npal.dedupe",
  quality: "npal.quality", spark: "npal.spark", flink_sql: "npal.flinkSql",
  sink: "npal.sink",
};

function labelOf(kind, def) {
  const key = LABEL_KEYS[kind];
  return key ? t(key) : def.label;
}
</script>

<style scoped>
.palette {
  position: absolute;
  z-index: 5;
  top: 10px;
  left: 10px;
  display: flex;
  gap: 6px;
  background: #fff;
  padding: 8px;
  border-radius: 0;
  border: 1px solid #e5e7eb;
  
}
</style>
