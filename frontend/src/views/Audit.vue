<template>
  <div class="page">
    <page-header icon="audit" :title="t('menu.audit')"
                 :intro="t('audit.intro')" />
    <div class="toolbar">
      <el-input v-model="actor" :placeholder="t('audit.filterActor')" clearable
                style="width: 200px" />
      <el-input v-model="action" :placeholder="t('audit.filterAction')" clearable
                style="width: 200px" />
      <el-input v-model="q" :placeholder="t('audit.filterQ')" clearable
                style="width: 220px" @keyup.enter="load" />
      <div class="spacer" />
      <el-popover placement="bottom" :width="190" trigger="click">
        <template #reference>
          <el-button>{{ t("audit.columns") }}</el-button>
        </template>
        <el-checkbox v-for="col in columnOptions" :key="col.key"
                     :model-value="visible.columns.includes(col.key)"
                     @change="toggleColumn(col.key)">
          {{ col.label }}
        </el-checkbox>
      </el-popover>
      <el-button @click="load" :loading="loading">{{ t("audit.query") }}</el-button>
      <el-button @click="exportCsv">{{ t("audit.export") }}</el-button>
    </div>

    <el-card class="card" shadow="never">
      <div ref="tableWrap" class="audit-table">
        <el-skeleton v-if="loading && !rows.length" :rows="6" animated />
        <el-table-v2 v-else-if="paged.length" :columns="v2Columns"
                     :data="paged" :width="tableWidth" :height="520"
                     :row-height="42" :header-height="40" row-key="id" fixed
                     :row-event-handlers="rowHandlers" />
        <empty-state v-else :title="t('audit.empty')" />
      </div>
      <div class="pager">
        <el-pagination v-model:current-page="page" :page-size="pageSize"
                       :page-sizes="[20, 50, 100]"
                       :total="filtered.length"
                       layout="total, sizes, prev, pager, next" small />
      </div>
    </el-card>

    <el-drawer v-model="drawer" :title="t('audit.drawerTitle')" size="520px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="ID">{{ current.id }}</el-descriptions-item>
        <el-descriptions-item :label="t('audit.actor')">{{ current.actor }}</el-descriptions-item>
        <el-descriptions-item :label="t('audit.action')">{{ current.action }}</el-descriptions-item>
        <el-descriptions-item :label="t('audit.target')">{{ current.target }}</el-descriptions-item>
        <el-descriptions-item :label="t('audit.at')">{{ fmtDate(current.at) }}</el-descriptions-item>
      </el-descriptions>
      <h4>{{ t("audit.detail") }}</h4>
      <json-view :value="current.detail || {}" />
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, h, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { api, errMsg, getToken } from "../api";
import { fmtDate, t } from "../i18n";
import { loadPrefs, savePrefs } from "../prefs";
import EmptyState from "../components/EmptyState.vue";
import JsonView from "../components/JsonView.vue";
import PageHeader from "../components/PageHeader.vue";

const rows = ref([]);
const loading = ref(false);
const prefs = loadPrefs("audit", { actor: "", action: "", q: "",
                                    pageSize: 20, columns: null });
const columnOptions = computed(() => [
  { key: "id", label: "ID" },
  { key: "actor", label: t("audit.actor") },
  { key: "action", label: t("audit.action") },
  { key: "target", label: t("audit.target") },
  { key: "at", label: t("audit.at") },
  { key: "detail", label: t("audit.detail") },
]);
const visible = ref({
  columns: Array.isArray(prefs.columns) && prefs.columns.length
    ? prefs.columns : columnOptions.value.map((col) => col.key),
});
const tableWrap = ref(null);
const tableWidth = ref(1000);
let observer = null;

