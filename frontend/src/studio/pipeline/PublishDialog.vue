<template>
  <el-dialog :model-value="modelValue" :title="t('ppub.title')" width="420px"
             @update:model-value="$emit('update:modelValue', $event)">
    <p>{{ t("ppub.hint") }}</p>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">{{ t("ppub.cancel") }}</el-button>
      <el-button type="primary" @click="$emit('confirm')">{{ t("ppub.confirm") }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { t } from "../../i18n";

defineProps({ modelValue: Boolean });
defineEmits(["update:modelValue", "confirm"]);
</script>
