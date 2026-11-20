<template>
  <span class="entity-icon" :class="{ plain }" :style="style">
    <el-icon :size="glyph"><component :is="icon" /></el-icon>
  </span>
</template>

<script setup>
import { computed } from "vue";
import {
  Bell, CircleCheck, Coin, Collection, Connection, Cpu, DataAnalysis,
  DataLine, Document, Grid, Odometer, Promotion, Share, Switch, User,
} from "@element-plus/icons-vue";
import { entityMeta } from "./entity";

const props = defineProps({
  type: { type: String, required: true },
  size: { type: Number, default: 16 },
  plain: { type: Boolean, default: false },
});

const ICONS = {
  Bell, CircleCheck, Coin, Collection, Connection, Cpu, DataAnalysis,
  DataLine, Document, Grid, Odometer, Promotion, Share, Switch, User,
};

const meta = computed(() => entityMeta(props.type));
const icon = computed(() => ICONS[meta.value.icon] || Grid);
const glyph = computed(() => Math.max(12, Math.round(props.size * 0.7)));
const style = computed(() => ({
  width: `${props.size}px`,
  height: `${props.size}px`,
  color: meta.value.color,
  background: props.plain ? "transparent" : `${meta.value.color}14`,
}));
</script>

<style scoped>
.entity-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  flex: none;
  vertical-align: -3px;
}
</style>
