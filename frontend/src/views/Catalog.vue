<template>
  <div class="page">
    <div class="toolbar">
      <el-input v-model="q" :placeholder="t('cat.searchPlaceholder')" clearable style="width: 240px"
                :prefix-icon="Search" />
      <div class="spacer" />
      <el-button @click="load" :loading="loading">{{ t("cat.refresh") }}</el-button>
    </div>

    <div class="layout">
      <el-card class="tree-card" shadow="never">
        <template #header><b>{{ t("cat.datasets") }}</b></template>
        <el-tree :data="tree" :props="{ label: 'label', children: 'children' }"
                 node-key="key" :filter-node-method="filterNode" ref="treeRef"
                 default-expand-all highlight-current @node-click="onNode">
          <template #default="{ data }">
            <span class="node">
              <el-icon v-if="data.type === 'ds'"><Coin /></el-icon>
              <el-icon v-else-if="data.type === 'schema'"><Folder /></el-icon>
              <el-icon v-else><Grid /></el-icon>
              {{ data.label }}
            </span>
          </template>
        </el-tree>
        <el-empty v-if="!datasets.length" :description="t('cat.noDatasets')" :image-size="70" />
      </el-card>

      <div class="right">
        <el-card v-if="q.trim()" class="card" shadow="never"
                 style="margin-bottom: 16px">
          <template #header><b>{{ t("cat.search") }} · {{ q }}</b></template>
          <div v-if="search.tables.length || search.columns.length">
            <div class="search-group" v-if="search.tables.length">
              <div class="muted">{{ t("cat.tables") }}</div>
              <el-tag v-for="t in search.tables" :key="'t' + t.id"
                      class="hit" @click="openDataset(t.id)">
                {{ t.schema }}.{{ t.table }}
              </el-tag>
            </div>
            <div class="search-group" v-if="search.columns.length">
              <div class="muted">{{ t("cat.columns") }}</div>
              <el-tag v-for="c in search.columns"
                      :key="'c' + c.dataset_id + c.column" type="info"
                      class="hit" @click="openDataset(c.dataset_id)">
                {{ c.table }}.{{ c.column }} · {{ c.type }}
              </el-tag>
            </div>
          </div>
          <el-empty v-else :description="t('cat.noMatches')" :image-size="50" />
        </el-card>

        <el-card class="card" shadow="never" style="margin-bottom: 16px">
          <el-empty :description="t('cat.openDetailHint')" :image-size="80" />
        </el-card>

        <el-card class="card" shadow="never">
          <template #header><b>{{ t("cat.lineage") }}</b></template>
          <div v-if="edges.length" class="lineage">
            <div v-for="(e, i) in edges" :key="i" class="edge">
              <span class="node-tag src">{{ e.from }}</span>
              <el-icon class="arrow"><Right /></el-icon>
              <span class="node-tag dst">{{ e.to }}</span>
              <span v-if="e.flow" class="flow">← {{ e.flow }}</span>
            </div>
          </div>
          <el-empty v-else :description="t('cat.noLineage')" :image-size="70" />
          <div v-if="columnEdges.length" class="column-lineage">
            <div class="muted" style="margin: 8px 0 6px">{{ t("cat.columnLineage") }}</div>
            <div v-for="(e, i) in columnEdges" :key="'c' + i" class="col-edge">
              <span>{{ e.from }}.{{ e.from_column }}</span>
              <el-icon><Right /></el-icon>
              <span>{{ e.to }}.{{ e.to_column }}</span>
            </div>
          </div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { Coin, Folder, Grid, Right, Search } from "@element-plus/icons-vue";
import { api, errMsg, getProject } from "../api";
import { t } from "../i18n";

const router = useRouter();
const datasources = ref([]);
const datasets = ref([]);
const edges = ref([]);
const columnEdges = ref([]);
const loading = ref(false);
const q = ref("");
const search = reactive({ tables: [], columns: [] });
const treeRef = ref();

const tree = computed(() => {
  const byDs = {};
  for (const d of datasets.value) {
    const ds = datasources.value.find((x) => x.id === d.datasource_id);
    const dsName = ds ? ds.name : `${t("cat.datasourceFallback")} ${d.datasource_id}`;
    byDs[d.datasource_id] = byDs[d.datasource_id] || {
      key: `ds-${d.datasource_id}`, label: dsName, type: "ds", children: {},
    };
    const node = byDs[d.datasource_id];
    const schema = d.schema || "main";
    node.children[schema] = node.children[schema] || {
      key: `ds-${d.datasource_id}-${schema}`, label: schema, type: "schema", children: [],
    };
    node.children[schema].children.push({
      key: `ds-${d.datasource_id}-${schema}-${d.table}`, label: d.table,
      type: "table", dataset: d,
    });
  }
  return Object.values(byDs).map((ds) => ({
    ...ds,
    children: Object.values(ds.children),
  }));
});

let searchTimer = null;
watch(q, (v) => {
  if (treeRef.value) treeRef.value.filter(v);
  clearTimeout(searchTimer);
  if (!v.trim()) {
    search.tables = [];
    search.columns = [];
    return;
  }
  searchTimer = setTimeout(async () => {
    try {
      const r = await api.get(
        `/catalog/search?q=${encodeURIComponent(v.trim())}`);
      search.tables = r.tables || [];
      search.columns = r.columns || [];
    } catch {
      search.tables = [];
      search.columns = [];
    }
  }, 250);
});

function openDataset(datasetId) {
  router.push(`/catalog/${datasetId}`);
}

function filterNode(value, data) {
  if (!value) return true;
  return data.label.toLowerCase().includes(value.toLowerCase());
}

async function load() {
  loading.value = true;
  try {
    datasources.value = await api.get("/datasources");
    datasets.value = await api.get("/catalog/datasets");
    const l = await api.get(`/catalog/lineage?project_id=${getProject() || 1}`);
    edges.value = l.edges;
    columnEdges.value = l.column_edges || [];
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

function onNode(data) {
  if (data.type !== "table") return;
  openDataset(data.dataset.id);
}

onMounted(load);
</script>

<style scoped>
.layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 16px;
}
.tree-card,
.card {
  border-radius: 12px;
  border: 1px solid #e5e7eb;
}
.node {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}
.muted {
  color: #9ca3af;
  font-size: 12px;
}
.search-group { margin-bottom: 10px; }
.hit { cursor: pointer; margin: 4px 6px 0 0; }
.column-lineage { border-top: 1px dashed #e5e7eb; margin-top: 10px; }
.col-edge {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #475569;
  padding: 3px 0;
}
.lineage {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.edge {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.node-tag {
  background: #eff6ff;
  color: #1d4ed8;
  border-radius: 6px;
  padding: 3px 8px;
}
.node-tag.dst {
  background: #ecfdf5;
  color: #047857;
}
.arrow {
  color: #9ca3af;
}
.flow {
  color: #9ca3af;
  font-size: 12px;
}
@media (max-width: 1000px) {
  .layout {
    grid-template-columns: 1fr;
  }
}
</style>
