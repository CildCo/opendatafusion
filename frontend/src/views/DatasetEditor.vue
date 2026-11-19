<template>
  <div class="model-page">
    <div class="head">
      <el-button link @click="$router.push('/datasets')":aria-label="t('common.back')">←</el-button>
      <el-input v-model="name" size="small" style="width: 240px"
                @change="rename" />
      <el-tag size="small" :type="published ? 'success' : 'info'">
        {{ published ? t("ded.published") : t("ded.draft") }}
      </el-tag>
      <div class="spacer" />
      <el-button size="small" @click="save">{{ t("ded.save") }}</el-button>
      <el-button size="small" @click="validate">{{ t("ded.validate") }}</el-button>
      <el-button size="small" :loading="previewing" @click="preview">{{ t("ded.preview") }}</el-button>
      <el-button size="small" type="primary" @click="publish">{{ t("ded.publish") }}</el-button>
      <el-button size="small" @click="openPolicies">{{ t("ded.rowPolicies") }}</el-button>
      <el-button size="small" @click="openColumnPolicies">{{ t("ded.columnMasking") }}</el-button>
      <el-button size="small" @click="versionsOpen = true">{{ t("ded.versions") }}</el-button>
    </div>
    <div class="body">
      <main class="center">
        <VisualBuilder :content="content" :datasources="datasources" />
      </main>
      <aside class="right">
        <el-table v-if="rows.length" :data="rows" size="small" height="320">
          <el-table-column v-for="c in columns" :key="c" :prop="c" :label="c" />
        </el-table>
        <div v-if="stats" class="stats">{{ stats }}</div>
        <pre v-if="sql" class="sql">{{ sql }}</pre>
      </aside>
    </div>
    <el-drawer v-model="policiesOpen" :title="t('ded.rowPolicies')" size="620px"
               @open="loadPolicies">
      <div class="policy-add">
        <el-select v-model="policyForm.column" filterable
                   :placeholder="t('ded.column')"
                   size="small" style="width: 130px">
          <el-option v-for="c in policyColumns" :key="c" :value="c"
                     :label="c" />
        </el-select>
        <el-select v-model="policyForm.op" size="small" style="width: 100px">
          <el-option v-for="op in policyOps" :key="op" :value="op"
                     :label="op" />
        </el-select>
        <el-input v-model="policyForm.value" size="small"
                  :placeholder="t('ded.value')"
                  style="width: 150px" />
        <el-select v-model="policyForm.roles" multiple size="small"
                   :placeholder="t('ded.roles')" style="width: 190px">
          <el-option v-for="r in roles" :key="r" :value="r" :label="r" />
        </el-select>
        <el-button type="primary" size="small" @click="addPolicy">
          {{ t("ded.add") }}
        </el-button>
      </div>
      <p class="policy-hint">
        {{ t("ded.policyHint") }}
      </p>
      <el-table :data="policies" size="small"
                :empty-text="t('ded.noPolicies')">
        <el-table-column prop="column" :label="t('ded.column')" width="130" />
        <el-table-column prop="op" :label="t('ded.operation')" width="90" />
        <el-table-column prop="value" :label="t('ded.value')" min-width="150">
          <template #default="{ row }">{{ JSON.stringify(row.value) }}</template>
        </el-table-column>
        <el-table-column :label="t('ded.roles')" min-width="140">
          <template #default="{ row }">
            <span v-if="!row.roles?.length">{{ t("ded.all") }}</span>
            <el-tag v-for="r in row.roles" :key="r" size="small"
                    style="margin-right: 4px">{{ r }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('ded.operation')" width="80">
          <template #default="{ row }">
            <el-button link type="danger" @click="removePolicy(row)">
              {{ t("ded.delete") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>
    <el-drawer v-model="columnPoliciesOpen" :title="t('ded.columnMasking')"
               size="720px" @open="loadColumnPolicies">
      <div class="policy-add">
        <el-select v-model="columnForm.column" filterable
                   :placeholder="t('ded.column')"
                   size="small" style="width: 130px">
          <el-option v-for="c in policyColumns" :key="c" :value="c"
                     :label="c" />
        </el-select>
        <el-select v-model="columnForm.classification" size="small"
                   style="width: 130px">
          <el-option value="pii" label="PII" />
          <el-option value="confidential" :label="t('ded.confidential')" />
          <el-option value="sensitive" :label="t('ded.sensitive')" />
        </el-select>
        <el-select v-model="columnForm.mask_type" size="small"
                   style="width: 120px">
          <el-option value="redact" :label="t('ded.maskRedact')" />
          <el-option value="partial" :label="t('ded.maskPartial')" />
          <el-option value="hash" :label="t('ded.maskHash')" />
          <el-option value="null" :label="t('ded.maskNull')" />
        </el-select>
        <el-select v-model="columnForm.exempt_roles" multiple size="small"
                   :placeholder="t('ded.exemptRoles')" style="width: 180px">
          <el-option v-for="r in roles" :key="r" :value="r" :label="r" />
        </el-select>
        <el-button type="primary" size="small" @click="saveColumnPolicy">
          {{ t("ded.save") }}
        </el-button>
      </div>
      <p class="policy-hint">
        {{ t("ded.columnHint") }}
      </p>
      <el-table :data="columnPolicies" size="small"
                :empty-text="t('ded.noColumnPolicies')">
        <el-table-column prop="column" :label="t('ded.field')" width="130" />
        <el-table-column :label="t('ded.classification')" width="110">
          <template #default="{ row }">{{ classLabel(row.classification) }}</template>
        </el-table-column>
        <el-table-column :label="t('ded.maskType')" width="110">
          <template #default="{ row }">{{ maskLabel(row.mask_type) }}</template>
        </el-table-column>
        <el-table-column :label="t('ded.exemptRoles')" min-width="140">
          <template #default="{ row }">
            <span v-if="!row.exempt_roles?.length">{{ t("ded.none") }}</span>
            <el-tag v-for="r in row.exempt_roles" :key="r" size="small"
                    style="margin-right: 4px">{{ r }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_by" :label="t('ded.configuredBy')"
                         width="110" />
        <el-table-column :label="t('ded.operation')" width="80">
          <template #default="{ row }">
            <el-button link type="danger" @click="removeColumnPolicy(row)">
              {{ t("ded.delete") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>
    <el-drawer v-model="versionsOpen" :title="t('ded.versions')" size="480px"
               @open="loadVersions">
      <el-table :data="versions" size="small">
        <el-table-column prop="version" :label="t('ded.version')" width="70" />
        <el-table-column prop="status" :label="t('ded.status')" width="100" />
        <el-table-column prop="created_by" :label="t('ded.createdBy')" />
        <el-table-column :label="t('ded.operation')" width="90">
          <template #default="{ row }">
            <el-button link :disabled="row.current || row.status === 'draft'"
                       @click="rollback(row)">{{ t("ded.rollback") }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../api";
import { t } from "../i18n";
import VisualBuilder from "../studio/api/VisualBuilder.vue";
import { normalizeContent } from "../studio/api/content";

const route = useRoute();
const id = Number(route.params.id);
const name = ref("");
const published = ref(false);
const content = ref(normalizeContent(null));
const datasources = ref([]);
const rows = ref([]);
const columns = ref([]);
const stats = ref("");
const sql = ref("");
const previewing = ref(false);
const versions = ref([]);
const versionsOpen = ref(false);
const policiesOpen = ref(false);
const policies = ref([]);
const policyColumns = ref([]);
const policyForm = ref({ column: "", op: "=", value: "", roles: [] });
const columnPoliciesOpen = ref(false);
const columnPolicies = ref([]);
const columnForm = ref({ column: "", classification: "pii",
                         mask_type: "redact", exempt_roles: [] });
const policyOps = ["=", "!=", ">", ">=", "<", "<=", "in", "like",
                   "is null", "is not null"];
const roles = ["viewer", "editor", "approver", "admin"];

async function openPolicies() {
  policiesOpen.value = true;
}

async function loadPolicies() {
  try {
    policies.value = await api.get(`/datasets/${id}/policies`);
    const schema = await api.get(`/datasets/${id}/schema`);
    policyColumns.value = (schema.columns || []).map((c) => c.name);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function openColumnPolicies() {
  columnPoliciesOpen.value = true;
}

function classLabel(v) {
  return { pii: "PII", confidential: t("ded.confidential"),
           sensitive: t("ded.sensitive") }[v] || v;
}
function maskLabel(v) {
  return { redact: t("ded.maskRedact"), partial: t("ded.maskPartial"),
           hash: t("ded.maskHash"), null: t("ded.maskNull") }[v] || v;
}

async function loadColumnPolicies() {
  try {
    columnPolicies.value = await api.get(
      `/datasets/${id}/column-policies`);
    const schema = await api.get(`/datasets/${id}/schema`);
    policyColumns.value = (schema.columns || []).map((c) => c.name);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function saveColumnPolicy() {
  const f = columnForm.value;
  if (!f.column) {
    ElMessage.warning(t("ded.selectField"));
    return;
  }
  try {
    await api.post(`/datasets/${id}/column-policies`, {
      column: f.column, classification: f.classification,
      mask_type: f.mask_type, exempt_roles: f.exempt_roles,
    });
    columnForm.value = { column: "", classification: "pii",
                         mask_type: "redact", exempt_roles: [] };
    await loadColumnPolicies();
    ElMessage.success(t("ded.saved"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function removeColumnPolicy(row) {
  try {
    await api.del(`/datasets/${id}/column-policies/${row.id}`);
    await loadColumnPolicies();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function addPolicy() {
  const f = policyForm.value;
  let value = f.value;
  if (f.op === "in") {
    value = String(value).split(",").map((x) => x.trim()).filter(Boolean);
  } else if (f.value !== "" && !Number.isNaN(Number(f.value))) {
    value = Number(f.value);
  }
  try {
    await api.post(`/datasets/${id}/policies`, {
      column: f.column, op: f.op, value, roles: f.roles,
    });
    policyForm.value = { column: "", op: "=", value: "", roles: [] };
    await loadPolicies();
    ElMessage.success(t("ded.added"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function removePolicy(row) {
  try {
    await api.del(`/datasets/${id}/policies/${row.id}`);
    await loadPolicies();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function load() {
  const a = await api.get(`/datasets/${id}`);
  name.value = a.name;
  published.value = Boolean(a.published);
  content.value = normalizeContent(a.draft);
  datasources.value = await api.get("/datasources");
}

async function save() {
  try {
    await api.put(`/datasets/${id}/draft`, { content: content.value });
    ElMessage.success(t("ded.draftSaved"));
    return true;
  } catch (e) {
    ElMessage.error(errMsg(e));
    return false;
  }
}

async function rename() {
  try {
    await api.put(`/datasets/${id}`, { name: name.value });
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function validate() {
  try {
    const r = await api.post(`/datasets/${id}/validate`,
                             { content: content.value });
    if (r.valid) ElMessage.success(t("ded.validated"));
    else ElMessage.error(r.errors.map((e) => e.message).join("; "));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function preview() {
  previewing.value = true;
  try {
    const r = await api.post(`/datasets/${id}/preview`, {
      limit: 100, content: content.value,
    });
    rows.value = r.rows || [];
    columns.value = r.columns || [];
    stats.value = t("ded.statsRows")
      .replace("{count}", r.row_count).replace("{ms}", r.ms);
    sql.value = r.sql || "";
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    previewing.value = false;
  }
}

async function publish() {
  const ok = await save();
  if (!ok) return;
  try {
    await api.applyChange("publish_dataset", id);
    await load();
    ElMessage.success(t("ded.published"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function loadVersions() {
  versions.value = await api.get(`/datasets/${id}/versions`);
}

async function rollback(row) {
  try {
    await ElMessageBox.confirm(
      t("ded.rollbackConfirm").replace("{version}", row.version),
      t("ded.rollbackTitle"));
    await api.applyChange("rollback_dataset", id, { version: row.version });
    await load();
    await loadVersions();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

onMounted(load);
</script>

<style scoped>
.policy-add { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.policy-hint { color: #6b7280; font-size: 12px; margin: 8px 0; }
.model-page { height: calc(100vh - 104px); display: flex; flex-direction: column;
              background: #f8fafc; border: 1px solid #e5e7eb;
              border-radius: 10px; overflow: hidden; }
.head { height: 52px; display: flex; align-items: center; gap: 8px;
        padding: 0 12px; background: #fff; border-bottom: 1px solid #e5e7eb; }
.spacer { flex: 1; }
.body { flex: 1; display: grid; grid-template-columns: 1fr 380px;
        min-height: 0; }
.center { overflow: auto; background: #fff; }
.right { background: #fff; border-left: 1px solid #e5e7eb; overflow: auto;
         padding: 10px; }
.stats { margin: 8px 0; font-size: 12px; color: #475569; }
.sql { background: #0f172a; color: #e2e8f0; padding: 8px; border-radius: 6px;
       font-size: 11px; white-space: pre-wrap; }
</style>
