<template>
  <div class="page">
    <page-header icon="catalog" :title="t('gov.title')"
                 :intro="t('gov.intro')" />
    <el-tabs v-model="tab">
      <el-tab-pane :label="t('gov.domains')" name="domains">
        <div class="toolbar">
          <el-button v-if="canEdit" type="primary" @click="openDomain()">
            {{ t("gov.newDomain") }}
          </el-button>
          <div class="spacer" />
          <el-button @click="load" :loading="loading">
            {{ t("common.refresh") }}
          </el-button>
        </div>
        <el-card shadow="never">
          <el-table :data="domains" size="small" v-loading="loading">
            <el-table-column prop="name" :label="t('gov.name')"
                             min-width="180" />
            <el-table-column prop="owner" :label="t('gov.owner')"
                             width="150" />
            <el-table-column prop="description" :label="t('gov.description')"
                             min-width="280" show-overflow-tooltip />
            <el-table-column :label="t('gov.actions')" width="150">
              <template #default="{ row }">
                <el-button link @click="openDomain(row)">
                  {{ t("gov.edit") }}
                </el-button>
                <el-button v-if="canEdit" link type="danger"
                           @click="removeDomain(row)">
                  {{ t("gov.delete") }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!loading && !domains.length"
                    :description="t('gov.emptyDomains')" />
        </el-card>
      </el-tab-pane>

      <el-tab-pane :label="t('gov.terms')" name="terms">
        <div class="toolbar">
          <el-button v-if="canEdit" type="primary" @click="openTerm()">
            {{ t("gov.newTerm") }}
          </el-button>
          <div class="spacer" />
          <el-button @click="load" :loading="loading">
            {{ t("common.refresh") }}
          </el-button>
        </div>
        <el-card shadow="never">
          <el-table :data="terms" size="small" v-loading="loading">
            <el-table-column prop="term" :label="t('gov.term')"
                             min-width="160" />
            <el-table-column prop="domain_name" :label="t('gov.domain')"
                             width="160" />
            <el-table-column prop="definition" :label="t('gov.definition')"
                             min-width="300" show-overflow-tooltip />
            <el-table-column prop="owner" :label="t('gov.owner')"
                             width="140" />
            <el-table-column :label="t('gov.actions')" width="150">
              <template #default="{ row }">
                <el-button link @click="openTerm(row)">
                  {{ t("gov.edit") }}
                </el-button>
                <el-button v-if="canEdit" link type="danger"
                           @click="removeTerm(row)">
                  {{ t("gov.delete") }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!loading && !terms.length"
                    :description="t('gov.emptyTerms')" />
        </el-card>
      </el-tab-pane>
      <el-tab-pane :label="t('gov.contracts')" name="contracts">
        <div class="toolbar">
          <span class="hint">{{ t("gov.contractsHint") }}</span>
          <div class="spacer" />
          <el-button @click="loadContracts" :loading="loading">
            {{ t("common.refresh") }}
          </el-button>
        </div>
        <el-card shadow="never">
          <el-table :data="contracts" size="small" v-loading="loading">
            <el-table-column :label="t('gov.asset')" min-width="220">
              <template #default="{ row }">
                <b>{{ row.name }}</b>
                <div class="muted">{{ row.asset_type }} · {{ row.key }}</div>
              </template>
            </el-table-column>
            <el-table-column prop="columns" :label="t('gov.contractColumns')"
                             width="110" />
            <el-table-column :label="t('gov.contractEnforce')" width="110">
              <template #default="{ row }">
                <el-switch :model-value="row.enforce" :disabled="!canEdit"
                           @change="setContract(row, { enforce: $event })" />
              </template>
            </el-table-column>
            <el-table-column :label="t('gov.contractStrict')" width="130">
              <template #default="{ row }">
                <el-switch :model-value="!row.allow_extra" :disabled="!canEdit"
                           @change="setContract(row, { allow_extra: !$event })" />
              </template>
            </el-table-column>
            <el-table-column :label="t('gov.actions')" width="300">
              <template #default="{ row }">
                <el-button link @click="checkContract(row)">
                  {{ t("gov.check") }}
                </el-button>
                <el-button v-if="canEdit" link @click="openFreshness(row)">
                  {{ t("gov.freshness") }}
                </el-button>
                <el-button v-if="canEdit" link type="primary"
                           @click="genContract(row)">
                  {{ row.columns ? t("gov.regenerate") : t("gov.generate") }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!loading && !contracts.length"
                    :description="t('gov.emptyContracts')" />
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="domainOpen" :title="domainForm.id
                 ? t('gov.edit') : t('gov.newDomain')" width="480px">
      <el-form label-width="90px">
        <el-form-item :label="t('gov.name')" required>
          <el-input v-model="domainForm.name" />
        </el-form-item>
        <el-form-item :label="t('gov.owner')">
          <el-input v-model="domainForm.owner" />
        </el-form-item>
        <el-form-item :label="t('gov.description')">
          <el-input v-model="domainForm.description" type="textarea"
                    :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="domainOpen = false">
          {{ t("gov.cancel") }}
        </el-button>
        <el-button type="primary" :loading="saving" @click="saveDomain">
          {{ t("gov.save") }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="termOpen" :title="termForm.id
                 ? t('gov.edit') : t('gov.newTerm')" width="500px">
      <el-form label-width="90px">
        <el-form-item :label="t('gov.term')" required>
          <el-input v-model="termForm.term" />
        </el-form-item>
        <el-form-item :label="t('gov.domain')">
          <el-select v-model="termForm.domain_id" clearable
                     style="width: 100%">
            <el-option v-for="d in domains" :key="d.id" :value="d.id"
                       :label="d.name" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('gov.definition')">
          <el-input v-model="termForm.definition" type="textarea"
                    :rows="3" />
        </el-form-item>
        <el-form-item :label="t('gov.owner')">
          <el-input v-model="termForm.owner" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="termOpen = false">{{ t("gov.cancel") }}</el-button>
        <el-button type="primary" :loading="saving" @click="saveTerm">
          {{ t("gov.save") }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="freshOpen" :title="t('gov.freshness')" width="460px">
      <el-form label-width="120px">
        <el-form-item :label="t('gov.freshnessColumn')">
          <el-input v-model="freshForm.column"
                    :placeholder="t('gov.freshnessColumnHint')" />
        </el-form-item>
        <el-form-item :label="t('gov.freshnessHours')">
          <el-input-number v-model="freshForm.max_hours" :min="1"
                           :max="8760" />
        </el-form-item>
      </el-form>
      <p class="muted">{{ t("gov.freshnessHint") }}</p>
      <template #footer>
        <el-button @click="freshOpen = false">{{ t("common.cancel") }}</el-button>
        <el-button type="primary" :loading="saving"
                   @click="saveFreshness">{{ t("gov.save") }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="contractOpen" :title="t('gov.contractResult')"
               width="640px">
      <el-alert v-if="contractResult.ok" type="success" :closable="false"
                :title="t('gov.contractOk')" />
      <el-alert v-else type="error" :closable="false"
                :title="t('gov.contractFailed')" />
      <p class="muted">
        {{ contractResult.target }} · {{ contractResult.actual }} /
        {{ contractResult.expected }}
      </p>
      <el-table v-if="(contractResult.issues || []).length"
                :data="contractResult.issues" size="small">
        <el-table-column prop="kind" :label="t('gov.issueKind')"
                         width="120" />
        <el-table-column prop="column" :label="t('gov.issueColumn')"
                         min-width="140" />
        <el-table-column prop="expected" :label="t('gov.issueExpected')"
                         min-width="120" />
        <el-table-column prop="actual" :label="t('gov.issueActual')"
                         min-width="120" />
      </el-table>
      <template #footer>
        <el-button @click="contractOpen = false">
          {{ t("common.close") }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, canWrite, errMsg } from "../api";
import { t } from "../i18n";
import PageHeader from "../components/PageHeader.vue";

const tab = ref("domains");
const canEdit = canWrite();
const domains = ref([]);
const terms = ref([]);
const loading = ref(false);
const saving = ref(false);
const domainOpen = ref(false);
const termOpen = ref(false);
const domainForm = reactive({ id: null, name: "", owner: "",
                             description: "" });
const termForm = reactive({ id: null, term: "", definition: "",
                            domain_id: null, owner: "" });
const contracts = ref([]);
const contractOpen = ref(false);
const contractResult = ref({});
const freshOpen = ref(false);
const freshForm = reactive({ asset_id: null, column: "", max_hours: 24 });

async function loadContracts() {
  loading.value = true;
  try {
    contracts.value = (await api.get(
      "/governance/contracts?include_missing=true")).items || [];
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

async function checkContract(row) {
  try {
    contractResult.value = await api.post(
      `/assets/${row.asset_id}/contract/check`);
    contractOpen.value = true;
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function genContract(row) {
  try {
    await api.post(`/assets/${row.asset_id}/contract/generate`);
    ElMessage.success(t("gov.generated"));
    await loadContracts();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

function openFreshness(row) {
  freshForm.asset_id = row.asset_id;
  freshForm.column = (row.freshness && row.freshness.column) || "";
  freshForm.max_hours = (row.freshness && row.freshness.max_hours) || 24;
  freshOpen.value = true;
}

async function saveFreshness() {
  saving.value = true;
  try {
    const freshness = freshForm.column.trim()
      ? { column: freshForm.column.trim(),
          max_hours: freshForm.max_hours }
      : {};
    await api.patch(`/assets/${freshForm.asset_id}/contract`, { freshness });
    ElMessage.success(t("gov.contractUpdated"));
    freshOpen.value = false;
    await loadContracts();
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

async function setContract(row, patch) {
  try {
    await api.patch(`/assets/${row.asset_id}/contract`, patch);
    ElMessage.success(t("gov.contractUpdated"));
    await loadContracts();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

watch(tab, (name) => {
  if (name === "contracts") loadContracts();
});

async function load() {
  loading.value = true;
  try {
    const [d, g] = await Promise.all([
      api.get("/governance/domains"),
      api.get("/governance/terms"),
    ]);
    domains.value = d.items || [];
    terms.value = g.items || [];
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

function openDomain(row = null) {
  Object.assign(domainForm, row
    ? { id: row.id, name: row.name, owner: row.owner,
        description: row.description }
    : { id: null, name: "", owner: "", description: "" });
  domainOpen.value = true;
}

async function saveDomain() {
  if (!domainForm.name.trim()) return;
  saving.value = true;
  try {
    const body = { name: domainForm.name, owner: domainForm.owner,
                   description: domainForm.description };
    if (domainForm.id) {
      await api.put(`/governance/domains/${domainForm.id}`, body);
    } else {
      await api.post("/governance/domains", body);
    }
    ElMessage.success(t(domainForm.id ? "gov.updated" : "gov.created"));
    domainOpen.value = false;
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

async function removeDomain(row) {
  try {
    await ElMessageBox.confirm(
      t("gov.deleteDomainConfirm").replace("{name}", row.name),
      t("gov.delete"), { type: "warning" });
    await api.del(`/governance/domains/${row.id}`);
    ElMessage.success(t("gov.deleted"));
    await load();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

function openTerm(row = null) {
  Object.assign(termForm, row
    ? { id: row.id, term: row.term, definition: row.definition,
        domain_id: row.domain_id, owner: row.owner }
    : { id: null, term: "", definition: "", domain_id: null, owner: "" });
  termOpen.value = true;
}

async function saveTerm() {
  if (!termForm.term.trim()) return;
  saving.value = true;
  try {
    const body = { term: termForm.term, definition: termForm.definition,
                   domain_id: termForm.domain_id, owner: termForm.owner };
    if (termForm.id) {
      await api.put(`/governance/terms/${termForm.id}`, body);
    } else {
      await api.post("/governance/terms", body);
    }
    ElMessage.success(t(termForm.id ? "gov.updated" : "gov.created"));
    termOpen.value = false;
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

async function removeTerm(row) {
  try {
    await ElMessageBox.confirm(
      t("gov.deleteTermConfirm").replace("{term}", row.term),
      t("gov.delete"), { type: "warning" });
    await api.del(`/governance/terms/${row.id}`);
    ElMessage.success(t("gov.deleted"));
    await load();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

onMounted(load);
</script>

<style scoped>
.toolbar { display: flex; gap: 10px; align-items: center; margin: 10px 0; }
.spacer { flex: 1; }
.hint { font-size: 12px; color: #6b7280; }
.muted { font-size: 11px; color: #94a3b8; margin-top: 2px; }
</style>
