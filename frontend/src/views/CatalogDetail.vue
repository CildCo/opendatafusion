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
      <el-button v-if="canCreate" @click="scanPii" :loading="pii.loading">
        {{ t("cat.piiScan") }}
      </el-button>
      <el-button @click="governanceOpen = true">{{ t("gov.button") }}</el-button>
      <el-button v-if="canCreate" @click="createInterface">
        {{ t("catd.createApi") }}
      </el-button>
      <el-button @click="tagDialog = true">{{ t("cat.tag") }}</el-button>
      <el-button :loading="loading" @click="load">{{ t("cat.refresh") }}</el-button>
    </div>

    <el-alert v-if="notFound" :title="t('catd.notFound')" type="warning"
              :closable="false" />

    <div v-else class="detail-layout">
    <el-card shadow="never" class="card">
      <div class="summary">
        <div class="summary-main">
          <div class="summary-title">
            {{ detail.schema }}.{{ detail.table }}
            <el-tag v-if="detail.domain_name" size="small" type="success">
              {{ detail.domain_name }}
            </el-tag>
          </div>
          <div class="summary-sub">
            {{ detail.datasource_name || "-" }}
            <span v-if="detail.datasource_kind">· {{ detail.datasource_kind }}</span>
          </div>
          <div class="meta">
            <el-tag v-for="tag in detail.tags || []" :key="tag" size="small"
                    type="info" closable @close="detachTag(tag)">
              {{ tag }}
            </el-tag>
            <span v-if="!(detail.tags || []).length" class="muted">
              {{ t("cat.noTags") }}
            </span>
          </div>
        </div>
        <div class="summary-stats">
          <div class="stat">
            <b>{{ stats.column_count }}</b><span>{{ t("catd.columnCount") }}</span>
          </div>
          <div class="stat">
            <b>{{ stats.rule_count }}</b><span>{{ t("catd.ruleCount") }}</span>
          </div>
          <div class="stat">
            <b>{{ (detail.metrics || []).length }}</b>
            <span>{{ t("catd.metricsUsedBy") }}</span>
          </div>
          <div class="stat">
            <b>{{ detail.comments?.open || 0 }}</b>
            <span>{{ t("catd.openComments") }}</span>
          </div>
          <div class="stat">
            <el-tag v-if="stats.last_quality" size="small"
                    :type="stats.last_quality.status === 'pass'
                      ? 'success' : 'danger'">
              {{ stats.last_quality.status === "pass"
                ? t("catd.pass") : t("catd.fail") }}
            </el-tag>
            <span>{{ t("catd.lastQuality") }}</span>
          </div>
        </div>
      </div>
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
            <el-descriptions-item :label="t('catd.metricsUsedBy')" :span="2">
              <template v-if="(detail.metrics || []).length">
                <el-tag v-for="m in detail.metrics" :key="m.id" size="small"
                        class="metric-link"
                        @click="$router.push(`/metrics/${m.id}`)">
                  {{ m.name }}
                </el-tag>
              </template>
              <span v-else class="muted">{{ t("catd.noMetrics") }}</span>
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
                               :label="c" min-width="140">
                <template #default="{ row }">
                  <el-popover v-if="isJsonValue(row[c])" placement="left"
                              :width="340" trigger="click">
                    <template #reference>
                      <el-button link>{{ t("interface.rawJson") }}</el-button>
                    </template>
                    <json-view :value="row[c]" />
                  </el-popover>
                  <span v-else-if="row[c] === null || row[c] === undefined"
                        class="muted">-</span>
                  <span v-else class="cell-text">{{ row[c] }}</span>
                </template>
              </el-table-column>
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
          <div class="preview-bar">
            <el-input v-model="columnQuery" size="small" clearable
                      style="width: 260px"
                      :placeholder="t('catd.columnFilter')" />
            <span class="muted">
              {{ filteredColumns.length }} / {{ (detail.columns || []).length }}
            </span>
          </div>
          <el-table :data="filteredColumns" size="small"
                    @row-click="openColumn">
            <el-table-column prop="name" :label="t('cat.columns')" />
            <el-table-column prop="type" :label="t('cat.type')" width="200" />
            <el-table-column :label="t('catd.classification')" width="130">
              <template #default="{ row }">
                <el-tag v-if="row.classification" size="small" type="warning">
                  {{ row.classification }}
                </el-tag>
                <span v-else class="muted">-</span>
              </template>
            </el-table-column>
            <el-table-column :label="t('catd.maskType')" width="130">
              <template #default="{ row }">
                <span v-if="row.mask_type">{{ row.mask_type }}</span>
                <span v-else class="muted">-</span>
              </template>
            </el-table-column>
            <el-table-column :label="t('catd.columnRules')" width="110">
              <template #default="{ row }">
                {{ rulesFor(row.name).length }}
              </template>
            </el-table-column>
            <el-table-column width="80">
              <template #default="{ row }">
                <el-button link @click.stop="openColumn(row)">
                  {{ t("catd.viewColumn") }}
                </el-button>
              </template>
            </el-table-column>
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
            <el-table-column :label="t('quality.enabled')" width="110">
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
          <lineage-explorer :focus-ref="lineageRef" :height="340" />
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
        <el-tab-pane :label="t('catd.comments')" name="comments">
          <div class="comment-box">
            <el-input v-model="newComment" type="textarea" :rows="3"
                      :placeholder="t('catd.commentPlaceholder')" />
            <el-button type="primary" :loading="commentSaving"
                       :disabled="!newComment.trim()" @click="submitComment">
              {{ t("catd.commentSubmit") }}
            </el-button>
          </div>
          <div class="preview-bar">
            <el-radio-group v-model="commentFilter" size="small"
                            @change="loadComments">
              <el-radio-button value="open">
                {{ t("catd.open") }}
              </el-radio-button>
              <el-radio-button value="resolved">
                {{ t("catd.resolved") }}
              </el-radio-button>
              <el-radio-button value="">{{ t("catd.allComments") }}</el-radio-button>
            </el-radio-group>
          </div>
          <div v-for="row in comments" :key="row.id" class="comment"
               :class="{ resolved: row.status === 'resolved' }">
            <div class="comment-head">
              <b>{{ row.actor }}</b>
              <span class="muted">{{ fmt(row.created_at) }}</span>
              <el-tag v-if="row.status === 'resolved'" size="small"
                      type="success">{{ t("catd.resolved") }}</el-tag>
              <div class="spacer" />
              <el-button link size="small" @click="toggleComment(row)">
                {{ row.status === "resolved"
                  ? t("catd.reopen") : t("catd.resolve") }}
              </el-button>
            </div>
            <div class="comment-body">{{ row.body }}</div>
          </div>
          <el-empty v-if="!comments.length"
                    :description="t('catd.noComments')" :image-size="60" />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <aside class="rail">
      <section class="rail-card">
        <h4>{{ t("catd.governance") }}</h4>
        <div class="rail-row">
          <span>{{ t("gov.domain") }}</span>
          <b>{{ detail.domain_name || t("cat.ungrouped") }}</b>
        </div>
        <div class="rail-row">
          <span>{{ t("catd.ruleCount") }}</span><b>{{ stats.rule_count }}</b>
        </div>
        <div class="rail-row">
          <span>{{ t("catd.classified") }}</span>
          <b>{{ classifiedColumns.length }}</b>
        </div>
        <div class="rail-row">
          <span>{{ t("catd.lastQuality") }}</span>
          <el-tag v-if="stats.last_quality" size="small"
                  :type="stats.last_quality.status === 'pass'
                    ? 'success' : 'danger'">
            {{ stats.last_quality.status === "pass"
              ? t("catd.pass") : t("catd.fail") }}
          </el-tag>
          <span v-else class="muted">{{ t("catd.never") }}</span>
        </div>
        <el-button size="small" style="width: 100%; margin-top: 8px"
                   @click="$router.push('/quality')">
          {{ t("catd.goQuality") }}
        </el-button>
      </section>

      <section class="rail-card">
        <h4>{{ t("cat.glossary") }}</h4>
        <div v-for="term in relatedTerms" :key="term.id" class="rail-term">
          <b>{{ term.term }}</b>
          <p>{{ term.definition || t("cat.noDefinition") }}</p>
        </div>
        <p v-if="!relatedTerms.length" class="muted">
          {{ t("cat.glossaryEmpty") }}
        </p>
      </section>

      <section class="rail-card">
        <h4>{{ t("catd.collaboration") }}</h4>
        <div class="rail-row">
          <span>{{ t("catd.openComments") }}</span>
          <b>{{ detail.comments?.open || 0 }}</b>
        </div>
        <div class="rail-row">
          <span>{{ t("catd.allComments") }}</span>
          <b>{{ detail.comments?.total || 0 }}</b>
        </div>
        <div class="rail-row">
          <span>{{ t("catd.lastActivity") }}</span>
          <span class="muted">{{ stats.last_activity_at
            ? fmt(stats.last_activity_at) : t("catd.never") }}</span>
        </div>
        <el-button size="small" style="width: 100%; margin-top: 8px"
                   @click="tab = 'comments'">
          {{ t("catd.goComments") }}
        </el-button>
      </section>
    </aside>
    </div>

    <el-drawer v-model="columnOpen" :title="selectedColumn?.name"
               size="440px">
      <template v-if="selectedColumn">
        <el-descriptions :column="1" border>
          <el-descriptions-item :label="t('cat.columns')">
            {{ selectedColumn.name }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('cat.type')">
            {{ selectedColumn.type || "-" }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('catd.classification')">
            {{ selectedColumn.classification || "-" }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('catd.maskType')">
            {{ selectedColumn.mask_type || "-" }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('catd.exemptRoles')">
            {{ (selectedColumn.exempt_roles || []).join(", ") || "-" }}
          </el-descriptions-item>
        </el-descriptions>
        <h4 class="drawer-head">{{ t("catd.columnRules") }}</h4>
        <el-table :data="rulesFor(selectedColumn.name)" size="small">
          <el-table-column prop="name" :label="t('quality.name')" />
          <el-table-column prop="kind" :label="t('quality.kind')" width="140" />
        </el-table>
        <el-empty v-if="!rulesFor(selectedColumn.name).length"
                  :description="t('catd.noColumnRules')" :image-size="50" />
        <el-button size="small" style="margin-top: 12px"
                   @click="$router.push('/quality')">
          {{ t("catd.goQuality") }}
        </el-button>
      </template>
    </el-drawer>

    <el-dialog v-model="pii.open" :title="t('cat.piiTitle')" width="640px">
      <p class="hint">
        {{ t("cat.piiIntro").replace("{n}", pii.sampled) }}
      </p>
      <el-table :data="pii.rows" size="small">
        <el-table-column prop="column" :label="t('cat.piiColumn')" />
        <el-table-column prop="classification" :label="t('cat.piiClass')" width="120" />
        <el-table-column prop="detected_as" :label="t('cat.piiType')" width="110" />
        <el-table-column prop="evidence" :label="t('cat.piiEvidence')" width="110" />
        <el-table-column :label="t('cat.piiMasked')" width="90">
          <template #default="{ row }">{{ row.masked ? t("cat.yes") : t("cat.no") }}</template>
        </el-table-column>
      </el-table>
      <empty-state v-if="!pii.rows.length" :title="t('cat.piiEmpty')"
                   :image-size="60" />
      <template #footer>
        <el-button @click="pii.open = false">{{ t("cat.cancel") }}</el-button>
        <el-button type="primary" :disabled="!pii.rows.length"
                   :loading="pii.applying" @click="applyPii">
          {{ t("cat.piiApply") }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="tagDialog" :title="t('cat.tag')" width="420px">
      <el-input v-model="newTag" :placeholder="t('cat.newTagPlaceholder')" />
      <template #footer>
        <el-button @click="tagDialog = false">{{ t("cat.cancel") }}</el-button>
        <el-button type="primary" @click="attachTag">{{ t("cat.save") }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="propsOpen" :title="t('cat.propsTitle')" width="600px">
      <p class="muted" style="margin-top: 0">{{ t("cat.propsHint") }}</p>
      <property-editor v-model="props.values"
                       :suggestions="propertySuggestions" />
      <template #footer>
        <el-button @click="propsOpen = false">{{ t("cat.cancel") }}</el-button>
        <el-button type="primary" :loading="props.saving"
                   @click="saveProperties">{{ t("cat.submit") }}</el-button>
      </template>
    </el-dialog>
    <governance-drawer v-model="governanceOpen" :asset-id="Number(route.params.id)"
                       mode="table" />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { api, canWrite, errMsg, getProject } from "../api";
import { fmtDate, t } from "../i18n";
import LineageExplorer from "../components/LineageExplorer.vue";
import JsonView from "../components/JsonView.vue";
import PropertyEditor from "../components/PropertyEditor.vue";
import GovernanceDrawer from "../components/GovernanceDrawer.vue";

function tr(key, vars = {}) {
  return Object.entries(vars).reduce(
    (s, [k, v]) => s.split(`{${k}}`).join(v ?? ""), t(key));
}

const route = useRoute();
const router = useRouter();
const canCreate = canWrite();
const datasetId = computed(() => Number(route.params.id));
const detail = ref({});
const notFound = ref(false);
const tab = ref("overview");
const governanceOpen = ref(false);
const loading = ref(false);
const rules = ref([]);
const history = ref([]);
const terms = ref([]);
const comments = ref([]);
const commentFilter = ref("open");
const newComment = ref("");
const commentSaving = ref(false);
const columnQuery = ref("");
const columnOpen = ref(false);
const selectedColumn = ref(null);

const lineageRef = computed(() => detail.value.datasource_id
  ? `${detail.value.datasource_id}:${detail.value.table}` : "");

const filteredColumns = computed(() => {
  const needle = columnQuery.value.trim().toLowerCase();
  const rows = detail.value.columns || [];
  if (!needle) return rows;
  return rows.filter((row) =>
    `${row.name} ${row.type || ""} ${row.classification || ""}`
      .toLowerCase().includes(needle));
});

const classifiedColumns = computed(() =>
  (detail.value.columns || []).filter((row) => row.classification));

const relatedTerms = computed(() => {
  const domain = detail.value.domain_id;
  if (!domain) return terms.value;
  return terms.value.filter((row) => row.domain_id === domain);
});

const limit = ref(20);
const profileSample = ref(50000);
const profile = reactive({ loading: false, error: "", rows: 0, ms: 0,
                           columns: [] });
const sample = reactive({ loading: false, error: "", rows: [],
                          columns: [], row_count: 0, ms: 0, truncated: false });
const tagDialog = ref(false);
const pii = reactive({ open: false, loading: false, applying: false,
                       rows: [], sampled: 0 });
const newTag = ref("");
const allTags = ref([]);
const propsOpen = ref(false);
const props = reactive({ saving: false, values: {} });

const propertySuggestions = [
  { key: "gc.enabled", value: "true" },
  { key: "write.metadata.delete-after-commit.enabled", value: "true" },
  { key: "write.metadata.previous-versions-max", value: "100" },
  { key: "write.target-file-size-bytes", value: "134217728" },
  { key: "write.distribution-mode", value: "hash" },
  { key: "write.parquet.compression-codec", value: "zstd" },
  { key: "format-version", value: "2" },
];

const stats = computed(() => detail.value.stats || {
  column_count: 0, rule_count: 0, last_quality: null, last_activity_at: null,
});
const isLakehouse = computed(() => detail.value.datasource_kind === "trino");
const loaded = { preview: false, quality: false, impact: false,
                 history: false, profile: false };

const fmt = fmtDate;

function createInterface() {
  router.push({ path: "/apis",
                query: { new: "1", ds: detail.value.datasource_id,
                         table: detail.value.table } });
}

function isJsonValue(value) {
  return value !== null && typeof value === "object";
}

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
    const rows = (await api.get("/quality/rules?page_size=200")).items || [];
    rules.value = rows.filter((r) => r.dataset_id === datasetId.value);
  } catch {
    rules.value = [];
  }
}

function rulesFor(name) {
  return rules.value.filter((row) => row.column === name);
}

function openColumn(row) {
  selectedColumn.value = row;
  columnOpen.value = true;
  if (!rules.value.length) loadRules();
}

async function loadComments() {
  try {
    const status = commentFilter.value
      ? `?status=${commentFilter.value}` : "";
    comments.value = await api.get(
      `/catalog/datasets/${datasetId.value}/comments${status}`);
  } catch {
    comments.value = [];
  }
}

async function submitComment() {
  if (!newComment.value.trim()) return;
  commentSaving.value = true;
  try {
    await api.post(`/catalog/datasets/${datasetId.value}/comments`,
                   { body: newComment.value });
    newComment.value = "";
    await loadComments();
    await load();
    ElMessage.success(t("catd.commentAdded"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    commentSaving.value = false;
  }
}

async function toggleComment(row) {
  try {
    await api.patch(`/catalog/comments/${row.id}`, {
      status: row.status === "resolved" ? "open" : "resolved",
    });
    await loadComments();
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function loadTerms() {
  try {
    const out = await api.get(
      `/governance/terms?project_id=${getProject() || 1}`);
    terms.value = out.items || [];
  } catch {
    terms.value = [];
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
  if (name === "quality" || name === "fields") loadRules();
  if (name === "comments") loadComments();
  if (name === "history") loadHistory();
});

async function loadTags() {
  try {
    allTags.value = await api.get("/catalog/tags");
  } catch {
    allTags.value = [];
  }
}

async function scanPii() {
  pii.loading = true;
  try {
    const out = await api.post(
      `/catalog/datasets/${route.params.id}/pii-scan?apply=false`);
    pii.rows = out.findings || [];
    pii.sampled = out.sampled_rows || 0;
    pii.open = true;
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    pii.loading = false;
  }
}

async function applyPii() {
  pii.applying = true;
  try {
    await api.post(`/catalog/datasets/${route.params.id}/pii-scan?apply=true`);
    ElMessage.success(t("cat.piiApplied"));
    pii.open = false;
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    pii.applying = false;
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
  props.values = { "gc.enabled": "true" };
  propsOpen.value = true;
}

async function saveProperties() {
  const properties = Object.fromEntries(
    Object.entries(props.values).filter(([key]) => key.trim()));
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
  await loadTerms();
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
.metric-link { cursor: pointer; margin-right: 6px; }
.prop-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.detail-layout { display: grid; grid-template-columns: minmax(0, 1fr) 280px;
                 gap: 16px; align-items: start; }
.summary { display: flex; justify-content: space-between; gap: 20px;
           padding: 4px 4px 16px; border-bottom: 1px solid #eef2f7;
           margin-bottom: 8px; flex-wrap: wrap; }
.summary-title { font-size: 18px; font-weight: 700; color: #0f172a;
                 display: flex; align-items: center; gap: 8px; }
.summary-sub { color: #64748b; font-size: 12px; margin: 4px 0 8px; }
.summary-stats { display: flex; gap: 18px; flex-wrap: wrap; }
.stat { display: flex; flex-direction: column; gap: 3px; min-width: 66px; }
.stat b { font-size: 20px; color: #0f172a; }
.stat span { font-size: 11px; color: #64748b; }
.rail { display: flex; flex-direction: column; gap: 12px; }
.rail-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px;
             padding: 12px; }
.rail-card h4 { margin: 0 0 8px; font-size: 12px; color: #334155; }
.rail-row { display: flex; justify-content: space-between; gap: 10px;
            align-items: center; font-size: 12px; color: #475569;
            padding: 4px 0; }
.rail-row b { color: #0f172a; }
.rail-term { padding: 5px 0; border-top: 1px dashed #eef2f7; }
.rail-term b { font-size: 12px; color: #0f172a; }
.rail-term p { margin: 2px 0 0; font-size: 11px; color: #64748b; }
.comment-box { display: flex; flex-direction: column; gap: 8px;
               align-items: flex-end; margin-bottom: 12px; }
.comment-box :deep(.el-textarea) { width: 100%; }
.comment { border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px;
           margin-bottom: 8px; }
.comment.resolved { background: #f8fafc; opacity: 0.85; }
.comment-head { display: flex; align-items: center; gap: 8px;
                font-size: 12px; }
.comment-body { margin-top: 6px; font-size: 13px; color: #334155;
                white-space: pre-wrap; }
.drawer-head { margin: 16px 0 8px; font-size: 13px; }
@media (max-width: 1100px) {
  .detail-layout { grid-template-columns: 1fr; }
}
</style>
