<template>
  <div class="page">
    <page-header icon="source" :title="t('menu.datasources')"
                 :intro="t('ds.intro')" />
    <div class="toolbar">
      <el-input v-model="q" :placeholder="t('ds.searchPlaceholder')" clearable
                style="width: 240px" :prefix-icon="Search" />
      <el-select v-model="kind" clearable :placeholder="t('ds.allKinds')"
                 style="width: 180px">
        <el-option-group v-for="group in connectorGroups"
                         :key="group.key" :label="t('ds.group.' + group.key)">
          <el-option v-for="item in group.items" :key="item.kind"
                     :value="item.kind" :label="item.label" />
        </el-option-group>
      </el-select>
      <div class="spacer" />
      <el-button @click="load" :loading="loading">{{ t("ds.refresh") }}</el-button>
      <el-button v-if="canEdit" type="primary" @click="openCreate">{{ t("ds.new") }}</el-button>
    </div>

    <el-card shadow="never" class="card">
      <el-table :data="paged" size="small" v-loading="loading">
        <el-table-column prop="id" :label="t('ds.colId')" width="70" />
        <el-table-column :label="t('ds.colName')" min-width="190">
          <template #default="{ row }">
            <span class="entity-cell">
              <entity-icon type="source" :size="20" />
              <b>{{ row.name }}</b>
            </span>
          </template>
        </el-table-column>
        <el-table-column :label="t('ds.colKind')" width="170">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ kindLabel(row.kind) }}</el-tag>
            <el-tag v-if="pipelineOnly(row)" size="small" type="warning"
                    class="cap-tag">{{ t("ds.pipelineOnly") }}</el-tag>
            <el-tag v-else-if="row.capabilities && !row.capabilities.query"
                    size="small" type="warning" class="cap-tag">
              {{ t("ds.noQuery") }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('ds.colConnection')" min-width="260">
          <template #default="{ row }">
            <span class="mono">{{ connSummary(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('ds.colActions')" width="330" fixed="right">
          <template #default="{ row }">
            <el-button link @click="test(row)">{{ t("ds.test") }}</el-button>
            <el-button v-if="capability(row, 'metadata')" link
                       @click="sync(row)">{{ t("ds.sync") }}</el-button>
            <el-button v-if="capability(row, 'metadata')" link
                       @click="showTables(row)">{{ t("ds.tablesButton") }}</el-button>
            <el-button v-if="canEdit" link @click="openEdit(row)">{{ t("ds.edit") }}</el-button>
            <el-button v-if="canEdit" link type="danger" @click="remove(row)">{{ t("ds.delete") }}</el-button>
            <el-button v-if="canEdit && row.kind === 'trino'" link
                       @click="openMaintain(row)">{{ t("ds.maintain") }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <empty-state v-if="!loading && !filtered.length"
                   :title="t('ds.noDatasources')" :description="t('ds.intro')"
                   :action-text="canEdit ? t('ds.new') : ''" @action="openCreate" />
      <div class="pager">
        <el-pagination v-model:current-page="page" :page-size="pageSize"
                       :page-sizes="[10, 20, 50]"
                       :total="filtered.length"
                       layout="total, sizes, prev, pager, next" small />
      </div>
    </el-card>

    <el-dialog v-model="dialog" :title="dialogTitle" width="600px">
      <el-form label-width="100px">
        <el-form-item :label="t('ds.name')" required>
          <el-input v-model="form.name" :placeholder="t('ds.namePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('ds.colKind')" required>
          <el-select v-model="form.kind" style="width: 100%"
                     :disabled="!!editId" @change="onKindChange">
            <el-option-group v-for="group in connectorGroups"
                             :key="group.key"
                             :label="t('ds.group.' + group.key)">
              <el-option v-for="item in group.items" :key="item.kind"
                         :value="item.kind" :label="item.label" />
            </el-option-group>
          </el-select>
          <div v-if="editId" class="hint">{{ t("ds.kindLocked") }}</div>
        </el-form-item>

        <el-form-item v-for="field in currentFields" :key="field.key"
                      :label="fieldLabel(field)"
                      :required="field.required">
          <el-select v-if="field.type === 'select'"
                     v-model="form.values[field.key]" style="width: 100%">
            <el-option v-for="option in field.options || []"
                       :key="option" :value="option" :label="option" />
          </el-select>
          <el-input-number v-else-if="field.type === 'number'"
                           v-model="form.values[field.key]" :min="1"
                           :max="65535" controls-position="right"
                           style="width: 100%" />
          <el-input v-else v-model="form.values[field.key]"
                    :type="field.type === 'password' ? 'password' : 'text'"
                    :show-password="field.type === 'password'"
                    :placeholder="placeholderFor(field)" />
          <div v-if="field.secret && form.values['has_' + field.key]"
               class="hint">{{ t("ds.keepPassword") }}</div>
        </el-form-item>

        <div class="cap-row">
          <span class="cap-label">{{ t("ds.capabilities") }}</span>
          <el-tag v-for="cap in currentCapabilities" :key="cap" size="small"
                  type="info">{{ t("ds.cap." + cap) }}</el-tag>
        </div>

        <div v-if="form.kind !== 'file'" class="test-row">
          <el-button :loading="testing" @click="testDraft">
            {{ testing ? t("ds.testing") : t("ds.testConnection") }}
          </el-button>
          <el-tag v-if="testResult" :type="testResult.ok ? 'success' : 'danger'">
            {{ testResult.ok ? t("ds.connOk") : t("ds.testFailed") }}
          </el-tag>
          <span v-if="testResult && testResult.error" class="test-error">
            {{ testResult.error }}
          </span>
        </div>
        <p v-else class="hint test-row">{{ t("ds.testAfterSave") }}</p>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">{{ t("ds.cancel") }}</el-button>
        <el-button type="primary" :loading="saving" @click="save">
          {{ t("ds.save") }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="maintainOpen" :title="t('ds.maintain')" width="520px">
      <el-form label-width="110px">
        <el-form-item :label="t('ds.schema')">
          <el-input v-model="maintain.schema"
                    :placeholder="t('ds.schemaPlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('ds.table')">
          <el-input v-model="maintain.tables"
                    :placeholder="t('ds.tablesPlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('ds.optimize')">
          <el-switch v-model="maintain.optimize" />
        </el-form-item>
        <el-form-item :label="t('ds.expire')">
          <el-switch v-model="maintain.expire" />
        </el-form-item>
        <el-form-item :label="t('ds.retention')">
          <el-input v-model="maintain.retention" placeholder="7d" />
        </el-form-item>
      </el-form>
      <el-table v-if="maintain.results.length" :data="maintain.results"
                size="small">
        <el-table-column prop="table" :label="t('ds.table')" />
        <el-table-column prop="optimize" :label="t('ds.optimizeCol')" />
        <el-table-column prop="expire" :label="t('ds.snapshotCol')" />
      </el-table>
      <template #footer>
        <el-button @click="maintainOpen = false">{{ t("ds.close") }}</el-button>
        <el-button type="primary" :loading="maintain.running"
                   @click="runMaintain">{{ t("ds.execute") }}</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="tablesDrawer" :title="`${t('ds.table')} · ${current.name}`" size="520px">
      <el-table :data="tables" size="small">
        <el-table-column prop="schema" label="Schema" width="100" />
        <el-table-column prop="table" :label="t('ds.table')" />
        <el-table-column :label="t('ds.columnCount')" width="90">
          <template #default="{ row }">{{ (row.columns || []).length }}</template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!tables.length" :description="t('ds.noTables')" />
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Search } from "@element-plus/icons-vue";
import { useRoute } from "vue-router";
import { api, canWrite, errMsg } from "../api";
import { loadPrefs, savePrefs } from "../prefs";
import { t } from "../i18n";
import EmptyState from "../components/EmptyState.vue";
import EntityIcon from "../components/EntityIcon.vue";
import PageHeader from "../components/PageHeader.vue";

const rows = ref([]);
const tables = ref([]);
const loading = ref(false);
const saving = ref(false);
const dialog = ref(false);
const editId = ref(null);
const tablesDrawer = ref(false);
const current = ref({});
const catalog = ref({ groups: [], connectors: [] });
const prefs = loadPrefs("datasources", { q: "", kind: "", pageSize: 10 });
const q = ref(prefs.q);
const kind = ref(prefs.kind);
const canEdit = canWrite();
const route = useRoute();
const page = ref(1);
const pageSize = ref(prefs.pageSize);
const form = reactive({ name: "", kind: "postgres", values: {} });
const testing = ref(false);
const testResult = ref(null);
const maintainOpen = ref(false);
const maintain = reactive({ datasource_id: 0, schema: "", tables: "",
                            optimize: true, expire: true, retention: "7d",
                            running: false, results: [] });

watch([q, kind], () => { page.value = 1; });
watch([q, kind, pageSize], () => savePrefs("datasources", {
  q: q.value, kind: kind.value, pageSize: pageSize.value,
}));

const connectorGroups = computed(() => {
  const items = catalog.value.connectors || [];
  return (catalog.value.groups || []).map((group) => ({
    key: group.key,
    items: items.filter((item) => item.group === group.key),
  })).filter((group) => group.items.length);
});
const specs = computed(() => Object.fromEntries(
  (catalog.value.connectors || []).map((item) => [item.kind, item])));
const currentSpec = computed(() => specs.value[form.kind]);
const currentFields = computed(() => currentSpec.value?.fields || []);
const currentCapabilities = computed(() => {
  const caps = currentSpec.value?.capabilities || {};
  return ["test", "metadata", "query", "source", "sink"]
    .filter((key) => caps[key]);
});
const dialogTitle = computed(() =>
  editId.value ? t("ds.editTitle") : t("ds.new"));

const filtered = computed(() =>
  rows.value.filter((r) => {
    const hitQ = !q.value ||
      (r.name + r.kind).toLowerCase().includes(q.value.toLowerCase());
    const hitK = !kind.value || r.kind === kind.value;
    return hitQ && hitK;
  }));
const paged = computed(() =>
  filtered.value.slice((page.value - 1) * pageSize.value,
    page.value * pageSize.value));

function kindLabel(value) {
  return specs.value[value]?.label || value;
}

function capability(row, key) {
  return !!(row.capabilities && row.capabilities[key]);
}

function pipelineOnly(row) {
  return row.capabilities && !row.capabilities.metadata &&
    !row.capabilities.query;
}

function connSummary(row) {
  const c = row.config || {};
  if (c.url) return c.url;
  if (c.path) return c.path;
  const host = c.host ? `${c.host}:${c.port || ""}` : "";
  return `${host}${c.database ? "/" + c.database : ""}`;
}

function fieldLabel(field) {
  const key = "dsf." + field.key;
  const text = t(key);
  return text === key ? field.label : text;
}

function placeholderFor(field) {
  if (field.type === "password") {
    return form.values["has_" + field.key] ? t("ds.keepPassword") : "";
  }
  if (field.key === "port") return "";
  return field.placeholder || "";
}

function resetValues(spec, values = {}) {
  form.values = {};
  for (const field of spec?.fields || []) {
    form.values[field.key] = values[field.key] ??
      (field.default !== undefined ? field.default : "");
  }
  for (const [key, value] of Object.entries(values || {})) {
    if (key.startsWith("has_")) form.values[key] = value;
  }
}

function onKindChange() {
  resetValues(currentSpec.value);
  testResult.value = null;
}

async function loadCatalog() {
  try {
    catalog.value = await api.get("/datasources/connectors");
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function load() {
  loading.value = true;
  try {
    rows.value = await api.get("/datasources");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editId.value = null;
  form.name = "";
  form.kind = "postgres";
  resetValues(currentSpec.value);
  testResult.value = null;
  dialog.value = true;
}

function openEdit(row) {
  editId.value = row.id;
  form.name = row.name;
  form.kind = row.kind;
  resetValues(currentSpec.value, row.config || {});
  testResult.value = null;
  dialog.value = true;
}

function validateDraft() {
  if (!form.name.trim()) return t("ds.nameRequired");
  for (const field of currentFields.value) {
    if (!field.required) continue;
    const value = form.values[field.key];
    if (value === null || value === undefined || value === "") {
      return t("ds.requiredField").replace("{field}", fieldLabel(field));
    }
  }
  return "";
}

function draftConfig() {
  const config = {};
  for (const field of currentFields.value) {
    config[field.key] = form.values[field.key];
  }
  const has = form.values.has_password;
  if (has) config.has_password = true;
  return config;
}

async function testDraft() {
  const problem = validateDraft();
  if (problem) {
    ElMessage.warning(problem);
    return;
  }
  testing.value = true;
  testResult.value = null;
  try {
    testResult.value = await api.post("/datasources/test", {
      kind: form.kind, config: draftConfig(),
      datasource_id: editId.value || undefined,
    });
  } catch (e) {
    testResult.value = { ok: false, error: errMsg(e) };
  } finally {
    testing.value = false;
  }
}

async function save() {
  const problem = validateDraft();
  if (problem) {
    ElMessage.warning(problem);
    return;
  }
  saving.value = true;
  try {
    const body = { name: form.name.trim(), kind: form.kind,
                   config: draftConfig() };
    if (editId.value) {
      await api.put(`/datasources/${editId.value}`, body);
    } else {
      await api.post("/datasources", body);
    }
    dialog.value = false;
    await load();
    ElMessage.success(editId.value ? t("ds.saved") : t("ds.created"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

function openMaintain(row) {
  maintain.datasource_id = row.id;
  maintain.schema = "";
  maintain.tables = "";
  maintain.optimize = true;
  maintain.expire = true;
  maintain.retention = "7d";
  maintain.results = [];
  maintainOpen.value = true;
}

async function runMaintain() {
  maintain.running = true;
  try {
    const tables = maintain.tables.split(",").map((x) => x.trim())
      .filter(Boolean);
    const out = await api.post("/lakehouse/maintain", {
      datasource_id: maintain.datasource_id,
      schema_name: maintain.schema.trim() || null,
      tables,
      optimize: maintain.optimize,
      expire_snapshots: maintain.expire,
      retention: maintain.retention,
    });
    maintain.results = out.results || [];
    ElMessage.success(`${t("ds.maintainDone")}${out.schema} · ${maintain.results.length} ${t("ds.tableUnit")}`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    maintain.running = false;
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(
      `${t("ds.deleteConfirmPrefix")}${row.name}${t("ds.deleteConfirmSuffix")}`,
      t("ds.deleteTitle"), { type: "warning" });
  } catch (e) {
    return;
  }
  try {
    await api.del(`/datasources/${row.id}`);
    ElMessage.success(t("ds.deleted"));
    await load();
  } catch (e) {
    const text = errMsg(e);
    if (!text.includes("force=true")) {
      ElMessage.error(text);
      return;
    }
    try {
      await ElMessageBox.confirm(
        `${text}${t("ds.forceConfirmSuffix")}`, t("ds.inUseTitle"),
        { type: "warning" });
    } catch (cancel) {
      return;
    }
    try {
      await api.del(`/datasources/${row.id}?force=true`);
      ElMessage.success(t("ds.deleted"));
      await load();
    } catch (forceError) {
      ElMessage.error(errMsg(forceError));
    }
  }
}

async function test(row) {
  try {
    const r = await api.post(`/datasources/${row.id}/test`);
    if (r.ok) {
      ElMessage.success(t("ds.connOk"));
    } else {
      ElMessage.error(`${t("ds.testFailed")}: ${r.error || ""}`);
    }
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function sync(row) {
  try {
    const r = await api.post(`/datasources/${row.id}/sync`);
    ElMessage.success(`${t("ds.synced")}${r.tables} ${t("ds.tableUnit")}`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function showTables(row) {
  current.value = row;
  tablesDrawer.value = true;
  try {
    tables.value = await api.tablesOf(row.id);
  } catch (e) {
    tables.value = [];
    ElMessage.error(errMsg(e));
  }
}

onMounted(loadCatalog);
onMounted(load);
onMounted(() => { if (route.query.new && canEdit) openCreate(); });
</script>

<style scoped>
.entity-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.card {
  border-radius: 12px;
  border: 1px solid #e5e7eb;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}
.mono { font-family: var(--odf-mono); font-size: 12px; color: #475569; }
.cap-tag { margin-left: 6px; }
.hint { color: #64748b; font-size: 12px; margin-top: 4px; }
.cap-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin: 4px 0 14px 100px;
}
.cap-label { color: #64748b; font-size: 12px; margin-right: 4px; }
.test-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: 100px;
  flex-wrap: wrap;
}
.test-error {
  color: #b91c1c;
  font-size: 12px;
  max-width: 360px;
  word-break: break-all;
}
</style>
