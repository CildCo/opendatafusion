<template>
  <el-dialog :model-value="modelValue" title="发布管道" width="420px"
             @update:model-value="$emit('update:modelValue', $event)">
    <p>发布后当前草稿将变成线上版本，并按 cron 进入调度。</p>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" @click="$emit('confirm')">确认发布</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
defineProps({ modelValue: Boolean });
defineEmits(["update:modelValue", "confirm"]);
</script>
