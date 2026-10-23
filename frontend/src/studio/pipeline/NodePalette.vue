<template>
  <div class="palette">
    <el-button v-for="(d, k) in defs" :key="k" size="small"
               @click="$emit('add', k)">{{ d.label }}</el-button>
  </div>
</template>

<script setup>
import { NODE_DEFS as defs } from "./nodes";
defineEmits(["add"]);
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
