<template>
  <div class="json-view">
    <div class="json-toolbar">
      <slot name="label" />
      <div class="spacer" />
      <el-button link size="small" @click="copy">
        {{ t("json.copy") }}
      </el-button>
    </div>
    <div class="json-body">
      <json-node name="" :value="value" :depth="0" />
    </div>
  </div>
</template>

<script setup>
import { ElMessage } from "element-plus";
import { t } from "../i18n";
import JsonNode from "./JsonNode.vue";

const props = defineProps({ value: { type: null, default: null } });

async function copy() {
  try {
    const text = typeof props.value === "string"
      ? props.value : JSON.stringify(props.value, null, 2);
    await navigator.clipboard.writeText(text);
    ElMessage.success(t("json.copied"));
  } catch {
    ElMessage.error(t("json.copyFailed"));
  }
}
</script>

<style scoped>
.json-view {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fbfcfe;
  overflow: hidden;
}
.json-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-bottom: 1px solid #eef2f6;
  background: #fff;
}
.json-body {
  max-height: 360px;
  overflow: auto;
  padding: 8px 10px;
}
.spacer { flex: 1; }
</style>
