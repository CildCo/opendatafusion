<template>
  <div v-if="params?.length" class="param-bar">
    <div v-for="p in params" :key="p.name" class="param">
      <span>{{ p.name }}</span>
      <el-date-picker v-if="p.type === 'date'" :model-value="value[p.name]"
                      type="date" size="small" value-format="YYYY-MM-DD"
                      style="width: 150px"
                      @update:model-value="set(p.name, $event)" />
      <el-input-number v-else-if="p.type === 'number'"
                       :model-value="numberValue(p.name)" size="small"
                       :controls="false" style="width: 120px"
                       @update:model-value="set(p.name, $event)" />
      <el-select v-else-if="p.type === 'bool'" :model-value="value[p.name]"
                 size="small" style="width: 110px"
                 @update:model-value="set(p.name, $event)">
        <el-option :label="t('acomp.all')" :value="''" />
        <el-option :label="t('acomp.yes')" :value="true" />
        <el-option :label="t('acomp.no')" :value="false" />
      </el-select>
      <el-input v-else :model-value="value[p.name]" size="small"
                style="width: 150px" :placeholder="p.example || p.type"
                @update:model-value="set(p.name, $event)" />
    </div>
    <el-button type="primary" size="small" @click="$emit('refresh')">
      {{ t("acomp.query") }}
    </el-button>
    <el-button v-if="resettable" size="small" @click="$emit('reset')">
      {{ t("common.reset") }}
    </el-button>
  </div>
</template>

<script setup>
import { t } from "../../i18n";

const props = defineProps({
  params: { type: Array, default: () => [] },
  value: { type: Object, default: () => ({}) },
  resettable: Boolean,
});
const emit = defineEmits(["update:value", "refresh", "reset"]);

function set(name, next) {
  emit("update:value", { ...props.value, [name]: next });
}

function numberValue(name) {
  const raw = props.value[name];
  if (raw === "" || raw === null || raw === undefined) return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}
</script>

<style scoped>
.param-bar { display: flex; gap: 10px; align-items: flex-end;
             flex-wrap: wrap; margin-bottom: 12px; padding: 8px 10px;
             background: #fff; border: 1px solid #e5e7eb; }
.param { display: flex; flex-direction: column; gap: 3px;
         font-size: 12px; color: #475569; }
</style>
