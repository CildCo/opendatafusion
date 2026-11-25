<template>
  <span class="history-controls">
    <el-button size="small" :disabled="!canUndo" @click="$emit('undo')"
               :aria-label="t('history.undo')"
               :title="t('history.undo')">↶</el-button>
    <el-button size="small" :disabled="!canRedo" @click="$emit('redo')"
               :aria-label="t('history.redo')"
               :title="t('history.redo')">↷</el-button>
  </span>
</template>

<script setup>
import { t } from "../i18n";

defineProps({ canUndo: Boolean, canRedo: Boolean });
defineEmits(["undo", "redo"]);
</script>

<style scoped>
.history-controls { display: inline-flex; gap: 2px; }
</style>
