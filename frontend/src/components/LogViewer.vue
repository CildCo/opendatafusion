<template>
  <div class="log-viewer">
    <div class="log-bar">
      <el-input v-model="search" size="small" clearable
                :placeholder="t('log.search')" style="width: 180px" />
      <el-select v-model="level" size="small" style="width: 110px">
        <el-option value="ALL" :label="t('log.all')" />
        <el-option value="ERROR" label="ERROR" />
        <el-option value="WARN" label="WARN" />
        <el-option value="INFO" label="INFO" />
        <el-option value="DEBUG" label="DEBUG" />
      </el-select>
      <el-checkbox v-model="follow" size="small">{{ t("log.follow") }}</el-checkbox>
      <div class="spacer" />
      <el-button link size="small" @click="copy">{{ t("log.copy") }}</el-button>
      <el-button link size="small" @click="download">{{ t("log.download") }}</el-button>
    </div>
    <div v-if="filtered.length" ref="box" class="log-lines">
      <div v-for="line in filtered" :key="line.index" class="log-line">
        <span class="log-level" :class="line.level.toLowerCase()"
              v-if="line.level">{{ line.level }}</span>
        <span class="log-text">{{ line.text }}</span>
      </div>
    </div>
    <empty-state v-else :title="t('log.empty')" />
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { t } from "../i18n";
import EmptyState from "./EmptyState.vue";

const props = defineProps({
  text: { type: String, default: "" },
  height: { type: Number, default: 340 },
});

const search = ref("");
const level = ref("ALL");
const follow = ref(true);
const box = ref(null);

const parsed = computed(() => (props.text || "").split("\n").map(
  (text, index) => {
    const match = text.match(/\b(FATAL|ERROR|WARN(?:ING)?|INFO|DEBUG|TRACE)\b/i);
    let tag = match ? match[1].toUpperCase() : "";
    if (tag === "WARNING") tag = "WARN";
    if (tag === "TRACE") tag = "DEBUG";
    return { index, text, level: tag };
  }));

const filtered = computed(() => {
  const term = search.value.trim().toLowerCase();
  return parsed.value.filter((line) => {
    if (line.text === "" && !term) return false;
    if (level.value !== "ALL" && line.level !== level.value) return false;
    return !term || line.text.toLowerCase().includes(term);
  });
});

watch(filtered, async () => {
  if (!follow.value) return;
  await nextTick();
  if (box.value) box.value.scrollTop = box.value.scrollHeight;
});

async function copy() {
  try {
    await navigator.clipboard.writeText(filtered.value
      .map((line) => line.text).join("\n"));
    ElMessage.success(t("result.copied"));
  } catch {
    ElMessage.error(t("result.copyFailed"));
  }
}

function download() {
  const blob = new Blob([props.text || ""], { type: "text/plain" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "engine-job.log";
  link.click();
  URL.revokeObjectURL(link.href);
}
</script>

<style scoped>
.log-viewer {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
  background: #0f172a;
}
.log-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: #fff;
  border-bottom: 1px solid #eef2f6;
}
.log-lines {
  max-height: 340px;
  overflow: auto;
  padding: 8px 10px;
  font-family: Consolas, "Courier New", monospace;
  font-size: 11px;
  line-height: 1.6;
}
.log-line { display: flex; gap: 8px; color: #cbd5e1; }
.log-text { white-space: pre-wrap; word-break: break-all; }
.log-level {
  flex: none;
  font-weight: 700;
  color: #94a3b8;
}
.log-level.error { color: #f87171; }
.log-level.warn { color: #fbbf24; }
.log-level.info { color: #60a5fa; }
.log-level.debug { color: #94a3b8; }
.spacer { flex: 1; }
</style>
