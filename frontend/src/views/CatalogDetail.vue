<template>
  <div class="page">
    <div class="toolbar">
      <el-button link @click="$router.push('/catalog')">
        ← {{ t("catd.back") }}
      </el-button>
      <span class="title">
        {{ detail.schema }}.{{ detail.table }}
      </span>
      <el-tag v-if="detail.datasource_kind" size="small" effect="plain">
        {{ detail.datasource_kind }}
      </el-tag>
      <div class="spacer" />
      <el-button v-if="isLakehouse" @click="openProperties">
        {{ t("cat.tableProperties") }}
      </el-button>
      <el-button @click="tagDialog = true">{{ t("cat.tag") }}</el-button>
      <el-button :loading="loading" @click="load">{{ t("cat.refresh") }}</el-button>
    </div>

    <el-alert v-if="notFound" :title="t('catd.notFound')" type="warning"
              :closable="false" />

    <el-card v-else shadow="never" class="card">
      <el-tabs v-model="tab">
        <el-tab-pane :label="t('catd.overview')" name="overview">
          <el-descriptions :column="2" border>
            <el-descriptions-item :label="t('catd.source')">
              {{ detail.datasource_name || "-" }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('catd.kind')">
              {{ detail.datasource_kind || "-" }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('catd.schema')">
              {{ detail.schema }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('catd.table')">
              {{ detail.table }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('catd.columnCount')">
              {{ stats.column_count }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('catd.ruleCount')">
              {{ stats.rule_count }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('catd.lastQuality')">
              <template v-if="stats.last_quality">
                <el-tag size="small"
                        :type="stats.last_quality.status === 'pass'
                          ? 'success' : 'danger'">
                  {{ stats.last_quality.status === "pass"
                    ? t("catd.pass") : t("catd.fail") }}
                </el-tag>
                <span class="muted time">{{ fmt(stats.last_quality.at) }}</span>
              </template>
              <span v-else class="muted">{{ t("catd.never") }}</span>
            </el-descriptions-item>
            <el-descriptions-item :label="t('catd.lastActivity')">
              <span v-if="stats.last_activity_at">{{ fmt(stats.last_activity_at) }}</span>
              <span v-else class="muted">{{ t("catd.never") }}</span>
            </el-descriptions-item>
          </el-descriptions>
          <div class="meta">
            <el-tag v-for="tag in detail.tags || []" :key="tag" size="small"
                    type="info" closable @close="detachTag(tag)">
              {{ tag }}
            </el-tag>
            <span v-if="!(detail.tags || []).length" class="muted">
              {{ t("cat.noTags") }}
            </span>
          </div>
        </el-tab-pane>

        <el-tab-pane :label="t('catd.preview')" name="preview">
          <div class="preview-bar">
            <span class="muted">{{ tr("catd.sampleHint", { n: limit }) }}</span>
            <div class="spacer" />
            <el-select v-model="limit" size="small" style="width: 110px">
              <el-option :value="20" :label="`20 ${t('catd.limit')}`" />
              <el-option :value="50" :label="`50 ${t('catd.limit')}`" />
              <el-option :value="100" :label="`100 ${t('catd.limit')}`" />
            </el-select>
            <el-button size="small" type="primary" :loading="sample.loading"
                       @click="loadSample">
              {{ t("catd.loadSample") }}
            </el-button>
          </div>
          <el-alert v-if="sample.error" :title="sample.error" type="error"
                    :closable="false" style="margin-top: 10px" />
          <template v-else-if="sample.rows.length">
            <div class="sample-head">
              <span class="muted">
                {{ sample.row_count }} {{ t("wb.rows") }} · {{ sample.ms }} ms
              </span>
              <el-tag v-if="sample.truncated" size="small" type="warning">
                {{ t("catd.truncated") }}
              </el-tag>
            </div>
            <el-table :data="sample.rows" size="small" border height="420">
              <el-table-column v-for="c in sample.columns" :key="c"
                               :prop="c" :label="c" min-width="140"
                               show-overflow-tooltip />
            </el-table>
          </template>
          <el-empty v-else :description="t('catd.noSample')" :image-size="70" />
        </el-tab-pane>

        <el-tab-pane :label="t('catd.profile')" name="profile">
          <div class="preview-bar">
            <span class="muted">
              {{ tr("catd.profileHint", { n: profileSample }) }}
            </span>
            <div class="spacer" />
            <el-select v-model="profileSample" size="small"
                       style="width: 130px">
              <el-option :value="5000" label="5,000" />
              <el-option :value="50000" label="50,000" />
              <el-option :value="200000" label="200,000" />
            </el-select>
            <el-button size="small" type="primary"
                       :loading="profile.loading" @click="runProfile">
              {{ t("catd.profileRun") }}
            </el-button>
          </div>
          <el-alert v-if="profile.error" :title="profile.error" type="error"
                    :closable="false" style="margin-bottom: 10px" />
          <template v-else-if="profile.columns.length">
            <div class="sample-head">
              <span class="muted">
                {{ tr("catd.profileRows", { n: profile.rows }) }} ·
                {{ profile.ms }} ms
              </span>
            </div>
            <el-table :data="profile.columns" size="small" border>
              <el-table-column prop="name" :label="t('catd.profileName')"
                               min-width="140" />
              <el-table-column prop="type" :label="t('catd.profileType')"
                               width="140" />
              <el-table-column prop="nulls" :label="t('catd.profileNulls')"
                               width="90" />
              <el-table-column :label="t('catd.profileNullRatio')" width="100">
                <template #default="{ row }">{{ row.null_ratio }}%</template>
              </el-table-column>
              <el-table-column prop="distinct"
                               :label="t('catd.profileDistinct')" width="110" />
              <el-table-column :label="t('catd.profileMin')" min-width="120">
                <template #default="{ row }">
                  <el-tag v-if="row.masked" size="small" type="info">
                    {{ t("catd.profileMasked") }}
                  </el-tag>
                  <span v-else>{{ row.min === null ? "-" : row.min }}</span>
                </template>
              </el-table-column>
              <el-table-column :label="t('catd.profileMax')" min-width="120">
                <template #default="{ row }">
                  <el-tag v-if="row.masked" size="small" type="info">
                    {{ t("catd.profileMasked") }}
                  </el-tag>
                  <span v-else>{{ row.max === null ? "-" : row.max }}</span>
                </template>
              </el-table-column>
            </el-table>
          </template>
          <el-empty v-else :description="t('catd.profileEmpty')"
                    :image-size="70" />
        </el-tab-pane>

        <el-tab-pane :label="t('catd.fields')" name="fields">
          <el-table :data="detail.columns || []" size="small">
            <el-table-column prop="name" :label="t('cat.columns')" />
            <el-table-column prop="type" :label="t('cat.type')" width="200" />
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="t('catd.quality')" name="quality">
          <div class="preview-bar">
            <span class="muted">
              {{ stats.rule_count }} {{ t("catd.ruleCount") }}
            </span>
            <div class="spacer" />
            <el-button size="small" @click="$router.push('/quality')">
              {{ t("catd.goQuality") }}
            </el-button>
          </div>
          <el-table :data="rules" size="small">
            <el-table-column prop="name" :label="t('quality.name')" />
            <el-table-column prop="kind" :label="t('quality.kind')" width="150" />
            <el-table-column prop="column" :label="t('quality.column')" width="160" />
            <el-table-column :label="t('iface.status')" width="110">
              <template #default="{ row }">
                <el-tag size="small" :type="row.enabled ? 'success' : 'info'">
                  {{ row.enabled ? t("catd.enabled") : t("catd.disabled") }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!rules.length" :description="t('catd.noRules')"
                    :image-size="60" />
        </el-tab-pane>

        <el-tab-pane :label="t('catd.impact')" name="impact">
          <div v-if="impact.edges.length">
            <div class="muted" style="margin-bottom: 8px">
              {{ tr("catd.downstream", { n: impact.edges.length }) }}
            </div>
            <div v-for="(e, i) in impact.edges" :key="'i' + i" class="edge">
              <span class="node-tag">{{ e.from }}</span>
              <el-icon><Right /></el-icon>
              <span class="node-tag dst">{{ e.to }}</span>
            </div>
            <div v-if="impact.column_edges.length" class="muted"
                 style="margin: 12px 0 6px">
              {{ tr("cat.columnImpact", { n: impact.column_edges.length }) }}
            </div>
            <div v-for="(e, i) in impact.column_edges" :key="'c' + i"
                 class="col-edge">
              <span>{{ e.from }}.{{ e.from_column }}</span>
              <el-icon><Right /></el-icon>
              <span>{{ e.to }}.{{ e.to_column }}</span>
            </div>
          </div>
          <el-empty v-else :description="t('catd.noImpact')" :image-size="70" />
        </el-tab-pane>

        <el-tab-pane :label="t('catd.history')" name="history">
          <p class="muted" style="margin-top: 0">{{ t("catd.historyHint") }}</p>
          <el-table :data="history" size="small">
            <el-table-column :label="t('catd.time')" width="190">
              <template #default="{ row }">{{ fmt(row.at) }}</template>
            </el-table-column>
            <el-table-column prop="actor" :label="t('catd.actor')" width="150" />
            <el-table-column prop="action" :label="t('catd.action')" width="200" />
            <el-table-column :label="t('catd.detail')" min-width="220">
              <template #default="{ row }">
                <span class="mono">{{ brief(row.detail) }}</span>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!history.length" :description="t('catd.emptyHistory')"
                    :image-size="60" />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog v-model="tagDialog" :title="t('cat.tag')" width="420px">
      <el-input v-model="newTag" :placeholder="t('cat.newTagPlaceholder')" />
      <template #footer>
        <el-button @click="tagDialog = false">{{ t("cat.cancel") }}</el-button>
        <el-button type="primary" @click="attachTag">{{ t("cat.save") }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="propsOpen" :title="t('cat.propsTitle')" width="600px">
      <p class="muted" style="margin-top: 0">{{ t("cat.propsHint") }}</p>
      <div v-for="(row, i) in props.rows" :key="i" class="prop-row">
        <el-input v-model="row.key" placeholder="gc.enabled" size="small" />
        <el-input v-model="row.value" placeholder="true" size="small" />
        <el-button link type="danger" size="small"
                   @click="props.rows.splice(i, 1)">{{ t("cat.delete") }}</el-button>
      </div>
      <el-button link @click="props.rows.push({ key: '', value: '' })">
        + {{ t("cat.addProperty") }}
      </el-button>
      <template #footer>
        <el-button @click="propsOpen = false">{{ t("cat.cancel") }}</el-button>
        <el-button type="primary" :loading="props.saving"
                   @click="saveProperties">{{ t("cat.submit") }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { ElMessage } from "element-plus";
import { Right } from "@element-plus/icons-vue";
import { api, errMsg, getProject } from "../api";
import { fmtDate, t } from "../i18n";

function tr(key, vars = {}) {
  return Object.entries(vars).reduce(
    (s, [k, v]) => s.split(`{${k}}`).join(v ?? ""), t(key));
}

const route = useRoute();
const datasetId = computed(() => Number(route.params.id));
const detail = ref({});
const notFound = ref(false);
const tab = ref("overview");
const loading = ref(false);
const rules = ref([]);
const history = ref([]);
const impact = reactive({ edges: [], column_edges: [] });
const limit = ref(20);
const profileSample = ref(50000);
const profile = reactive({ loading: false, error: "", rows: 0, ms: 0,
                           columns: [] });
const sample = reactive({ loading: false, error: "", rows: [],
                          columns: [], row_count: 0, ms: 0, truncated: false });
const tagDialog = ref(false);
const newTag = ref("");
const allTags = ref([]);
const propsOpen = ref(false);
const props = reactive({ saving: false, rows: [{ key: "", value: "" }] });

const stats = computed(() => detail.value.stats || {
  column_count: 0, rule_count: 0, last_quality: null, last_activity_at: null,
});
const isLakehouse = computed(() => detail.value.datasource_kind === "trino");
const loaded = { preview: false, quality: false, impact: false,
                 history: false, profile: false };

const fmt = fmtDate;

function brief(detailJson) {
  const text = JSON.stringify(detailJson || {});
  return text.length > 120 ? text.slice(0, 117) + "..." : text;
}

async function load() {
  loading.value = true;
  notFound.value = false;
  try {
    detail.value = await api.get(`/catalog/datasets/${datasetId.value}`);
  } catch (e) {
    notFound.value = true;
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

async function loadSample() {
  sample.loading = true;
  sample.error = "";
  try {
    const r = await api.get(
      `/catalog/datasets/${datasetId.value}/sample?limit=${limit.value}`);
    Object.assign(sample, r);
    sample.error = "";
  } catch (e) {
    sample.error = errMsg(e);
    sample.rows = [];
    sample.columns = [];
  } finally {
    sample.loading = false;
  }
}

async function runProfile() {
  profile.loading = true;
  profile.error = "";
  try {
    const out = await api.get(
      `/catalog/datasets/${datasetId.value}/profile?sample=${profileSample.value}`);
    profile.rows = out.rows;
    profile.ms = out.ms;
    profile.columns = out.columns;
  } catch (e) {
    profile.error = errMsg(e);
    profile.columns = [];
  } finally {
    profile.loading = false;
  }
}

async function loadRules() {
  try {
    const rows = await api.get("/quality/rules");
    rules.value = rows.filter((r) => r.dataset_id === datasetId.value);
  } catch {
    rules.value = [];
  }
}

async function loadImpact() {
  impact.edges = [];
  impact.column_edges = [];
  if (!detail.value.datasource_id || !detail.value.table) return;
  try {
    const ref = `${detail.value.datasource_id}:${detail.value.table}`;
    const r = await api.get(`/catalog/impact?ref=${encodeURIComponent(ref)}`);
    impact.edges = r.edges || [];
    impact.column_edges = r.column_edges || [];
  } catch {
    /* impact is advisory */
  }
}

async function loadHistory() {
  try {
    history.value = await api.get(
      `/catalog/datasets/${datasetId.value}/history`);
  } catch {
    history.value = [];
  }
}

watch(tab, (name) => {
  if (loaded[name]) return;
  loaded[name] = true;
  if (name === "profile") loaded.profile = true;
  if (name === "quality") loadRules();
  if (name === "impact") loadImpact();
  if (name === "history") loadHistory();
});

async function loadTags() {
  try {
    allTags.value = await api.get("/catalog/tags");
  } catch {
    allTags.value = [];
  }
}

async function attachTag() {
  if (!newTag.value) return;
  try {
    const created = await api.post("/catalog/tags", {
      project_id: getProject() || 1, name: newTag.value,
    });
    await api.post("/catalog/tags/attach", {
      dataset_id: datasetId.value, tag_id: created.id,
    });
    tagDialog.value = false;
    newTag.value = "";
    await load();
    await loadTags();
    ElMessage.success(t("cat.tagged"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function detachTag(name) {
  const tag = allTags.value.find((x) => x.name === name);
  if (!tag) return;
  try {
    await api.post("/catalog/tags/detach", {
      dataset_id: datasetId.value, tag_id: tag.id,
    });
    await load();
    ElMessage.success(t("cat.tagRemoved"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

function openProperties() {
  props.rows = [{ key: "gc.enabled", value: "true" }];
  propsOpen.value = true;
}

async function saveProperties() {
  const properties = Object.fromEntries(
    props.rows.filter((r) => r.key.trim())
      .map((r) => [r.key.trim(), r.value]));
  if (!Object.keys(properties).length) {
    ElMessage.warning(t("cat.propertiesRequired"));
    return;
  }
  props.saving = true;
  try {
    const out = await api.post(
      `/lakehouse/tables/${encodeURIComponent(detail.value.table)}/properties`,
      { datasource_id: detail.value.datasource_id,
        schema_name: detail.value.schema, properties });
    propsOpen.value = false;
    ElMessage.success(`${t("cat.propsSubmitted")} #${out.job_id}`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    props.saving = false;
  }
}

onMounted(async () => {
  await load();
  await loadTags();
});
</script>

<style scoped>
.card {
  border-radius: 12px;
  border: 1px solid #e5e7eb;
}
.title {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
}
.muted {
  color: #64748b;
  font-size: 12px;
}
.time { margin-left: 8px; }
.meta {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 14px;
}
.preview-bar {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 10px;
}
.sample-head {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 8px;
}
.edge {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  padding: 4px 0;
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
.col-edge {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #475569;
  padding: 3px 0;
}
.mono {
  font-family: Consolas, "Courier New", monospace;
  font-size: 11px;
}
.prop-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
</style>
