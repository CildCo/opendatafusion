<template>
  <div class="page-header">
    <entity-icon v-if="icon" :type="icon" :size="34" />
    <div class="text">
      <h2>{{ title }}</h2>
      <p v-if="intro">{{ intro }}</p>
      <p v-else-if="$slots.sub" class="sub"><slot name="sub" /></p>
    </div>
    <div class="actions"><slot name="actions" /></div>
  </div>
</template>

<script setup>
import EntityIcon from "./EntityIcon.vue";

defineProps({
  icon: { type: String, default: "" },
  title: { type: String, required: true },
  intro: { type: String, default: "" },
});
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 4px 2px 14px;
  border-bottom: 1px solid #eef2f6;
  margin-bottom: 14px;
}
.text { min-width: 0; }
h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 650;
  color: #0f172a;
  letter-spacing: -0.01em;
}
p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}
.actions { margin-left: auto; display: flex; gap: 8px; }
</style>
