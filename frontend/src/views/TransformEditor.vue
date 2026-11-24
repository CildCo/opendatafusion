<template>
  <div class="model-page">
    <div class="head">
      <el-button link @click="$router.push('/models')" :aria-label="t('common.back')">←</el-button>
      <el-input v-model="name" size="small" style="width: 220px"
                @change="rename" />
      <el-tag size="small" :type="published ? 'success' : 'info'">
        {{ published ? t("tm.published") : t("tm.draft") }}
      </el-tag>
      <el-tag v-if="target" size="small" type="info" class="mono">
        {{ target }}
      </el-tag>
      <div class="spacer" />
      <el-button size="small" @click="save()">{{ t("tm.save") }}</el-button>
      <el-button size="small" @click="validate">{{ t("tm.validate") }}</el-button>
      <el-button size="small" :loading="querying" @click="preview">{{ t("tm.preview") }}</el-button>
      <el-button size="small" :disabled="!published" @click="run">{{ t("tm.run") }}</el-button>
      <el-button size="small" type="primary" @click="publish">{{ t("tm.publish") }}</el-button>
      <el-button size="small" @click="versionsOpen = true">{{ t("tm.versions") }}</el-button>
      <el-button size="small" @click="lineageOpen = true">{{ t("lin.button") }}</el-button>
      <el-button size="small" @click="governanceOpen = true">{{ t("gov.button") }}</el-button>
    </div>

    <div class="body">
      <aside class="form">
        <el-form label-width="92px" size="small">
          <el-form-item :label="t('tm.datasource')">
            <el-select v-model="content.datasource_id" filterable
                       style="width: 100%">
              <el-option v-for="d in datasources" :key="d.id" :value="d.id"
                         :label="`${d.name} (${d.kind})`" />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('tm.materialization')">
            <el-select v-model="content.materialization" style="width: 100%">
              <el-option v-for="m in materializations" :key="m" :value="m"
                         :label="m" />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('tm.schema')">
            <el-input v-model="content.schema"
                      :placeholder="t('tm.schemaPlaceholder')" />
          </el-form-item>
          <el-form-item :label="t('tm.layer')">
            <el-select v-model="content.layer" style="width: 100%">
              <el-option v-for="l in layers" :key="l" :value="l"
                         :label="l" />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('tm.uniqueKey')">
            <el-select v-model="content.unique_key" multiple filterable
                       allow-create style="width: 100%">
              <el-option v-for="c in resultColumns" :key="c" :value="c"
                         :label="c" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="content.materialization === 'incremental'"
                        :label="t('tm.incrementalStrategy')">
            <el-select v-model="content.incremental_strategy"
                       style="width: 100%">
              <el-option value="append" :label="t('tm.strategyAppend')" />
              <el-option value="merge" :label="t('tm.strategyMerge')" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="content.materialization !== 'view'"
                        :label="t('tm.partitionBy')">
            <el-select v-model="content.partition_by" multiple filterable
                       allow-create :placeholder="t('tm.partitionHint')"
                       style="width: 100%">
              <el-option v-for="c in resultColumns" :key="c" :value="c"
                         :label="c" />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('tm.description')">
            <el-input v-model="content.description" type="textarea"
                      :rows="2" />
          </el-form-item>
        </el-form>

        <h4>{{ t("tm.tests") }}</h4>
        <div v-for="(test, i) in content.tests" :key="i" class="test-row">
          <el-select v-model="test.kind" size="small" style="width: 128px">
            <el-option v-for="k in testKinds" :key="k" :value="k"
                       :label="k" />
          </el-select>
          <template v-if="test.kind === 'sql'">
            <el-input v-model="test.sql" size="small" type="textarea"
                      :rows="2" :placeholder="t('tm.testSql')" />
          </template>
          <template v-else>
            <el-select v-model="test.column" size="small" filterable
                       allow-create style="width: 110px">
              <el-option v-for="c in resultColumns" :key="c" :value="c"
                         :label="c" />
            </el-select>
          </template>
          <el-input v-if="test.kind === 'accepted_values'" size="small"
                    style="width: 120px" :model-value="(test.values || []).join(',')"
                    @update:model-value="setValues(test, $event)"
                    :placeholder="t('tm.values')" />
          <template v-if="test.kind === 'relationships'">
            <el-input v-model="test.to_model" size="small" style="width: 110px"
                      :placeholder="t('tm.toModel')" />
            <el-input v-model="test.to_column" size="small" style="width: 100px"
                      :placeholder="t('tm.toColumn')" />
          </template>
          <el-button link type="danger" @click="content.tests.splice(i, 1)"
                     :aria-label="t('common.remove')">×</el-button>
        </div>
        <el-button link type="primary" @click="addTest">
          {{ t("tm.addTest") }}
        </el-button>

        <h4 class="col-head">
          {{ t("tm.columns") }}
          <span>
            <el-button link type="primary" size="small" @click="inferColumns">
              {{ t("tm.inferColumns") }}
            </el-button>
            <el-button link type="primary" size="small" @click="fillColumns">
              {{ t("tm.fillColumns") }}
            </el-button>
          </span>
        </h4>
        <div v-for="(col, i) in content.columns" :key="i" class="col-row">
          <el-input v-model="col.name" size="small" style="width: 100px"
                    placeholder="name" />
          <el-input v-model="col.source" size="small" style="width: 118px"
                    :placeholder="t('tm.source')" />
          <el-input v-model="col.type" size="small" style="width: 80px"
                    placeholder="type" />
          <el-button link type="danger" @click="content.columns.splice(i, 1)"
                     :aria-label="t('common.remove')">×</el-button>
        </div>
        <el-button link type="primary" size="small" @click="addColumn">
          {{ t("tm.addColumn") }}
        </el-button>
        <p class="hint">{{ t("tm.columnsHint") }}</p>
        <p class="hint">{{ t("tm.refHint") }}</p>
      </aside>

      <main class="result">
        <SqlEditor v-model="content.sql" class="editor" />
        <el-table v-if="rows.length" :data="rows" size="small" height="360"
                  style="margin-top: 10px">
          <el-table-column v-for="c in resultColumns" :key="c" :prop="c"
                           :label="c" />
        </el-table>
        <el-empty v-else :description="t('tm.emptyPreview')"
                  :image-size="60" />
        <div v-if="stats" class="stats">{{ stats }}</div>
        <pre v-if="sql" class="sql">{{ sql }}</pre>
      </main>
    </div>

    <el-drawer v-model="versionsOpen" :title="t('tm.versions')" size="480px"
               @open="loadVersions">
      <el-table :data="versions" size="small">
        <el-table-column prop="version" :label="t('tm.version')" width="70" />
        <el-table-column prop="status" :label="t('tm.status')" width="100" />
        <el-table-column prop="created_by" :label="t('tm.createdBy')" />
        <el-table-column :label="t('tm.actions')" width="90">
          <template #default="{ row }">
            <el-button link :disabled="row.current || row.status === 'draft'"
                       @click="rollback(row)">{{ t("tm.rollback") }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>
    <lineage-drawer v-model="lineageOpen" :asset-id="id" />
    <governance-drawer v-model="governanceOpen" :asset-id="id" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg, getProject, getRole } from "../api";
