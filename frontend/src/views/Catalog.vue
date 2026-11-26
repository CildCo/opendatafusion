<template>
  <div class="page">
    <div class="toolbar">
      <el-radio-group v-model="mode" size="small">
        <el-radio-button value="tables">{{ t("cat.tabTables") }}</el-radio-button>
        <el-radio-button value="assets">{{ t("cat.tabAssets") }}</el-radio-button>
      </el-radio-group>
      <el-input v-if="mode === 'tables'" v-model="q"
                :placeholder="t('cat.searchPlaceholder')" clearable
                style="width: 240px" :prefix-icon="Search" />
      <div class="spacer" />
      <el-button @click="load" :loading="loading">{{ t("cat.refresh") }}</el-button>
      <el-button @click="exportCatalog">{{ t("cat.export") }}</el-button>
    </div>

    <asset-catalog v-if="mode === 'assets'" />
    <div v-else class="layout">
      <div class="left">
        <el-card class="tree-card" shadow="never">
          <template #header>
            <div class="tree-head">
              <b>{{ t("cat.datasets") }}</b>
              <el-radio-group v-model="groupBy" size="small">
                <el-radio-button value="source">
                  {{ t("cat.groupBySource") }}
                </el-radio-button>
                <el-radio-button value="domain">
                  {{ t("cat.groupByDomain") }}
                </el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <div v-if="domainFilter" class="domain-filter">
            <el-tag size="small" closable @close="clearDomain">
              {{ domainLabel }}
            </el-tag>
          </div>
          <el-tree :data="tree" :props="{ label: 'label', children: 'children' }"
                   node-key="key" :filter-node-method="filterNode" ref="treeRef"
                   default-expand-all highlight-current @node-click="onNode">
            <template #default="{ data }">
              <span class="node">
                <el-icon v-if="data.type === 'ds' || data.type === 'domain'">
                  <Coin v-if="data.type === 'domain'" /><Coin v-else />
                </el-icon>
                <el-icon v-else-if="data.type === 'schema'"><Folder /></el-icon>
                <el-icon v-else><Grid /></el-icon>
                {{ data.label }}
                <span v-if="data.count" class="count">{{ data.count }}</span>
              </span>
            </template>
          </el-tree>
          <el-empty v-if="!tree.length" :description="t('cat.noDatasets')"
                    :image-size="70" />
        </el-card>

        <el-card class="card glossary" shadow="never">
          <template #header>
            <div class="tree-head">
              <b>{{ t("cat.glossary") }}</b>
              <span class="muted">{{ terms.length }}</span>
            </div>
          </template>
          <div v-for="term in terms" :key="term.id" class="term"
               @click="pickDomain(term.domain_id)">
            <b>{{ term.term }}</b>
            <small>{{ term.definition || t("cat.noDefinition") }}</small>
          </div>
          <el-empty v-if="!terms.length" :description="t('cat.glossaryEmpty')"
                    :image-size="50" />
        </el-card>
      </div>

      <div class="right">
        <el-card v-if="q.trim()" class="card" shadow="never"
                 style="margin-bottom: 16px">
          <template #header><b>{{ t("cat.search") }} · {{ q }}</b></template>
          <div v-if="search.tables.length || search.columns.length">
            <div class="search-group" v-if="search.tables.length">
              <div class="muted">{{ t("cat.tables") }}</div>
              <div v-for="t in search.tables" :key="'t' + t.id"
                   class="search-row" @click="openDataset(t.id)">
                <b>{{ t.schema }}.{{ t.table }}</b>
                <small>{{ t.datasource_name }}</small>
                <span class="hit-tags">
                  <el-tag v-for="c in t.matched_columns" :key="c"
                          size="small" type="info">{{ c }}</el-tag>
                  <el-tag v-for="g in t.matched_tags" :key="'g' + g"
                          size="small">{{ g }}</el-tag>
                  <el-tag v-for="term in t.matched_terms || []"
                          :key="'tm' + term.term + term.column" size="small"
                          type="success">
                    {{ term.term }} · {{ term.column }}
                  </el-tag>
                </span>
              </div>
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
          <template #header>
            <div class="tree-head">
              <b>{{ t("cat.lineage") }}</b>
              <span class="muted">{{ t("cat.lineageHint") }}</span>
            </div>
          </template>
          <lineage-explorer :height="340" focusable />
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { Coin, Folder, Grid, Search } from "@element-plus/icons-vue";
import { api, errMsg, getProject } from "../api";
import { t } from "../i18n";
import LineageExplorer from "../components/LineageExplorer.vue";
import AssetCatalog from "./AssetCatalog.vue";

