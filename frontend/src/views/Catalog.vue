<template>
  <div class="page">
    <div class="toolbar">
      <el-input v-model="q" placeholder="搜索表名" clearable style="width: 240px"
                :prefix-icon="Search" />
      <div class="spacer" />
      <el-button @click="load" :loading="loading">刷新</el-button>
    </div>

    <div class="layout">
      <el-card class="tree-card" shadow="never">
        <template #header><b>数据资产</b></template>
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
        <el-empty v-if="!datasets.length" description="尚未同步元数据" :image-size="70" />
      </el-card>

      <div class="right">
        <el-card v-if="q.trim()" class="card" shadow="never"
                 style="margin-bottom: 16px">
          <template #header><b>搜索 · {{ q }}</b></template>
          <div v-if="search.tables.length || search.columns.length">
            <div class="search-group" v-if="search.tables.length">
              <div class="muted">表</div>
              <el-tag v-for="t in search.tables" :key="'t' + t.id"
                      class="hit" @click="openDataset(t.id)">
                {{ t.schema }}.{{ t.table }}
              </el-tag>
            </div>
            <div class="search-group" v-if="search.columns.length">
              <div class="muted">字段</div>
              <el-tag v-for="c in search.columns"
                      :key="'c' + c.dataset_id + c.column" type="info"
                      class="hit" @click="openDataset(c.dataset_id)">
                {{ c.table }}.{{ c.column }} · {{ c.type }}
              </el-tag>
            </div>
          </div>
          <el-empty v-else description="没有匹配的表或字段" :image-size="50" />
        </el-card>
        <el-card v-if="detail.id" class="card" shadow="never">
          <template #header>
            <div class="card-head">
              <span>{{ detail.schema }}.{{ detail.table }}</span>
              <el-button link @click="tagDialog = true">打标签</el-button>
            </div>
          </template>
          <div class="meta">
            <el-tag v-for="t in detail.tags || []" :key="t" size="small"
                    type="info">{{ t }}</el-tag>
            <span v-if="!(detail.tags || []).length" class="muted">暂无标签</span>
          </div>
          <el-table :data="detail.columns || []" size="small" style="margin-top: 12px">
            <el-table-column prop="name" label="字段" />
            <el-table-column prop="type" label="类型" />
          </el-table>
          <div v-if="impact.edges.length" class="impact">
            <div class="muted" style="margin: 10px 0 6px">
              影响分析 · 下游 {{ impact.edges.length }} 条
            </div>
            <div v-for="(e, i) in impact.edges" :key="'i' + i"
                 class="col-edge">
              <span>{{ e.from }}</span>
              <el-icon><Right /></el-icon>
              <span>{{ e.to }}</span>
            </div>
            <div v-if="impact.column_edges.length" class="muted"
                 style="margin-top: 6px">
              列级影响 {{ impact.column_edges.length }} 条
            </div>
          </div>
        </el-card>
        <el-card v-else class="card" shadow="never">
          <el-empty description="从左侧选择一张表查看字段与标签" />
        </el-card>

        <el-card class="card" shadow="never" style="margin-top: 16px">
          <template #header><b>血缘</b></template>
          <div v-if="edges.length" class="lineage">
            <div v-for="(e, i) in edges" :key="i" class="edge">
              <span class="node-tag src">{{ e.from }}</span>
              <el-icon class="arrow"><Right /></el-icon>
              <span class="node-tag dst">{{ e.to }}</span>
              <span v-if="e.flow" class="flow">← {{ e.flow }}</span>
            </div>
          </div>
          <el-empty v-else description="暂无血缘（创建流程后自动生成）" :image-size="70" />
          <div v-if="columnEdges.length" class="column-lineage">
            <div class="muted" style="margin: 8px 0 6px">列级血缘</div>
            <div v-for="(e, i) in columnEdges" :key="'c' + i" class="col-edge">
              <span>{{ e.from }}.{{ e.from_column }}</span>
              <el-icon><Right /></el-icon>
              <span>{{ e.to }}.{{ e.to_column }}</span>
            </div>
          </div>
        </el-card>
      </div>
    </div>

    <el-dialog v-model="tagDialog" title="打标签" width="420px">
      <el-input v-model="newTag" placeholder="新标签名" />
      <template #footer>
        <el-button @click="tagDialog = false">取消</el-button>
        <el-button type="primary" @click="attachTag">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { Coin, Folder, Grid, Right, Search } from "@element-plus/icons-vue";
import { api, errMsg } from "../api";

const datasources = ref([]);
const datasets = ref([]);
const edges = ref([]);
const columnEdges = ref([]);
const impact = reactive({ nodes: [], edges: [], column_edges: [] });
const detail = ref({});
const loading = ref(false);
const q = ref("");
const search = reactive({ tables: [], columns: [] });
const treeRef = ref();
const tagDialog = ref(false);
const newTag = ref("");

const tree = computed(() => {
  const byDs = {};
  for (const d of datasets.value) {
    const ds = datasources.value.find((x) => x.id === d.datasource_id);
    const dsName = ds ? ds.name : `数据源 ${d.datasource_id}`;
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

async function openDataset(datasetId) {
  try {
    detail.value = await api.datasetDetail(datasetId);
    await loadImpact(detail.value);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function loadImpact(d) {
  impact.nodes = [];
  impact.edges = [];
  impact.column_edges = [];
  if (!d || !d.datasource_id || !d.table) return;
  try {
    const ref = `${d.datasource_id}:${d.table}`;
    const r = await api.get(
      `/catalog/impact?ref=${encodeURIComponent(ref)}`);
    impact.nodes = r.nodes || [];
    impact.edges = r.edges || [];
    impact.column_edges = r.column_edges || [];
  } catch {
    /* impact is advisory */
  }
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
    const l = await api.get("/catalog/lineage?project_id=1");
    edges.value = l.edges;
    columnEdges.value = l.column_edges || [];
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

async function onNode(data) {
  if (data.type !== "table") return;
  try {
    detail.value = await api.datasetDetail(data.dataset.id);
    await loadImpact(detail.value);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function attachTag() {
  if (!newTag.value) return;
  try {
    const t = await api.post("/catalog/tags", { project_id: 1, name: newTag.value });
    await api.post("/catalog/tags/attach", { dataset_id: detail.value.id, tag_id: t.id });
    tagDialog.value = false;
    newTag.value = "";
    detail.value = await api.datasetDetail(detail.value.id);
    ElMessage.success("已打标签");
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
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
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.meta {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
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