import { t } from "../i18n";
import SqlEditor from "../studio/api/SqlEditor.vue";
import LineageDrawer from "../components/LineageDrawer.vue";
import GovernanceDrawer from "../components/GovernanceDrawer.vue";
import { useDraftSafety } from "../draftSafety";

const route = useRoute();
const id = Number(route.params.id);
const name = ref("");
const published = ref(false);
const draftVersion = ref(null);
const datasources = ref([]);
const rows = ref([]);
const resultColumns = ref([]);
const stats = ref("");
const sql = ref("");
const target = ref("");
const querying = ref(false);
const versions = ref([]);
const versionsOpen = ref(false);
const lineageOpen = ref(false);
const governanceOpen = ref(false);
const materializations = ["view", "table", "incremental"];
const layers = ["raw", "staging", "intermediate", "mart"];
const testKinds = ["not_null", "unique", "accepted_values",
                   "relationships", "sql"];
const content = ref({
  datasource_id: null, sql: "",
  materialization: "table", schema: "", unique_key: [], layer: "staging",
  description: "", tests: [], columns: [], partition_by: [],
  incremental_strategy: "append",
});

function setValues(test, text) {
  test.values = String(text || "").split(",").map((x) => x.trim())
    .filter(Boolean);
}

function addTest() {
  content.value.tests.push({ kind: "not_null", column: "" });
}

function addColumn() {
  content.value.columns.push({ name: "", source: "", type: "",
                               description: "" });
}

function fillColumns() {
  const known = new Set(content.value.columns.map((c) => c.name));
  for (const name of resultColumns.value) {
    if (!known.has(name)) {
      content.value.columns.push({ name, source: name, type: "",
                                   description: "" });
    }
  }
}