const v2Columns = computed(() => {
  const shown = visible.value.columns;
  const cols = [];
  if (shown.includes("id")) {
    cols.push({ key: "id", dataKey: "id", title: "ID", width: 80 });
  }
  if (shown.includes("actor")) {
    cols.push({ key: "actor", dataKey: "actor", title: t("audit.actor"),
                width: 150 });
  }
  if (shown.includes("action")) {
    cols.push({ key: "action", dataKey: "action", title: t("audit.action"),
                width: 190 });
  }
  if (shown.includes("target")) {
    cols.push({ key: "target", dataKey: "target", title: t("audit.target"),
                width: 160 });
  }
  if (shown.includes("at")) {
    cols.push({ key: "at", dataKey: "at", title: t("audit.at"), width: 200,
                cellRenderer: ({ cellData }) => h("span", fmtDate(cellData)) });
  }
  if (shown.includes("detail")) {
    cols.push({ key: "detail", dataKey: "detail", title: t("audit.detail"),
                width: 0, flexGrow: 1,
                cellRenderer: ({ cellData }) =>
                  h("span", { class: "mono" }, JSON.stringify(cellData)) });
  }
  return cols;
});

const rowHandlers = { onClick: ({ rowData }) => showDetail(rowData) };

function toggleColumn(key) {
  const current = visible.value.columns;
  visible.value.columns = current.includes(key)
    ? current.filter((item) => item !== key)
    : [...current, key];
}
const actor = ref(prefs.actor);
const action = ref(prefs.action);
const q = ref(prefs.q);
const page = ref(1);
const pageSize = ref(prefs.pageSize);
watch([q, actor, action], () => { page.value = 1; });
watch([q, actor, action, pageSize, visible], () => savePrefs("audit", {
  actor: actor.value, action: action.value, q: q.value,
  pageSize: pageSize.value, columns: visible.value.columns,
}), { deep: true });
const drawer = ref(false);
const current = ref({});

const filtered = computed(() =>
  rows.value.filter((r) => {
    const hitA = !actor.value || (r.actor || "").includes(actor.value);
    const hitB = !action.value || (r.action || "").includes(action.value);
    return hitA && hitB;
  })
);
const paged = computed(() =>
  filtered.value.slice((page.value - 1) * pageSize.value,
    page.value * pageSize.value)
);

function params() {
  const p = new URLSearchParams();
  p.set("limit", "500");
  if (actor.value) p.set("actor", actor.value);
  if (action.value) p.set("action", action.value);
  if (q.value) p.set("q", q.value);
  return p;
}

async function load() {
  loading.value = true;
  page.value = 1;
  try {
    rows.value = await api.get("/audit?" + params().toString());
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

async function exportCsv() {
  try {
    const p = params();
    p.delete("limit");
    p.set("limit", "5000");
    const r = await fetch("/api/v1/audit/export?" + p.toString(), {
      headers: { Authorization: "Bearer " + getToken() },
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const blob = await r.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "audit.csv";
    a.click();
    URL.revokeObjectURL(a.href);
  } catch (e) {
    ElMessage.error(t("audit.exportFailed") + ": " + errMsg(e));
  }
}
function showDetail(row) {
  current.value = row;
  drawer.value = true;
}
onMounted(() => {
  load();
  if (tableWrap.value) {
    tableWidth.value = tableWrap.value.clientWidth;
    observer = new ResizeObserver((entries) => {
      tableWidth.value = Math.max(320,
        Math.floor(entries[0].contentRect.width));
    });
    observer.observe(tableWrap.value);
  }
});

onBeforeUnmount(() => observer?.disconnect());
</script>

<style scoped>
.audit-table { width: 100%; }
.audit-table :deep(.el-table-v2__row) { cursor: pointer; }
.audit-table :deep(.mono) {
  font-family: Consolas, "Courier New", monospace;
  font-size: 11px;
}
.card {
  border-radius: 0;
  border: 1px solid #e5e7eb;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}
.mono {
  font-family: Consolas, monospace;
  font-size: 12px;
}
.detail {
  background: #0f172a;
  color: #e2e8f0;
  padding: 14px;
  border-radius: 0;
  font-size: 12px;
  overflow: auto;
}
:deep(.clickable) {
  cursor: pointer;
}
</style>
