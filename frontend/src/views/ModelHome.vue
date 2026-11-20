<template>
  <div class="page">
    <el-tabs v-model="tab" @tab-change="go">
      <el-tab-pane :label="t('model.datasets')" name="datasets" />
      <el-tab-pane :label="t('model.metrics')" name="metrics" />
    </el-tabs>
    <div class="toolbar">
      <el-input v-model="q" :placeholder="t('model.search')" clearable
                style="width: 260px" />
      <div class="spacer" />
      <el-button @click="load" :loading="loading">{{ t("model.refresh") }}</el-button>
      <el-button type="primary" @click="create">
        {{ t(tab === "datasets" ? "model.newDataset" : "model.newMetric") }}
      </el-button>
    </div>
    <el-card shadow="never">
      <el-table :data="filtered" size="small" v-loading="loading">
        <el-table-column prop="name" :label="t('model.name')" min-width="160" />
        <el-table-column prop="key" :label="t('model.key')" min-width="240">
          <template #default="{ row }">
            <span class="mono">{{ row.key }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('model.status')" width="110">
          <template #default="{ row }">
            <el-tag :type="row.published ? 'success' : 'info'" size="small">
              {{ row.published ? t("model.published") : t("model.draft") }}
            </el-tag>
          </template>
        </el-table-column>
        <template v-if="tab === 'metrics'">
          <el-table-column :label="t('model.metricSource')" min-width="150">
            <template #default="{ row }">{{ row.dataset_name || "-" }}</template>
          </el-table-column>
          <el-table-column :label="t('model.metricDefinition')" min-width="190">
            <template #default="{ row }">
              <span class="mono">{{ definition(row) }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('model.metricUsage')" width="110">
            <template #default="{ row }">
              <el-button link @click.stop="openUsage(row)">
                {{ row.usage_count }} {{ t("model.usageUnit") }}
              </el-button>
            </template>
          </el-table-column>
        </template>
        <el-table-column :label="t('model.actions')" width="170">
          <template #default="{ row }">
            <el-button link @click="$router.push(`/${tab}/${row.id}`)">
              {{ t("model.edit") }}
            </el-button>
            <el-button link type="danger" @click="remove(row)">
              {{ t("model.delete") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !filtered.length" :description="t('model.empty')" />
    </el-card>

    <el-drawer v-model="usageOpen" :title="t('model.metricDetail')"
               size="560px">
      <el-descriptions :column="1" border>
        <el-descriptions-item :label="t('model.name')">
          {{ current.name }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('model.owner')">
          {{ current.owner || "-" }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('model.metricSource')">
          {{ current.dataset_name || "-" }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('model.metricDefinition')">
          {{ definition(current) }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('model.dimensions')">
          {{ (current.dimensions || []).join(", ") || "-" }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('model.format')">
          <span class="mono">{{ JSON.stringify(current.format || {}) }}</span>
        </el-descriptions-item>
      </el-descriptions>
      <h4>{{ t("model.usageTitle") }}</h4>
      <el-table :data="current.usage || []" size="small">
        <el-table-column prop="type" :label="t('model.type')" width="120" />
        <el-table-column prop="name" :label="t('model.name')" min-width="160" />
        <el-table-column :label="t('model.status')" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="row.published ? 'success' : 'info'">
              {{ row.published ? t("model.published") : t("model.draft") }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!(current.usage || []).length"
                :description="t('model.noUsage')" :image-size="60" />

      <el-divider content-position="left">{{ t("model.lineage") }}</el-divider>
      <div v-if="lineage.edges.length" class="lineage">
        <div v-for="(e, i) in lineage.edges" :key="i" class="edge">
          <span class="node-tag">{{ e.from }}</span>
          <el-icon><Right /></el-icon>
          <span class="node-tag dst">{{ e.to }}</span>
        </div>
        <div v-if="lineage.column_edges.length" class="column-lineage">
          <div class="muted">{{ t("model.columnLineage") }}</div>
          <el-table :data="lineage.column_edges" size="small">
            <el-table-column prop="from" label="From" min-width="150" />
            <el-table-column prop="from_column" label="Column" width="120" />
            <el-table-column prop="to" label="To" min-width="150" />
            <el-table-column prop="to_column" label="Column" width="120" />
          </el-table>
        </div>
      </div>
      <el-empty v-else :description="t('model.noLineage')" :image-size="60" />
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { Right } from "@element-plus/icons-vue";
import { api, errMsg } from "../api";
import { t } from "../i18n";

const route = useRoute();
const router = useRouter();
const tab = ref(route.path.startsWith("/metrics") ? "metrics" : "datasets");
const rows = ref([]);
const q = ref("");
const loading = ref(false);
const usageOpen = ref(false);
const current = ref({});
const lineage = ref({ edges: [], column_edges: [] });
const filtered = computed(() => rows.value.filter((r) => {
  if (!q.value) return true;
  const text = [r.name, r.key, r.dataset_name,
                (r.dimensions || []).join(" ")].join(" ").toLowerCase();
  return text.includes(q.value.toLowerCase());
}));

function definition(row) {
  const measure = row.measure || {};
  if (!measure.agg) return "-";
  const column = measure.column || "*";
  const dims = row.dimensions || [];
  const base = `${measure.agg}(${column})`;
  return dims.length ? `${base} by ${dims.join(", ")}` : base;
}

async function openUsage(row) {
  current.value = row;
  lineage.value = { edges: [], column_edges: [] };
  usageOpen.value = true;
  try {
    lineage.value = await api.get(`/metrics/${row.id}/lineage`);
  } catch {
    lineage.value = { edges: [], column_edges: [] };
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(
      t("model.deleteConfirm").replace("{name}", row.name),
      t("model.deleteTitle"), { type: "warning" });
  } catch (e) {
    return;
  }
  try {
    await api.del(`/${tab.value}/${row.id}`);
    ElMessage.success(t("model.deleted"));
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function load() {
  loading.value = true;
  try {
    rows.value = await api.get(
      tab.value === "metrics" ? "/metrics/catalog" : "/datasets");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

function go() {
  router.push(`/${tab.value}`);
}

async function create() {
  try {
    const { value } = await ElMessageBox.prompt(t("model.namePrompt"), t("model.createTitle"), {
      inputPattern: /\S+/, inputErrorMessage: t("model.nameRequired"),
    });
    const r = await api.post(`/${tab.value}`, { name: value });
    router.push(`/${tab.value}/${r.id}`);
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

watch(() => route.path, () => {
  tab.value = route.path.startsWith("/metrics") ? "metrics" : "datasets";
  load();
});
onMounted(load);
</script>

<style scoped>
.toolbar { display: flex; gap: 10px; margin: 12px 0; align-items: center; }
.spacer { flex: 1; }
.mono { font-family: ui-monospace, monospace; font-size: 11px; }
.lineage { display: flex; flex-direction: column; gap: 8px; }
.edge { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.node-tag { background: #eff6ff; color: #1d4ed8; padding: 3px 8px;
            border-radius: 6px; }
.node-tag.dst { background: #ecfdf5; color: #047857; }
.muted { color: #64748b; font-size: 12px; }
.column-lineage { margin-top: 8px; }
</style>
