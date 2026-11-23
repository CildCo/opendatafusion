<template>
  <div class="property-editor">
    <div v-for="(row, index) in rows" :key="index" class="property-row">
      <el-select v-model="row.key" filterable allow-create
                 default-first-option size="small" style="width: 260px"
                 :placeholder="t('props.key')"
                 @change="(key) => onKey(row, key)">
        <el-option v-for="item in suggestions" :key="item.key"
                   :value="item.key" :label="item.key" />
      </el-select>
      <el-input v-model="row.value" size="small" style="width: 180px"
                :placeholder="t('props.value')" />
      <el-button link type="danger" size="small"
                 @click="remove(index)">{{ t("props.remove") }}</el-button>
    </div>
    <el-button link type="primary" size="small" @click="add">
      + {{ t("props.add") }}
    </el-button>
  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { t } from "../i18n";

const props = defineProps({
  modelValue: { type: Object, default: () => ({}) },
  suggestions: { type: Array, default: () => [] },
});
const emit = defineEmits(["update:modelValue"]);

const rows = ref(Object.entries(props.modelValue || {}).map(
  ([key, value]) => ({ key, value: String(value) })));

watch(rows, () => {
  emit("update:modelValue", Object.fromEntries(
    rows.value.filter((row) => row.key.trim())
      .map((row) => [row.key.trim(), row.value])));
}, { deep: true });

function onKey(row, key) {
  const match = props.suggestions.find((item) => item.key === key);
  if (match && !row.value) row.value = match.value;
}

function add() {
  rows.value.push({ key: "", value: "" });
}

function remove(index) {
  rows.value.splice(index, 1);
}
</script>

<style scoped>
.property-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
</style>
