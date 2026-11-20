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
      <el-button @click="load" :loading="loading">{{ t("audit.query") }}</el-button>
      <el-button @click="exportCsv">{{ t("audit.export") }}</el-button>
    </div>

    <el-card class="card" shadow="never">
      <el-table :data="paged" size="small" v-loading="loading"
                @row-click="showDetail" row-class-name="clickable">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="actor" :label="t('audit.actor')" width="150" />
        <el-table-column prop="action" :label="t('audit.action')" width="190" />
        <el-table-column prop="target" :label="t('audit.target')" width="160" />
        <el-table-column :label="t('audit.at')" width="200">
          <template #default="{ row }">{{ fmtDate(row.at) }}</template>
        </el-table-column>
        <el-table-column :label="t('audit.detail')">
          <template #default="{ row }">
            <span class="mono">{{ JSON.stringify(row.detail) }}</span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !filtered.length"
                :description="t('audit.empty')" />
      <div class="pager">
        <el-pagination v-model:current-page="page" :page-size="pageSize"
                       :total="filtered.length" layout="total, prev, pager, next" small />
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
      <pre class="detail">{{ JSON.stringify(current.detail, null, 2) }}</pre>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { api, errMsg, getToken } from "../api";
import { fmtDate, t } from "../i18n";
import PageHeader from "../components/PageHeader.vue";

const rows = ref([]);
const loading = ref(false);
const actor = ref("");
const action = ref("");
const q = ref("");
const page = ref(1);
const pageSize = 20;
watch([q, actor, action], () => { page.value = 1; });
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
  filtered.value.slice((page.value - 1) * pageSize, page.value * pageSize)
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
onMounted(load);
</script>

<style scoped>
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
