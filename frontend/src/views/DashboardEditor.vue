<template>
  <div class="dash-page">
    <div class="head">
      <el-button link @click="$router.push('/dashboards')":aria-label="t('common.back')">←</el-button>
      <el-input v-model="name" size="small" style="width: 220px"
                @change="rename" />
      <el-tag size="small" :type="published ? 'success' : 'info'">
        {{ published ? t("dedit.published") : t("dedit.draft") }}
      </el-tag>
      <favorite-button type="dashboard" :id="id" />
      <div class="spacer" />
      <history-controls :can-undo="canUndo" :can-redo="canRedo"
                        @undo="history.undo" @redo="history.redo" />
      <el-button size="small" @click="save()">{{ t("dedit.save") }}</el-button>
      <el-button size="small" @click="validate">{{ t("dedit.validate") }}</el-button>
      <el-button size="small" :loading="loadingData" @click="refresh">{{ t("dedit.refreshData") }}</el-button>
      <el-button size="small" type="primary" @click="publish">{{ t("dedit.publish") }}</el-button>
      <el-button size="small" @click="versionsOpen = true">{{ t("dedit.versions") }}</el-button>
      <el-button size="small" @click="lineageOpen = true">{{ t("lin.button") }}</el-button>
      <el-button size="small" @click="governanceOpen = true">{{ t("gov.button") }}</el-button>
      <el-button size="small" @click="reportOpen = true">{{ t("report.button") }}</el-button>
      <el-button size="small" :disabled="!published"
                 @click="$router.push(`/dashboards/${id}/run`)">
        {{ t("dedit.run") }}
      </el-button>
      <ShareDialog kind="dashboards" :asset-id="id"
                   :published="published" />
    </div>

    <div class="body">
      <aside class="palette">
        <div class="label">{{ t("dedit.components") }}</div>
        <el-button size="small" type="primary" class="add"
                   @click="galleryOpen = true">
          + {{ t("gallery.add") }}
        </el-button>
        <div class="label" style="margin-top: 14px">{{ t("dedit.filterParams") }}</div>
        <div v-for="(p, i) in content.params" :key="i" class="param-row">
          <el-input v-model="p.name" size="small" :placeholder="t('dedit.paramNamePlaceholder')"
                    @change="resetParams" />
          <el-select v-model="p.type" size="small" style="width: 88px"
                     @change="resetParams">
            <el-option v-for="pt in paramTypes" :key="pt" :value="pt"
                       :label="pt" />
          </el-select>
          <el-input v-model="p.default" size="small" :placeholder="t('dedit.defaultValue')"
                    @change="resetParams" />
          <el-button link type="danger" size="small"
                     @click="removeParam(i)":aria-label="t('common.remove')">×</el-button>
        </div>
        <el-button size="small" class="add" @click="addParam">
          {{ t("dedit.addParam") }}
        </el-button>
        <p class="hint">{{ t("dedit.dragHint") }}</p>
      </aside>

      <main class="canvas">
        <DashboardFilters :params="content.params || []"
                          :value="paramValues"
                          @update:value="setParams"
                          @refresh="refresh" @reset="resetFilterParams" />
        <DashboardGrid :widgets="content.widgets" :data="data"
                       :columns="content.columns"
                       :row-height="content.row_height"
                       :selected-id="selected?.id || ''"
                       drillable
                       @select="selectWidget" @change="dirty = true"
                       @drag-start="history.pause"
                       @change-end="onCanvasChangeEnd"
                       @filter="onFilter" @drill="onDrill" />
      </main>

      <aside class="config">
        <template v-if="selected">
          <div class="config-head">
            <h4>{{ selected.type }} {{ t("dedit.configSuffix") }}</h4>
            <el-button link type="danger" @click="removeWidget">{{ t("dedit.delete") }}</el-button>
          </div>
          <el-form label-width="76px" size="small">
            <el-form-item :label="t('dedit.title')">
              <el-input v-model="selected.title" />
            </el-form-item>
            <template v-if="selected.type !== 'text'">
              <el-form-item :label="t('dedit.filter')">
                <div class="filter-list">
                  <div v-for="(f, i) in selected.filters || []" :key="i"
                       class="filter-row">
                    <el-select v-model="f.column" size="small" filterable
                               allow-create :placeholder="t('dedit.column')"
                               style="width: 96px">
                      <el-option v-for="c in filterColumns" :key="c"
                                 :value="c" :label="c" />
                    </el-select>
                    <el-select v-model="f.op" size="small"
                               style="width: 82px">
                      <el-option v-for="op in ops" :key="op" :value="op"
                                 :label="op" />
                    </el-select>
                    <el-select v-model="f.param" size="small"
                               :placeholder="t('dedit.param')" style="width: 84px">
                      <el-option v-for="p in content.params" :key="p.name"
                                 :value="p.name" :label="p.name" />
                    </el-select>
                    <el-button link type="danger" size="small"
                               @click="removeFilter(i)":aria-label="t('common.remove')">×</el-button>
                  </div>
                  <el-button link size="small"
                             :disabled="!content.params.length"
                             @click="addFilter">{{ t("dedit.addCondition") }}</el-button>
                </div>
              </el-form-item>
              <el-form-item v-if="!selected.interaction && ['line','bar','area','pie','map','table'].includes(selected.type)"
                            :label="t('dedit.clickLinkage')">
                <div v-if="selected.emit" class="filter-row">
                  <el-select v-model="selected.emit.param" size="small"
                             :placeholder="t('dedit.param')" style="width: 92px">
                    <el-option v-for="p in content.params" :key="p.name"
                               :value="p.name" :label="p.name" />
                  </el-select>
                  <el-select v-if="isChart" :model-value="selected.dimension"
                             size="small" disabled style="width: 92px">
                    <el-option :value="selected.dimension"
                               :label="selected.dimension" />
                  </el-select>
                  <el-select v-else v-model="selected.emit.from" size="small"
                             filterable allow-create :placeholder="t('dedit.column')"
                             style="width: 92px">
                    <el-option v-for="c in filterColumns" :key="c" :value="c"
                               :label="c" />
                  </el-select>
                  <el-button link type="danger" size="small"
                             @click="selected.emit = null":aria-label="t('common.remove')">×</el-button>
                </div>
                <el-button v-else link size="small"
                           :disabled="!content.params.length"
                           @click="enableEmit">{{ t("dedit.enable") }}</el-button>
              </el-form-item>
              <el-form-item :label="t('dedit.clickBehavior')">
                <el-select :model-value="selected.interaction?.type || 'filter'"
                           style="width: 100%"
                           @update:model-value="setInteractionType">
                  <el-option value="filter" :label="t('dedit.behaviorFilter')" />
                  <el-option value="navigate"
                             :label="t('dedit.behaviorNavigate')" />
                  <el-option value="url" :label="t('dedit.behaviorUrl')" />
                </el-select>
                <el-input v-if="selected.interaction"
                          v-model="selected.interaction.url" size="small"
                          style="margin-top: 6px"
                          :placeholder="t('dedit.behaviorUrlHint')" />
              </el-form-item>
            </template>
            <template v-if="['card','line','bar','area','pie','map'].includes(selected.type)">
              <el-form-item :label="t('dedit.metric')">
                <el-select v-model="selected.metric_id" filterable clearable
                           style="width: 100%" @change="loadMetric">
                  <el-option v-for="m in metrics" :key="m.id" :value="m.id"
                             :label="m.name" />
                </el-select>
              </el-form-item>
              <el-form-item v-if="['line','bar','area','pie','map'].includes(selected.type)"
                            :label="t('dedit.dimension')">
                <el-select v-model="selected.dimension" filterable
                           style="width: 100%" @change="syncEmit">
                  <el-option v-for="d in metricDims" :key="d" :value="d"
                             :label="d" />
                </el-select>
              </el-form-item>
              <template v-if="selected.type === 'pivot'">
                <el-form-item :label="t('dedit.rowDimension')">
                  <el-select v-model="selected.row_dimension" filterable
                             style="width: 100%">
                    <el-option v-for="d in metricDims" :key="d" :value="d"
                               :label="d" />
                  </el-select>
                </el-form-item>
                <el-form-item :label="t('dedit.columnDimension')">
                  <el-select v-model="selected.column_dimension" filterable
                             style="width: 100%">
                    <el-option v-for="d in metricDims" :key="d" :value="d"
                               :label="d" />
                  </el-select>
                </el-form-item>
              </template>
              <el-form-item :label="t('dedit.valueColumn')">
                <el-select v-model="selected.value_column" filterable
                           clearable style="width: 100%">
                  <el-option v-for="c in valueOptions" :key="c" :value="c"
                             :label="c" />
                </el-select>
              </el-form-item>
              <template v-if="selected.type === 'map'">
                <el-form-item :label="t('dedit.mapData')">
                  <el-upload :auto-upload="false" :show-file-list="false"
                             accept=".json,application/json"
                             :on-change="loadGeo">
                    <el-button size="small">{{ t("dedit.mapUpload") }}</el-button>
                  </el-upload>
                  <span class="map-hint">
                    {{ selected.geo_json?.features?.length || 0 }}
                    {{ t("dedit.mapFeatures") }}
                  </span>
                </el-form-item>
                <el-form-item :label="t('dedit.mapNameProperty')">
                  <el-input v-model="selected.name_property"
                            placeholder="name" />
                </el-form-item>
              </template>
            </template>
            <template v-if="selected.type === 'table'">
              <el-form-item :label="t('dedit.dataset')">
                <el-select v-model="selected.dataset_id" filterable clearable
                           style="width: 100%"
                           @change="selected.metric_id = null">
                  <el-option v-for="d in datasets" :key="d.id" :value="d.id"
                             :label="d.name" />
                </el-select>
              </el-form-item>
              <el-form-item :label="t('dedit.metric')">
                <el-select v-model="selected.metric_id" filterable clearable
                           style="width: 100%"
                           @change="chooseTableMetric">
                  <el-option v-for="m in metrics" :key="m.id" :value="m.id"
                             :label="m.name" />
                </el-select>
              </el-form-item>
              <el-form-item :label="t('dedit.rowCount')">
                <el-input-number v-model="selected.limit" :min="1"
                                 :max="10000" />
              </el-form-item>
              <el-form-item v-if="selected.metric_id"
                            :label="t('dedit.drillDimension')">
                <el-select v-model="selected.drill_dimension" clearable
                           filterable style="width: 100%">
                  <el-option v-for="d in metricDims" :key="d" :value="d"
                             :label="d" />
                </el-select>
              </el-form-item>
            </template>
            <el-form-item v-if="selected.type === 'text'" :label="t('dedit.text')">
              <el-input v-model="selected.text" type="textarea" :rows="4" />
            </el-form-item>
            <template v-if="['card','line','bar','area','pie','map'].includes(selected.type)">
              <el-divider content-position="left">
                {{ t("dedit.style") }}
              </el-divider>
              <el-form-item :label="t('dedit.palette')">
                <el-select v-model="selected.format.palette" clearable
                           style="width: 100%"
                           :placeholder="t('dedit.paletteDefault')">
                  <el-option value="blue" :label="t('dedit.paletteBlue')" />
                  <el-option value="green" :label="t('dedit.paletteGreen')" />
                  <el-option value="warm" :label="t('dedit.paletteWarm')" />
                  <el-option value="mono" :label="t('dedit.paletteMono')" />
                </el-select>
              </el-form-item>
              <el-form-item :label="t('dedit.numberFormat')">
                <el-select v-model="selected.format.numberFormat"
                           style="width: 100%">
                  <el-option value="auto" :label="t('dedit.fmtAuto')" />
                  <el-option value="number" :label="t('dedit.fmtNumber')" />
                  <el-option value="percent" :label="t('dedit.fmtPercent')" />
                  <el-option value="compact" :label="t('dedit.fmtCompact')" />
                </el-select>
              </el-form-item>
              <template v-if="selected.type !== 'card'">
                <el-form-item :label="t('dedit.legend')">
                  <el-switch v-model="selected.format.legend" />
                </el-form-item>
                <el-form-item :label="t('dedit.labels')">
                  <el-switch v-model="selected.format.labels" />
                </el-form-item>
              </template>
              <template v-if="['line','bar','area'].includes(selected.type)">
                <el-form-item :label="t('dedit.smooth')">
                  <el-switch v-model="selected.format.smooth" />
                </el-form-item>
                <el-form-item :label="t('dedit.xTitle')">
                  <el-input v-model="selected.format.xTitle" />
                </el-form-item>
                <el-form-item :label="t('dedit.yTitle')">
                  <el-input v-model="selected.format.yTitle" />
                </el-form-item>
              </template>
            </template>
            <el-form-item :label="t('dedit.layout')">
              <div class="layout">
                <el-input-number v-model="selected.x" :min="0"
                                 :max="content.columns - 1" />
                <el-input-number v-model="selected.y" :min="0" />
                <el-input-number v-model="selected.w" :min="1"
                                 :max="content.columns" />
                <el-input-number v-model="selected.h" :min="1" />
              </div>
            </el-form-item>
          </el-form>
        </template>
        <el-empty v-else :description="t('dedit.emptyWidgets')" :image-size="60" />
      </aside>
    </div>

    <el-drawer v-model="versionsOpen" :title="t('dedit.versions')" size="480px"
               @open="loadVersions">
      <el-table :data="versions" size="small">
        <el-table-column prop="version" :label="t('dedit.version')" width="70" />
        <el-table-column prop="status" :label="t('dedit.status')" width="100" />
        <el-table-column prop="created_by" :label="t('dedit.createdBy')" />
        <el-table-column :label="t('dedit.actions')" width="90">
          <template #default="{ row }">
            <el-button link :disabled="row.current || row.status === 'draft'"
                       @click="rollback(row)">{{ t("dedit.rollback") }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>
    <chart-gallery v-model="galleryOpen" @select="addFromGallery" />

    <lineage-drawer v-model="lineageOpen" :asset-id="id" />
    <governance-drawer v-model="governanceOpen" :asset-id="id" />
    <drill-drawer v-model="drillOpen" :asset-id="id" :widget="drill.widget"
                  :dimension="drill.dimension" :value="drill.value"
                  :params="paramValues" />
    <report-drawer v-model="reportOpen" :asset-id="id"
                   :published="published" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../api";
import { t } from "../i18n";
import FavoriteButton from "../components/FavoriteButton.vue";
import DashboardGrid from "../studio/dashboard/DashboardGrid.vue";
import DashboardFilters from "../studio/dashboard/DashboardFilters.vue";
import HistoryControls from "../components/HistoryControls.vue";
import ChartGallery from "../studio/dashboard/ChartGallery.vue";
import { bindHistoryKeys, useHistory } from "../composables/useHistory";
import DrillDrawer from "../studio/dashboard/DrillDrawer.vue";
import ReportDrawer from "../studio/dashboard/ReportDrawer.vue";
import ShareDialog from "../studio/share/ShareDialog.vue";
import LineageDrawer from "../components/LineageDrawer.vue";
import GovernanceDrawer from "../components/GovernanceDrawer.vue";
import { useDraftSafety } from "../draftSafety";

const route = useRoute();
const id = Number(route.params.id);
const name = ref("");
const published = ref(false);
const content = ref({ columns: 12, row_height: 80, params: [],
                      widgets: [] });
const galleryOpen = ref(false);
const history = useHistory(content);
const { canUndo, canRedo } = history;
bindHistoryKeys(history);
const paramValues = ref({});
const paramTypes = ["string", "number", "date", "bool"];
const ops = ["=", "!=", ">", ">=", "<", "<=", "in", "like",
             "is null", "is not null"];
const data = ref({});
const selected = ref(null);
const metrics = ref([]);
const datasets = ref([]);
const metricContent = ref(null);
const loadingData = ref(false);
const versions = ref([]);
const versionsOpen = ref(false);
const lineageOpen = ref(false);
const governanceOpen = ref(false);
const drillOpen = ref(false);
const drill = ref({ widget: null, dimension: null, value: null });
const reportOpen = ref(false);
const draftVersion = ref(null);
const dirty = ref(false);
function addFromGallery(type) {
  add({ type });
}

const types = computed(() => [
  { type: "card", label: t("dedit.typeCard") },
  { type: "line", label: t("dedit.typeLine") },
  { type: "bar", label: t("dedit.typeBar") },
  { type: "area", label: t("dedit.typeArea") },
  { type: "pie", label: t("dedit.typePie") },
  { type: "map", label: t("dedit.typeMap") },
  { type: "pivot", label: t("dedit.typePivot") },
  { type: "table", label: t("dedit.typeTable") },
  { type: "text", label: t("dedit.text") },
]);

const metricDims = computed(() => modelDims(metricContent.value));
const isChart = computed(
  () => ["line", "bar", "area", "pie", "map"].includes(
    selected.value?.type));
const filterColumns = computed(() => {
  const wid = selected.value?.id;
  return data.value?.[wid]?.columns || [];
});
const valueOptions = computed(() => {
  const m = metricContent.value;
  if (!m) return [];
  const alias = (m.measure || {}).as || "value";
  return [...new Set([...modelDims(m), alias])];
});

function modelDims(content) {
  if (!content) return [];
  const dims = [...(content.dimensions || [])];
  const column = content.time?.column;
  if (column && !dims.includes(column)) dims.push(column);
  return dims;
}

async function load() {
  const a = await api.get(`/dashboards/${id}`);
  name.value = a.name;
  draftVersion.value = a.draft_version;
  published.value = Boolean(a.published);
  const selId = selected.value?.id;
  const draft = a.draft || {};
  content.value = {
    columns: draft.columns || 12,
    row_height: draft.row_height || 80,
    params: draft.params || [],
    widgets: draft.widgets || [],
  };
  for (const widget of content.value.widgets) {
    if (!widget.format) {
      widget.format = { legend: true, labels: false, smooth: true,
                        numberFormat: "auto" };
    }
  }
  history.reset();
  resetParams();
  selected.value = selId
    ? content.value.widgets.find((w) => w.id === selId) || null
    : null;
  metrics.value = ((await api.get("/metrics?page_size=200")).items || [])
    .filter((m) => m.published);
  datasets.value = ((await api.get("/datasets?page_size=200")).items || [])
    .filter((d) => d.published);
  if (selected.value) await loadMetric();
  if (content.value.widgets.length) await refresh();
  draftGuard.reset();
}

function add(ty) {
  const y = content.value.widgets.reduce(
    (m, w) => Math.max(m, w.y + w.h), 0);
  const widget = {
    id: `w_${Date.now()}_${content.value.widgets.length}`,
    type: ty.type,
    title: ty.label,
    x: 0, y, w: ty.type === "card" || ty.type === "text" ? 3 : 6,
    h: ty.type === "card" || ty.type === "text" ? 2 : 4,
    filters: [],
    format: { legend: true, labels: false, smooth: true,
              numberFormat: "auto" },
  };
  if (["card", "line", "bar", "area", "pie", "map"].includes(ty.type)) {
    widget.metric_id = metrics.value[0]?.id || null;
    if (["line", "bar", "area", "pie", "map"].includes(ty.type)) {
      widget.dimension = "";
    }
  }
  if (ty.type === "map") {
    widget.geo_json = null;
    widget.name_property = "name";
  }
  if (ty.type === "pivot") {
    widget.metric_id = metrics.value[0]?.id || null;
    widget.row_dimension = "";
    widget.column_dimension = "";
  }
  if (ty.type === "table") {
    widget.dataset_id = datasets.value[0]?.id || null;
    widget.limit = 100;
  }
  if (ty.type === "text") widget.text = t("dedit.text");
  content.value.widgets.push(widget);
  selected.value = widget;
  dirty.value = true;
  loadMetric();
}

function selectWidget(w) {
  selected.value = w;
  loadMetric();
}

function chooseTableMetric() {
  if (selected.value) selected.value.dataset_id = null;
  loadMetric();
}

function removeWidget() {
  if (!selected.value) return;
  const id = selected.value.id;
  content.value.widgets = content.value.widgets.filter((w) => w.id !== id);
  delete data.value[id];
  selected.value = null;
  dirty.value = true;
}

function loadGeo(uploadFile) {
  const file = uploadFile?.raw;
  if (!file) return;
  if (file.size > 1500000) {
    ElMessage.error(t("dedit.mapTooLarge"));
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const geo = JSON.parse(String(reader.result || ""));
      if (geo.type !== "FeatureCollection"
          || !Array.isArray(geo.features) || !geo.features.length) {
        throw new Error("invalid");
      }
      selected.value.geo_json = geo;
      dirty.value = true;
    } catch (e) {
      ElMessage.error(t("dedit.mapInvalid"));
    }
  };
  reader.readAsText(file);
}