async function inferColumns() {
  try {
    const result = await api.post(`/models/${id}/infer-columns`, {
      content: content.value,
    });
    content.value.columns = result.columns || [];
    ElMessage.success(t("tm.inferred"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function load() {
  const a = await api.get(`/models/${id}`);
  name.value = a.name;
  draftVersion.value = a.draft_version;
  published.value = Boolean(a.published_version);
  const draft = a.draft || {};
  content.value = {
    datasource_id: draft.datasource_id || null,
    sql: draft.sql || "",
    materialization: draft.materialization || "table",
    schema: draft.schema || "",
    unique_key: draft.unique_key || [],
    layer: draft.layer || "staging",
    description: draft.description || "",
    tests: draft.tests || [],
    columns: draft.columns || [],
    partition_by: draft.partition_by || [],
    incremental_strategy: draft.incremental_strategy || "append",
  };
  try {
    target.value = (await api.get(`/models/${id}/target`)).target || "";
  } catch {
    target.value = "";
  }
  datasources.value = ((await api.get("/datasources")) || [])
    .filter((d) => d.capabilities?.query);
  draftGuard.reset();
}

async function save(silent = false) {
  try {
    const body = { content: content.value };
    if (draftVersion.value !== null) body.base_version = draftVersion.value;
    const result = await api.put(`/models/${id}/draft`, body);
    draftVersion.value = result.version;
    if (!silent) ElMessage.success(t("tm.draftSaved"));
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
    await api.put(`/models/${id}`, { name: name.value });
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function validate() {
  try {
    const r = await api.post(`/models/${id}/validate`,
                             { content: content.value });
    if (r.valid) ElMessage.success(t("tm.validated"));
    else ElMessage.error(r.errors.map((e) => e.message).join("; "));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function preview() {
  querying.value = true;
  try {
    const r = await api.post(`/models/${id}/preview`, {
      limit: 100, content: content.value,
    });
    rows.value = r.rows || [];
    resultColumns.value = (r.columns || []).map((c) => c.name);
    target.value = r.target || "";
    stats.value = t("tm.statsRows")
      .replace("{count}", r.row_count).replace("{ms}", r.ms);
    sql.value = r.sql || "";
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    querying.value = false;
  }
}

async function run() {
  try {
    const r = await api.post(`/models/${id}/run`, {});
    ElMessage.success(t("tm.queued").replace("{id}", r.job_id));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function publish() {
  const ok = await save();
  if (!ok) return;
  try {
    if (["approver", "admin"].includes(getRole())) {
      await api.applyChange("publish_model", id);
      ElMessage.success(t("tm.published"));
    } else {
      await api.post("/changes", {
        project_id: getProject() || 1, action: "publish_model",
        target: id, payload: {},
      });
      ElMessage.success(t("tm.submitted"));
    }
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function loadVersions() {
  versions.value = await api.get(`/models/${id}/versions`);
}

async function rollback(row) {
  try {
    await ElMessageBox.confirm(
      t("tm.rollbackConfirm").replace("{version}", row.version),
      t("tm.rollbackTitle"));
    await api.applyChange("rollback_model", id, { version: row.version });
    await load();
    await loadVersions();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

onMounted(load);
</script>

<style scoped>
.model-page { height: calc(100vh - 104px); display: flex; flex-direction: column;
              background: #f8fafc; border: 1px solid #e5e7eb;
              border-radius: 10px; overflow: hidden; }
.head { min-height: 52px; display: flex; align-items: center; gap: 8px;
        padding: 4px 12px; background: #fff; border-bottom: 1px solid #e5e7eb;
        flex-wrap: wrap; }
.spacer { flex: 1; }
.body { flex: 1; display: grid; grid-template-columns: 430px 1fr;
        min-height: 0; }
.form { background: #fff; border-right: 1px solid #e5e7eb; overflow: auto;
        padding: 12px; }
.result { overflow: auto; padding: 12px; }
.test-row { display: flex; gap: 4px; margin-bottom: 6px; align-items: center;
            flex-wrap: wrap; }
h4 { margin: 14px 0 8px; font-size: 13px; color: #374151; }
.hint { color: #6b7280; font-size: 11px; }
.col-head { display: flex; align-items: center; justify-content: space-between;
            gap: 6px; }
.col-row { display: flex; gap: 4px; margin-bottom: 4px; align-items: center; }
.stats { margin-top: 8px; font-size: 12px; color: #475569; }
.sql { background: #0f172a; color: #e2e8f0; padding: 8px;
       border-radius: 6px; font-size: 11px; white-space: pre-wrap; }
.mono { font-family: ui-monospace, monospace; font-size: 11px; }
.editor { height: 240px; border: 1px solid #e5e7eb; }
</style>
