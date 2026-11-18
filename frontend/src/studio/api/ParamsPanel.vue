<template>
  <div class="params">
    <div class="head">
      <span>{{ t("apic.params") }}</span>
      <el-button link type="primary" @click="params.push(newParam())">
        {{ t("apic.addParam") }}
      </el-button>
    </div>
    <div v-for="(p, i) in params" :key="i" class="param">
      <el-input v-model="p.name" :placeholder="t('apic.namePlaceholder')" size="small" />
      <el-select v-model="p.type" size="small" style="width: 92px">
        <el-option value="string" :label="t('apic.typeString')" />
        <el-option value="number" :label="t('apic.typeNumber')" />
        <el-option value="date" :label="t('apic.typeDate')" />
        <el-option value="bool" :label="t('apic.typeBool')" />
      </el-select>
      <el-checkbox v-model="p.required" size="small">{{ t("apic.required") }}</el-checkbox>
      <el-input v-model="p.default" :placeholder="t('apic.defaultValue')" size="small" />
      <el-input v-model="p.example" :placeholder="t('apic.example')" size="small" />
      <el-button link type="danger" @click="params.splice(i, 1)">×</el-button>
    </div>
    <el-empty v-if="!params.length" :description="t('apic.noParams')" :image-size="50" />
  </div>
</template>

<script setup>
import { t } from "../../i18n";

defineProps({ params: { type: Array, required: true } });
function newParam() {
  return { name: "", type: "string", required: false,
           default: null, example: "" };
}
</script>

<style scoped>
.params { padding: 10px; }
.head { display: flex; justify-content: space-between; align-items: center;
        font-weight: 600; font-size: 13px; margin-bottom: 8px; }
.param { display: grid; grid-template-columns: 1fr 92px 58px 1fr 1fr 20px;
         gap: 4px; margin-bottom: 6px; align-items: center; }
</style>