async function loadMetric() {
  metricContent.value = null;
  const mid = selected.value?.metric_id;
  const wid = selected.value?.id;
  if (!mid) return;  try {
    const m = await api.get(`/metrics/${mid}`);
    if (!selected.value || selected.value.id !== wid
        || selected.value.metric_id !== mid) return;
    const content = m.published || m.draft;
    metricContent.value = content;
    const dims = modelDims(content);
    const alias = (content?.measure || {}).as || "value";
    const cols = [...dims, alias];
    if (!selected.value.value_column
        || !cols.includes(selected.value.value_column)) {
      selected.value.value_column = alias;
    }
    if (selected.value.dimension
        && !dims.includes(selected.value.dimension)) {
      selected.value.dimension = "";
    }
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function refresh() {
  loadingData.value = true;
  try {
    const r = await api.post(`/dashboards/${id}/data`, {
      limit: 100, params: paramValues.value, content: content.value,
    });
    data.value = r.widgets || {};
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loadingData.value = false;
  }
}

function resetParams() {
  const values = {};
  for (const p of content.value.params || []) {
    if (p.name) values[p.name] = p.default ?? "";
  }
  paramValues.value = values;
}

function resetFilterParams() {
  resetParams();
  refresh();
}

function setParams(p) {
  paramValues.value = { ...p };
}

function onCanvasChangeEnd() {
  history.commit();
  history.resume();
}

function onFilter({ param, value }) {
  if (!param) return;
  paramValues.value = { ...paramValues.value, [param]: value };
  refresh();
}

function onDrill(context) {
  drill.value = context;
  drillOpen.value = true;
}

function addParam() {
  const used = new Set((content.value.params || []).map((p) => p.name));
  let n = (content.value.params || []).length + 1;
  while (used.has(`p${n}`)) n += 1;
  content.value.params = content.value.params || [];
  content.value.params.push({ name: `p${n}`, type: "string",
                              default: "", required: false });
  resetParams();
}

function removeParam(i) {
  const p = content.value.params[i];
  content.value.params.splice(i, 1);
  for (const w of content.value.widgets) {
    w.filters = (w.filters || []).filter((f) => f.param !== p.name);
    if (w.emit?.param === p.name) w.emit = null;
  }
  resetParams();
}

function addFilter() {
  if (!selected.value) return;
  selected.value.filters = selected.value.filters || [];
  selected.value.filters.push({
    column: filterColumns.value[0] || "",
    op: "=",
    param: content.value.params[0]?.name || "",
  });
}

function removeFilter(i) {
  selected.value.filters.splice(i, 1);
}

function setInteractionType(type) {
  if (!selected.value) return;
  if (type === "filter") {
    selected.value.interaction = null;
    return;
  }
  selected.value.interaction = { type, url: "" };
}

function enableEmit() {
  if (!selected.value) return;
  selected.value.emit = {
    param: content.value.params[0]?.name || "",
    from: isChart.value
      ? (selected.value.dimension || "")
      : (filterColumns.value[0] || ""),
  };
}

function syncEmit() {
  if (selected.value?.emit && isChart.value) {
    selected.value.emit.from = selected.value.dimension || "";
  }
}

async function save(silent = false) {
  try {
    const body = { content: content.value };
    if (draftVersion.value !== null) body.base_version = draftVersion.value;
    const result = await api.put(`/dashboards/${id}/draft`, body);
    draftVersion.value = result.version;
    dirty.value = false;
    if (!silent) ElMessage.success(t("dedit.savedDraft"));
    return true;
  } catch (e) {
    if (/draft changed/i.test(e.message || "")) {
      ElMessageBox.confirm(t("draft.conflict"), t("draft.conflictTitle"),
        { type: "warning" })
        .then(() => load()).catch(() => {});
    } else if (!silent) {
      ElMessage.error(errMsg(e));
    }
    return false;
  }
}

const draftGuard = useDraftSafety({ content, save });

async function rename() {
  try {
    await api.put(`/dashboards/${id}`, { name: name.value });
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function validate() {
  try {
    const r = await api.post(`/dashboards/${id}/validate`,
                             { content: content.value });
    if (r.valid) ElMessage.success(t("dedit.validated"));
    else ElMessage.error(r.errors.map((e) => e.message).join("; "));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function publish() {
  const ok = await save();
  if (!ok) return;
  try {
    await api.applyChange("publish_dashboard", id);
    await load();
    ElMessage.success(t("dedit.published"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function loadVersions() {
  versions.value = await api.get(`/dashboards/${id}/versions`);
}

async function rollback(row) {
  try {
    await ElMessageBox.confirm(
      t("dedit.rollbackConfirm").replace("{version}", row.version),
      t("dedit.rollbackTitle"));
    await api.applyChange("rollback_dashboard", id, { version: row.version });
    await load();
    await loadVersions();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

onMounted(load);
</script>

<style scoped>
.dash-page { height: calc(100vh - 104px); display: flex; flex-direction: column;
             background: #f8fafc; border: 1px solid #e5e7eb;
             border-radius: 10px; overflow: hidden; }
.head { height: 52px; display: flex; align-items: center; gap: 8px;
        padding: 0 12px; background: #fff; border-bottom: 1px solid #e5e7eb; }
.spacer { flex: 1; }
.body { flex: 1; display: grid; grid-template-columns: 200px 1fr 340px;
        min-height: 0; }
.palette { background: #fff; border-right: 1px solid #e5e7eb; padding: 10px; }
.palette .label { font-size: 13px; font-weight: 600; margin-bottom: 8px; }
.palette .add { width: 100%; margin: 0 0 6px; }
.hint { color: #6b7280; font-size: 11px; margin-top: 10px; }
.canvas { overflow: auto; padding: 10px; }
.config { background: #fff; border-left: 1px solid #e5e7eb; overflow: auto;
          padding: 12px; }
.config-head { display: flex; justify-content: space-between; align-items: center; }
h4 { margin: 0 0 12px; font-size: 13px; }
.layout { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; }
.param-row { display: flex; gap: 3px; align-items: center;
             margin-bottom: 4px; flex-wrap: wrap; }
.param-row :deep(.el-input) { width: 78px; }
.filter-list { width: 100%; }
.filter-row { display: flex; gap: 3px; align-items: center;
              margin-bottom: 4px; flex-wrap: wrap; }
.map-hint { margin-left: 8px; color: #6b7280; font-size: 12px; }
</style>
