<template>
  <div class="lineage-explorer" v-loading="loading">
    <div class="controls">
      <el-radio-group v-model="direction" size="small" :disabled="!focus"
                      @change="load">
        <el-radio-button value="upstream">{{ t("line.upstream") }}</el-radio-button>
        <el-radio-button value="downstream">
          {{ t("line.downstream") }}
        </el-radio-button>
        <el-radio-button value="both">{{ t("line.both") }}</el-radio-button>
      </el-radio-group>
      <el-select v-model="depth" size="small" style="width: 108px"
                 :disabled="!focus" @change="load">
        <el-option v-for="n in depths" :key="n" :value="n"
                   :label="tr('line.depth', { n })" />
      </el-select>
      <el-input v-if="focusable" v-model="focus" size="small" clearable
                style="width: 240px" :placeholder="t('line.focusHint')"
                @change="load" />
      <el-button v-if="focus" size="small" @click="clearFocus">
        {{ t("line.clearFocus") }}
      </el-button>
      <span v-if="!focus" class="muted">{{ t("line.focusFirst") }}</span>
      <div class="spacer" />
      <el-button size="small" @click="exportJson" :disabled="!data.nodes.length">
        {{ t("line.exportJson") }}
      </el-button>
      <el-button size="small" @click="exportCsv" :disabled="!data.edges.length">
        {{ t("line.exportCsv") }}
      </el-button>
    </div>

    <div class="meta">
      {{ tr("line.summary", { nodes: data.nodes.length, edges: data.edges.length }) }}
      <span v-if="focus" class="focus-chip">{{ focus }}</span>
    </div>

    <graph-canvas :nodes="graphNodes" :edges="data.edges" :height="height"
                  :highlight="focus" @select="selectNode" />

    <div class="column-head">
      <b>{{ t("line.columnLineage") }}</b>
      <span class="muted">{{ data.column_edges.length }}</span>
      <div class="spacer" />
      <el-input v-model="columnFilter" size="small" clearable
                style="width: 220px" :placeholder="t('line.columnFilter')" />
    </div>
    <el-table v-if="shownColumns.length" :data="shownColumns" size="small"
              border max-height="300">
      <el-table-column prop="from" :label="t('line.from')" min-width="150"
                       show-overflow-tooltip />
      <el-table-column prop="from_column" :label="t('line.fromColumn')"
                       min-width="130" />
      <el-table-column prop="to" :label="t('line.to')" min-width="150"
                       show-overflow-tooltip />
      <el-table-column prop="to_column" :label="t('line.toColumn')"
                       min-width="130" />
    </el-table>
    <el-empty v-else :description="t('line.noColumns')" :image-size="60" />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { api, errMsg } from "../api";
import { t } from "../i18n";
import GraphCanvas from "./GraphCanvas.vue";

const props = defineProps({
  focusRef: { type: String, default: "" },
  height: { type: Number, default: 360 },
  focusable: { type: Boolean, default: true },
});
const emit = defineEmits(["select"]);

const direction = ref("both");
const depth = ref(5);
const depths = [1, 2, 3, 5, 10];
const focus = ref(props.focusRef || "");
const columnFilter = ref("");
const loading = ref(false);
const data = reactive({ nodes: [], edges: [], column_edges: [],
                        node_types: {} });

function tr(key, vars = {}) {
  return Object.entries(vars).reduce(
    (out, [name, value]) => out.split(`{${name}}`).join(value ?? ""), t(key));
}

const graphNodes = computed(() => data.nodes.map((id) => ({
  id,
  name: id,
  type: data.node_types?.[id] || "table",
})));

const shownColumns = computed(() => {
  const needle = columnFilter.value.trim().toLowerCase();
  if (!needle) return data.column_edges;
  return data.column_edges.filter((row) =>
    `${row.from}.${row.from_column} ${row.to}.${row.to_column}`
      .toLowerCase().includes(needle));
});

async function load() {
  loading.value = true;
  try {
    const params = new URLSearchParams({
      depth: String(depth.value), direction: direction.value,
    });
    if (focus.value.trim()) params.set("ref", focus.value.trim());
    const out = await api.get(`/catalog/lineage?${params}`);
    data.nodes = out.nodes || [];
    data.edges = out.edges || [];
    data.column_edges = out.column_edges || [];
    data.node_types = out.node_types || {};
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

function clearFocus() {
  focus.value = "";
  load();
}

function selectNode(nodeId) {
  emit("select", nodeId);
  if (!props.focusable || !nodeId) return;
  focus.value = nodeId;
  load();
}

function download(name, text, type) {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

function exportJson() {
  download("odf-lineage.json", JSON.stringify(data, null, 2),
           "application/json");
}

function exportCsv() {
  const lines = ["from,to,from_type,to_type"];
  for (const row of data.edges) {
    lines.push([row.from, row.to, row.from_type || "", row.to_type || ""]
      .map((value) => `"${String(value).replaceAll('"', '""')}"`).join(","));
  }
  download("odf-lineage.csv", lines.join("\n"), "text/csv");
}

watch(() => props.focusRef, (value) => {
  focus.value = value || "";
  load();
});

onMounted(load);
</script>

<style scoped>
.lineage-explorer { min-height: 240px; }
.controls { display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
            margin-bottom: 8px; }
.spacer { flex: 1; }
.meta { font-size: 12px; color: #64748b; margin-bottom: 8px; }
.focus-chip { margin-left: 8px; padding: 1px 6px; border-radius: 4px;
              background: #eff6ff; color: #1d4ed8; }
.muted { color: #94a3b8; font-size: 12px; }
.column-head { display: flex; gap: 8px; align-items: center;
               margin: 14px 0 8px; font-size: 13px; }
</style>
