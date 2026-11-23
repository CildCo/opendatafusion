<template>
  <div class="result-table">
    <el-table v-if="rows.length" :data="rows" size="small" border
              :height="height" show-overflow-tooltip>
      <el-table-column v-for="column in columns" :key="column"
                       :label="column" min-width="140">
        <template #default="{ row }">
          <span v-if="isComplex(row[column])" class="complex"
                :title="JSON.stringify(row[column])">{
            {{ Array.isArray(row[column]) ? row[column].length : "…" }} }</span>
          <span v-else-if="row[column] === null || row[column] === undefined"
                class="null">-</span>
          <span v-else>{{ row[column] }}</span>
        </template>
      </el-table-column>
    </el-table>
    <empty-state v-else :title="emptyText" :description="hint" />
    <div v-if="rows.length" class="result-foot">
      <span class="muted">{{ rows.length }} {{ t("result.rows") }}</span>
      <div class="spacer" />
      <el-button link size="small" @click="copyCsv">
        {{ t("result.copyCsv") }}
      </el-button>
      <el-button link size="small" @click="copyJson">
        {{ t("result.copyJson") }}
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { ElMessage } from "element-plus";
import { t } from "../i18n";
import EmptyState from "./EmptyState.vue";

const props = defineProps({
  rows: { type: Array, default: () => [] },
  height: { type: Number, default: 360 },
  emptyText: { type: String, default: "" },
  hint: { type: String, default: "" },
});

function isComplex(value) {
  return value !== null && typeof value === "object";
}

const columns = computed(() => {
  const keys = [];
  const seen = new Set();
  for (const row of props.rows.slice(0, 100)) {
    if (!row || typeof row !== "object") continue;
    for (const key of Object.keys(row)) {
      if (!seen.has(key)) {
        seen.add(key);
        keys.push(key);
      }
    }
  }
  return keys;
});

function cell(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function toCsv() {
  const header = columns.value.map((c) => csvCell(c)).join(",");
  const body = props.rows.map(
    (row) => columns.value.map((c) => csvCell(cell(row[c]))).join(","));
  return [header, ...body].join("\n");
}

function csvCell(value) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

async function copyCsv() {
  try {
    await navigator.clipboard.writeText(toCsv());
    ElMessage.success(t("result.copied"));
  } catch {
    ElMessage.error(t("result.copyFailed"));
  }
}

async function copyJson() {
  try {
    await navigator.clipboard.writeText(JSON.stringify(props.rows, null, 2));
    ElMessage.success(t("result.copied"));
  } catch {
    ElMessage.error(t("result.copyFailed"));
  }
}
</script>

<style scoped>
.result-table { width: 100%; }
.result-foot {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 2px 0;
}
.muted { color: #94a3b8; font-size: 12px; }
.complex { color: #7c3aed; }
.null { color: #94a3b8; }
.spacer { flex: 1; }
</style>