const router = useRouter();
const datasources = ref([]);
const datasets = ref([]);
const terms = ref([]);
const loading = ref(false);
const q = ref("");
const mode = ref("tables");
const groupBy = ref("source");
const domainFilter = ref(null);
const search = reactive({ tables: [], columns: [] });
const treeRef = ref();

const visibleDatasets = computed(() => {
  if (!domainFilter.value) return datasets.value;
  return datasets.value.filter((d) => d.domain_id === domainFilter.value);
});

const domainLabel = computed(() => {
  const found = datasets.value.find((d) => d.domain_id === domainFilter.value);
  return found?.domain_name || t("cat.ungrouped");
});

function buildGroup(key, label, type, items) {
  const schemas = {};
  for (const d of items) {
    const schema = d.schema || "main";
    schemas[schema] = schemas[schema] || {
      key: `${key}-${schema}`, label: schema, type: "schema", children: [],
    };
    schemas[schema].children.push({
      key: `${key}-${schema}-${d.table}`, label: d.table,
      type: "table", dataset: d,
    });
  }
  return {
    key, label, type, count: items.length,
    children: Object.values(schemas),
  };
}

const tree = computed(() => {
  const groups = new Map();
  for (const d of visibleDatasets.value) {
    if (groupBy.value === "domain") {
      const key = d.domain_id ? `domain-${d.domain_id}` : "domain-none";
      const label = d.domain_name || t("cat.ungrouped");
      if (!groups.has(key)) groups.set(key, { label, type: "domain",
                                              items: [] });
      groups.get(key).items.push(d);
    } else {
      const key = `ds-${d.datasource_id}`;
      if (!groups.has(key)) {
        const ds = datasources.value.find((x) => x.id === d.datasource_id);
        groups.set(key, {
          label: ds ? ds.name
            : `${t("cat.datasourceFallback")} ${d.datasource_id}`,
          type: "ds", items: [],
        });
      }
      groups.get(key).items.push(d);
    }
  }
  return [...groups.entries()].map(([key, group]) =>
    buildGroup(key, group.label, group.type, group.items));
});

function pickDomain(domainId) {
  domainFilter.value = domainId || null;
  if (domainId) groupBy.value = "domain";
}

function clearDomain() {
  domainFilter.value = null;
}

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

async function exportCatalog() {
  try {
    await api.download("/catalog/export", "odf-catalog.json");
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function load() {
  loading.value = true;
  try {
    datasources.value = await api.get("/datasources");
    datasets.value = await api.get("/catalog/datasets");
    const termsOut = await api.get(
      `/governance/terms?project_id=${getProject() || 1}`);
    terms.value = termsOut.items || [];
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
.left { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.tree-card,
.card {
  border-radius: 12px;
  border: 1px solid #e5e7eb;
}
.tree-head { display: flex; align-items: center; justify-content: space-between;
             gap: 8px; }
.count { color: #94a3b8; font-size: 11px; }
.domain-filter { margin-bottom: 6px; }
.glossary :deep(.el-card__body) { padding: 4px 10px 10px; }
.term { display: flex; flex-direction: column; gap: 2px; padding: 6px 4px;
        border-bottom: 1px solid #f1f5f9; cursor: pointer; }
.term b { font-size: 12px; color: #0f172a; }
.term small { font-size: 11px; color: #64748b; overflow: hidden;
              text-overflow: ellipsis; white-space: nowrap; }
.term:hover { background: #f8fafc; }
.search-row { display: flex; align-items: center; gap: 8px; padding: 6px 8px;
              border-radius: 6px; cursor: pointer; font-size: 13px; }
.search-row:hover { background: #f1f5f9; }
.search-row small { color: #64748b; }
.hit-tags { display: inline-flex; gap: 4px; flex-wrap: wrap; }
.node {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}
.muted {
  color: #64748b;
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
  color: #64748b;
}
.flow {
  color: #64748b;
  font-size: 12px;
}
@media (max-width: 1000px) {
  .layout {
    grid-template-columns: 1fr;
  }
}
</style>
