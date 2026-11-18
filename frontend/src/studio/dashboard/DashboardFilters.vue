<template>
  <div v-if="params?.length" class="filters">
    <div v-for="p in params" :key="p.name" class="filter">
      <span>{{ p.name }}</span>
      <el-select v-if="p.type === 'bool'" :model-value="value[p.name]"
                 size="small" style="width: 110px"
                 @update:model-value="set(p.name, $event)">
        <el-option :label="t('dcomp.all')" :value="''" />
        <el-option :label="t('dcomp.yes')" :value="true" />
        <el-option :label="t('dcomp.no')" :value="false" />
      </el-select>
      <el-input v-else :model-value="value[p.name]" size="small"
                style="width: 150px"
                :placeholder="p.example || p.type || t('dcomp.all')"
                @update:model-value="set(p.name, $event)" />
    </div>
    <el-button type="primary" size="small" @click="$emit('refresh')">
      {{ t("dcomp.query") }}
    </el-button>
  </div>
</template>

<script setup>
import { t } from "../../i18n";

const props = defineProps({
  params: { type: Array, default: () => [] },
  value: { type: Object, default: () => ({}) },
});
const emit = defineEmits(["update:value", "refresh"]);

function set(name, v) {
  emit("update:value", { ...props.value, [name]: v });
}
</script>

<style scoped>
.filters { display: flex; gap: 10px; align-items: flex-end; flex-wrap: wrap;
           margin-bottom: 10px; padding: 8px 10px; background: #fff;
           border: 1px solid #e5e7eb; border-radius: 0; }
.filter { display: flex; flex-direction: column; gap: 3px;
          font-size: 12px; color: #475569; }
</style>
