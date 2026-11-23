<template>
  <div class="page">
    <page-header icon="quality" :title="t('menu.quality')"
                 :intro="t('quality.intro')" />
    <div class="toolbar">
      <el-input v-model="q" :placeholder="t('quality.search')" clearable style="width: 220px"
                :prefix-icon="Search" />
      <div class="spacer" />
      <el-button @click="load" :loading="loading">{{ t("quality.refresh") }}</el-button>
      <el-button v-if="canEdit" type="primary" @click="openCreate">{{ t("quality.new") }}</el-button>
    </div>

    <div class="summary-row">
      <stat-tile icon="quality" :label="t('quality.rulesTotal')"
                 :value="summary.total" />
      <stat-tile icon="alert" :label="t('quality.rulesFailing')"
                 :value="summary.failing"
                 :tone="summary.failing ? 'danger' : 'success'" />
      <stat-tile icon="quality" :label="t('quality.avgPass')"
                 :value="summary.avg === null ? '-' : `${summary.avg}%`"
                 :tone="summary.avg === null ? ''
                   : summary.avg >= 90 ? 'success'
                   : summary.avg >= 60 ? 'warning' : 'danger'" />
    </div>

    <el-card class="card" shadow="never">
      <el-table :data="filtered" size="small" v-loading="loading">
        <el-table-column prop="id" :label="t('quality.id')" width="70" />
        <el-table-column :label="t('quality.name')" min-width="200">
          <template #default="{ row }">
            <span class="entity-cell">
              <entity-icon type="quality" :size="20" />
              <b>{{ row.name }}</b>
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="kind" :label="t('quality.kind')" width="120">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ kindLabel(row.kind) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="column" :label="t('quality.column')" width="140" />
        <el-table-column :label="t('quality.dataset')" min-width="160">
          <template #default="{ row }">{{ datasetName(row.dataset_id) }}</template>
        </el-table-column>
        <el-table-column :label="t('quality.schedule')" width="150">
          <template #default="{ row }">
            <span :class="{ muted: !row.schedule_cron }">
              {{ row.schedule_cron || "-" }}
            </span>
            <el-tag v-if="row.alert_on_fail" size="small" type="warning"
                    class="alert-tag">{{ t("quality.alertOnFail") }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('quality.lastStatus')" width="140">
          <template #default="{ row }">
            <status-dot v-if="row.last_status" :status="row.last_status" />
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('quality.passRate')" width="150">
          <template #default="{ row }">
            <el-progress v-if="row.pass_rate !== null"
                         :percentage="row.pass_rate"
                         :status="row.pass_rate >= 90 ? 'success'
                           : row.pass_rate >= 60 ? 'warning' : 'exception'"
                         :stroke-width="8" />
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('quality.actions')" width="240" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canEdit" link @click="run(row)">{{ t("quality.run") }}</el-button>
            <el-button v-if="canEdit" link @click="openSchedule(row)">
              {{ t("quality.schedule") }}
            </el-button>
            <el-button link @click="showResults(row)">{{ t("quality.results") }}</el-button>
            <el-button v-if="canEdit" link type="danger" @click="removeRule(row)">{{ t("quality.delete") }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <empty-state v-if="!loading && !filtered.length"
                   :title="t('quality.empty')"
                   :description="t('quality.intro')"
                   :action-text="canEdit ? t('quality.new') : ''"
                   @action="openCreate" />
    </el-card>

    <el-dialog v-model="dialog" :title="t('quality.createTitle')" width="560px">
      <el-form ref="formRef" :model="form" :rules="formRules"
               label-width="100px">
        <el-form-item :label="t('quality.name')" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item :label="t('quality.dataset')" prop="dataset_id">
          <el-select v-model="form.dataset_id" style="width: 100%" filterable
                     @change="onDataset">
            <el-option v-for="d in datasets" :key="d.id" :value="d.id"
                       :label="`${d.schema}.${d.table}`" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('quality.kind')" required>
          <el-select v-model="form.kind" style="width: 100%">
            <el-option value="not_null" :label="t('quality.kindNotNull')" />
            <el-option value="unique" :label="t('quality.kindUnique')" />
            <el-option value="row_count" :label="t('quality.kindRowCount')" />
            <el-option value="range" :label="t('quality.kindRange')" />
            <el-option value="freshness" :label="t('quality.kindFreshness')" />
            <el-option value="regex" :label="t('quality.kindRegex')" />
            <el-option value="accepted_values" :label="t('quality.kindAcceptedValues')" />
            <el-option value="schema" :label="t('quality.kindSchema')" />
            <el-option value="custom_sql" :label="t('quality.kindCustomSql')" />
            <el-option value="row_count_anomaly"
                       :label="t('quality.kindAnomaly')" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="!['row_count', 'schema', 'custom_sql',
                             'row_count_anomaly'].includes(form.kind)"
                      :label="t('quality.column')">
          <el-select v-model="form.column_name" style="width: 100%" filterable>
            <el-option v-for="c in columns" :key="c.name" :value="c.name"
                       :label="`${c.name} (${c.type})`" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.kind === 'freshness'" :label="t('quality.maxAge')">
          <el-input-number v-model="form.max_age_hours" :min="1" />
        </el-form-item>
        <el-form-item v-if="form.kind === 'regex'" :label="t('quality.pattern')">
          <el-input v-model="form.pattern" placeholder="^[^@]+@[^@]+$" />
        </el-form-item>
        <el-form-item v-if="form.kind === 'regex'" :label="t('quality.allowNull')">
          <el-switch v-model="form.allow_null" />
        </el-form-item>
        <el-form-item v-if="form.kind === 'accepted_values'" :label="t('quality.allowedValues')">
          <el-input v-model="form.values_text" placeholder="ok,failed,pending" />
        </el-form-item>
        <el-form-item v-if="form.kind === 'accepted_values'" :label="t('quality.allowNull')">
          <el-switch v-model="form.allow_null" />
        </el-form-item>
        <el-form-item v-if="form.kind === 'schema'" :label="t('quality.expected')">
          <el-input v-model="form.expected_text" placeholder="id,email,created_at" />
        </el-form-item>
        <el-form-item v-if="form.kind === 'schema'" :label="t('quality.allowExtra')">
          <el-switch v-model="form.allow_extra" />
        </el-form-item>
        <template v-if="form.kind === 'custom_sql'">
          <el-form-item :label="t('quality.sql')">
            <el-input v-model="form.custom_sql" type="textarea" :rows="5"
                      placeholder="select * from table where ..." />
          </el-form-item>
          <el-form-item :label="t('quality.expect')">
            <el-select v-model="form.expect" style="width: 100%">
              <el-option value="zero" :label="t('quality.expectZero')" />
              <el-option value="nonzero" :label="t('quality.expectNonzero')" />
              <el-option value="max_rows" :label="t('quality.expectMax')" />
              <el-option value="min_rows" :label="t('quality.expectMin')" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="['max_rows', 'min_rows'].includes(form.expect)"
                        :label="t('quality.value')">
            <el-input-number v-model="form.expect_value" :min="0" />
          </el-form-item>
        </template>
        <template v-if="form.kind === 'row_count_anomaly'">
          <el-form-item :label="t('quality.deviation')">
            <el-input-number v-model="form.deviation_pct" :min="1" :max="500" />
          </el-form-item>
          <el-form-item :label="t('quality.window')">
            <el-input-number v-model="form.window" :min="3" :max="100" />
          </el-form-item>
        </template>
        <el-form-item :label="t('quality.schedule')">
          <el-input v-model="form.schedule_cron"
                    :placeholder="t('quality.schedulePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('quality.alertOnFail')">
          <el-switch v-model="form.alert_on_fail" />
        </el-form-item>
        <template v-if="form.kind === 'range' || form.kind === 'row_count'">
          <el-form-item :label="t('quality.min')">
            <el-input-number v-model="form.min" />
          </el-form-item>
          <el-form-item :label="t('quality.max')">
            <el-input-number v-model="form.max" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">{{ t("quality.cancel") }}</el-button>
        <el-button type="primary" :loading="saving" @click="create">{{ t("quality.save") }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="scheduleDialog" :title="t('quality.schedule')"
               width="460px">
      <el-form label-width="110px">
        <el-form-item :label="t('quality.schedule')">
          <el-input v-model="scheduleForm.schedule_cron"
                    :placeholder="t('quality.schedulePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('quality.alertOnFail')">
          <el-switch v-model="scheduleForm.alert_on_fail" />
        </el-form-item>
        <el-form-item :label="t('quality.enabled')">
          <el-switch v-model="scheduleForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="scheduleDialog = false">{{ t("quality.cancel") }}</el-button>
        <el-button type="primary" :loading="scheduleSaving"
                   @click="saveSchedule">{{ t("quality.save") }}</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="resultDrawer" :title="t('quality.results') + ' · ' + (current.name || '')" size="640px">
      <div class="trend-head">
        <span class="hint">
          {{ t("quality.trendSummary").replace("{n}", results.length) }}
        </span>
        <span class="hint" v-if="current.pass_rate !== null">
          {{ t("quality.passRate") }}: {{ current.pass_rate }}%
        </span>
        <div class="spacer" />
        <el-button size="small" @click="openDataset">
          {{ t("quality.viewDataset") }}
        </el-button>
      </div>
      <el-table :data="results" size="small">
        <el-table-column prop="id" :label="t('quality.id')" width="70" />
        <el-table-column prop="status" :label="t('quality.results')" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'pass' ? 'success' : 'danger'" size="small">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('quality.time')" width="200">
          <template #default="{ row }">{{ fmtDate(row.at) }}</template>
        </el-table-column>
        <el-table-column :label="t('quality.detail')">
          <template #default="{ row }">
            <el-popover v-if="row.detail && Object.keys(row.detail).length"
                        placement="left" :width="380" trigger="click">
              <template #reference>
                <el-button link>{{ t("quality.detail") }}</el-button>
              </template>
              <json-view :value="row.detail" />
            </el-popover>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!results.length" :description="t('quality.noResults')" />
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { Search } from "@element-plus/icons-vue";
import { api, canWrite, errMsg, getProject } from "../api";
import { fmtDate, t } from "../i18n";
import EmptyState from "../components/EmptyState.vue";
import EntityIcon from "../components/EntityIcon.vue";
import PageHeader from "../components/PageHeader.vue";
import StatusDot from "../components/StatusDot.vue";
import JsonView from "../components/JsonView.vue";
import StatTile from "../components/StatTile.vue";

const router = useRouter();

const rows = ref([]);
const canEdit = canWrite();
const formRef = ref(null);
const formRules = computed(() => ({
  name: [{ required: true, message: t("quality.nameDatasetRequired"),
          trigger: "blur" }],
  dataset_id: [{ required: true,
                message: t("quality.nameDatasetRequired"),
                trigger: "change" }],
}));

const summary = computed(() => {
  const all = rows.value;
  const failing = all.filter((r) => r.last_status && r.last_status !== "pass")
    .length;
  const rates = all.filter((r) => typeof r.pass_rate === "number")
    .map((r) => r.pass_rate);
  const avg = rates.length
    ? Math.round(rates.reduce((a, b) => a + b, 0) / rates.length) : null;
  return { total: all.length, failing, avg };
});
const datasets = ref([]);
const columns = ref([]);
const results = ref([]);
const loading = ref(false);
const saving = ref(false);
const dialog = ref(false);
const scheduleDialog = ref(false);
const scheduleSaving = ref(false);
const scheduleRule = ref(null);
const scheduleForm = reactive({ schedule_cron: "", alert_on_fail: false,
                                enabled: true });
const resultDrawer = ref(false);
const current = ref({});
const q = ref("");
const form = reactive({
  schedule_cron: "", alert_on_fail: false,
  name: "", dataset_id: null, kind: "not_null", column_name: "",
  min: null, max: null, max_age_hours: 24, pattern: "", values_text: "",
  expected_text: "", allow_null: true, allow_extra: false,
  custom_sql: "", expect: "zero", expect_value: null,
  deviation_pct: 30, window: 10,
});

const filtered = computed(() =>
  rows.value.filter((r) => !q.value || r.name.toLowerCase().includes(q.value.toLowerCase()))
);

function kindLabel(k) {
  return {
    not_null: t("quality.tagNotNull"), unique: t("quality.tagUnique"),
    row_count: t("quality.tagRowCount"), range: t("quality.tagRange"),
    freshness: t("quality.tagFreshness"), regex: t("quality.tagRegex"),
    accepted_values: t("quality.tagAcceptedValues"), schema: t("quality.tagSchema"),
    custom_sql: t("quality.tagCustomSql"),
    row_count_anomaly: t("quality.tagAnomaly"),
  }[k] || k;
}
function datasetName(id) {
  const d = datasets.value.find((x) => x.id === id);
  return d ? `${d.schema}.${d.table}` : `#${id}`;
}

async function load() {
  loading.value = true;
  try {
    rows.value = (await api.get("/quality/rules?page_size=200")).items || [];
    datasets.value = await api.get("/catalog/datasets");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

async function removeRule(row) {
  try {
    await ElMessageBox.confirm(
      t("quality.deleteConfirm").replace("{name}", row.name), t("quality.deleteTitle"),
      { type: "warning" });
  } catch (e) {
    return;
  }
  try {
    await api.del(`/quality/rules/${row.id}`);
    ElMessage.success(t("quality.deleted"));
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

function openCreate() {
  Object.assign(form, {
    name: "", dataset_id: datasets.value[0]?.id ?? null, kind: "not_null",
    column_name: "", min: null, max: null, max_age_hours: 24,
    pattern: "", values_text: "", expected_text: "", allow_null: true,
    allow_extra: false, schedule_cron: "", alert_on_fail: false,
    custom_sql: "", expect: "zero", expect_value: null,
    deviation_pct: 30, window: 10,
  });
  columns.value = [];
  dialog.value = true;
  if (form.dataset_id) onDataset(form.dataset_id);
}

async function onDataset(id) {
  form.column_name = "";
  columns.value = [];
  try {
    const d = await api.datasetDetail(id);
    columns.value = d.columns || [];
    if (columns.value.length) form.column_name = columns.value[0].name;
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function create() {
  try {
    await formRef.value.validate();
  } catch {
    return;
  }
  saving.value = true;
  try {
    const config = {};
    if (form.min !== null) config.min = form.min;
    if (form.max !== null) config.max = form.max;
    if (form.kind === "freshness") {
      config.max_age_hours = form.max_age_hours;
    }
    if (form.kind === "regex") {
      config.pattern = form.pattern;
      config.allow_null = form.allow_null;
    }
    if (form.kind === "accepted_values") {
      config.values = form.values_text.split(",")
        .map((x) => x.trim()).filter(Boolean);
      config.allow_null = form.allow_null;
    }
    if (form.kind === "schema") {
      config.expected = form.expected_text.split(",")
        .map((x) => x.trim()).filter(Boolean);
      config.allow_extra = form.allow_extra;
    }
    if (form.kind === "custom_sql") {
      config.sql = form.custom_sql;
      config.expect = form.expect;
      if (form.expect_value !== null) config.value = form.expect_value;
    }
    if (form.kind === "row_count_anomaly") {
      config.deviation_pct = form.deviation_pct;
      config.window = form.window;
    }
    await api.post("/quality/rules", {
      project_id: getProject() || 1,
      dataset_id: form.dataset_id,
      name: form.name,
      kind: form.kind,
      column_name: ["row_count", "schema", "custom_sql",
                    "row_count_anomaly"].includes(form.kind)
        ? null : form.column_name,
      schedule_cron: form.schedule_cron || null,
      alert_on_fail: form.alert_on_fail,
      config,
    });
    dialog.value = false;
    await load();
    ElMessage.success(t("quality.created"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

function openSchedule(row) {
  scheduleRule.value = row;
  scheduleForm.schedule_cron = row.schedule_cron || "";
  scheduleForm.alert_on_fail = !!row.alert_on_fail;
  scheduleForm.enabled = row.enabled !== false;
  scheduleDialog.value = true;
}

async function saveSchedule() {
  if (!scheduleRule.value) return;
  scheduleSaving.value = true;
  try {
    await api.put(`/quality/rules/${scheduleRule.value.id}`, {
      schedule_cron: scheduleForm.schedule_cron || null,
      alert_on_fail: scheduleForm.alert_on_fail,
      enabled: scheduleForm.enabled,
    });
    scheduleDialog.value = false;
    await load();
    ElMessage.success(t("quality.updated"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    scheduleSaving.value = false;
  }
}

async function run(row) {
  try {
    const r = await api.post(`/quality/rules/${row.id}/run`);
    ElMessage[r.status === "pass" ? "success" : "warning"](
      r.status === "pass"
        ? t("quality.pass")
        : t("quality.fail").replace("{detail}", JSON.stringify(r.detail))
    );
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function showResults(row) {
  current.value = row;
  try {
    results.value = await api.get(`/quality/rules/${row.id}/results`);
    resultDrawer.value = true;
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

function openDataset() {
  if (current.value.dataset_id) {
    router.push(`/catalog/${current.value.dataset_id}`);
  }
}

onMounted(load);
</script>

<style scoped>
.summary-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}
@media (max-width: 720px) {
  .summary-row { grid-template-columns: 1fr; }
}
.entity-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.card {
  border-radius: 12px;
  border: 1px solid #e5e7eb;
}
.mono {
  font-family: Consolas, monospace;
  font-size: 12px;
}
.muted { color: #64748b; font-size: 12px; }
.trend-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.spacer { flex: 1; }
.hint { color: #6b7280; font-size: 12px; }
</style>
