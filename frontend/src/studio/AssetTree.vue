<template>
  <div class="tree">
    <div class="head">{{ title || t("tree.title") }}</div>
    <div v-for="p in items" :key="p.id" class="item"
         :class="{ active: p.id === activeId }" @click="$emit('select', p)">
      <span class="name">{{ p.name }}</span>
      <el-tag size="small" :type="p.enabled ? 'success' : 'info'">
        {{ p.enabled ? t("tree.enabled") : t("tree.disabled") }}
      </el-tag>
    </div>
    <el-empty v-if="!items.length" :description="t('tree.empty')" :image-size="60" />
  </div>
</template>

<script setup>
import { t } from "../i18n";

defineProps({
  items: { type: Array, default: () => [] },
  activeId: { type: Number, default: null },
  title: { type: String, default: "" },
});
defineEmits(["select"]);
</script>

<style scoped>
.tree { padding: 10px; }
.head { font-weight: 600; font-size: 13px; margin: 4px 6px 10px; color: #374151; }
.item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
}
.item:hover { background: #f3f4f6; }
.item.active { background: #eff6ff; }
.name { font-size: 13px; color: #111827; }
</style>
