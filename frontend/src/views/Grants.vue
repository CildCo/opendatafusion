<template>
  <div class="page">
    <page-header icon="grant" :title="t('menu.grants')"
                 :intro="t('grants.intro')" />
    <div class="toolbar">
      <el-tag size="small" type="info">{{ t("grants.crossProject") }}</el-tag>
      <div class="spacer" />
      <el-button size="small" @click="loadAll" :loading="loading">
        {{ t("grants.refresh") }}
      </el-button>
    </div>

    <el-card shadow="never">
      <el-tabs v-model="tab">
        <el-tab-pane :label="t('grants.tabCatalog')" name="catalog">
          <el-table :data="catalog" size="small"
                    :empty-text="t('grants.emptyCatalog')">
            <el-table-column prop="name" :label="t('grants.colInterface')"
                             min-width="180" />
            <el-table-column :label="t('grants.colType')" width="120">
              <template #default="{ row }">
                <el-tag size="small" effect="plain">
                  {{ typeLabel(row.asset_type) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="key" label="Key" min-width="220">
              <template #default="{ row }">
                <span class="mono">{{ row.key }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="owner_project"
                             :label="t('grants.colProject')" width="150" />
            <el-table-column :label="t('grants.colAction')" width="120">
              <template #default="{ row }">
                <el-button v-if="!row.owned" link type="primary"
                           @click="openRequest(row)">
                  {{ t("grants.requestAccess") }}
                </el-button>
                <span v-else class="hint">{{ t("grants.thisProject") }}</span>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="t('grants.tabShared')" name="shared">
          <el-table :data="shared" size="small"
                    :empty-text="t('grants.emptyShared')">
            <el-table-column prop="name" :label="t('grants.colInterface')"
                             min-width="180" />
            <el-table-column :label="t('grants.colType')" width="120">
              <template #default="{ row }">
                <el-tag size="small" effect="plain">
                  {{ typeLabel(row.asset_type) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="key" label="Key" min-width="220">
              <template #default="{ row }">
                <span class="mono">{{ row.key }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="owner_project"
                             :label="t('grants.colProject')" width="150" />
            <el-table-column :label="t('grants.colAction')" width="190">
              <template #default="{ row }">
                <el-button link @click="openShared(row)">
                  {{ t("grants.view") }}
                </el-button>
                <el-button v-if="row.asset_type === 'dataset'" link
                           type="primary" @click="previewShared(row)">
                  {{ t("grants.preview") }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="t('grants.tabOutgoing')" name="outgoing">
          <el-table :data="outgoing" size="small"
                    :empty-text="t('grants.emptyOutgoing')">
            <el-table-column prop="asset_name"
                             :label="t('grants.colInterface')" min-width="160" />
            <el-table-column prop="owner_project"
                             :label="t('grants.colProject')" width="140" />
            <el-table-column prop="note" :label="t('grants.colNote')"
                             min-width="180" />
            <el-table-column :label="t('grants.colStatus')" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="statusTone(row.status)">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="t('grants.colRequestedAt')" width="170">
              <template #default="{ row }">{{ fmt(row.created_at) }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="t('grants.tabIncoming')" name="incoming">
          <el-table :data="incoming" size="small"
                    :empty-text="t('grants.emptyIncoming')">
            <el-table-column prop="asset_name"
                             :label="t('grants.colInterface')" min-width="160" />
            <el-table-column prop="grantee_project"
                             :label="t('grants.colRequestingProject')"
                             width="140" />
            <el-table-column prop="requested_by"
                             :label="t('grants.colRequester')" width="110" />
            <el-table-column prop="note" :label="t('grants.colNote')"
                             min-width="180" />
            <el-table-column :label="t('grants.colStatus')" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="statusTone(row.status)">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="t('grants.colAction')" width="130">
              <template #default="{ row }">
                <template v-if="row.status === 'pending'">
                  <el-button link type="primary"
                             @click="decide(row, true)">
                    {{ t("grants.approve") }}
                  </el-button>
                  <el-button link type="danger"
                             @click="decide(row, false)">
                    {{ t("grants.reject") }}
                  </el-button>
                </template>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="t('grants.tabGrants')" name="grants">
          <el-table :data="grants" size="small"
                    :empty-text="t('grants.emptyGrants')">
            <el-table-column prop="asset_name"
                             :label="t('grants.colInterface')" min-width="180" />
            <el-table-column prop="grantee_project"
                             :label="t('grants.colGrantedProject')" width="150" />
            <el-table-column prop="granted_by"
                             :label="t('grants.colGrantedBy')" width="120" />
            <el-table-column :label="t('grants.colGrantedAt')" width="170">
              <template #default="{ row }">{{ fmt(row.created_at) }}</template>
            </el-table-column>
            <el-table-column :label="t('grants.colAction')" width="90">
              <template #default="{ row }">
                <el-button link type="danger"
                           @click="revoke(row)">
                  {{ t("grants.revoke") }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="t('grants.tabKeys')" name="keys">
          <div class="keys-head">
            <span class="hint">{{ t("grants.keyHint") }}</span>
            <el-button size="small" type="primary" :loading="issuing"
                       @click="issueKey">
              {{ t("grants.issueKey") }}
            </el-button>
          </div>
          <el-alert v-if="newKey" type="success" :closable="false"
                    show-icon style="margin: 10px 0">
            <p style="margin: 0 0 6px">{{ t("grants.keyCreated") }}</p>
            <p class="mono" style="margin: 0">AK: {{ newKey.ak }}</p>
            <p class="mono" style="margin: 0">SK: {{ newKey.sk }}</p>
          </el-alert>
          <el-table :data="keys" size="small"
                    :empty-text="t('grants.emptyKeys')">
            <el-table-column prop="ak" label="Access Key" min-width="240">
              <template #default="{ row }">
                <span class="mono">{{ row.ak }}</span>
              </template>
            </el-table-column>
            <el-table-column :label="t('grants.colStatus')" width="110">
              <template #default="{ row }">
                <el-tag size="small" :type="row.enabled ? 'success' : 'info'">
                  {{ row.enabled ? t("grants.valid") : t("grants.revoked") }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="t('grants.colAction')" width="100">
              <template #default="{ row }">
                <el-button v-if="row.enabled" link type="danger"
                           @click="revokeKey(row)">
                  {{ t("grants.revokeKey") }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog v-model="sharedOpen" :title="t('grants.sharedDetail')"
               width="560px">
      <el-descriptions :column="1" border size="small"
                       v-loading="sharedLoading">
        <el-descriptions-item :label="t('grants.colInterface')">
          {{ sharedDetail.name }} · <span class="mono">{{ sharedDetail.key }}</span>
        </el-descriptions-item>
        <el-descriptions-item :label="t('grants.colType')">
          {{ typeLabel(sharedDetail.asset_type) }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('grants.colProject')">
          {{ sharedDetail.owner_project }}
        </el-descriptions-item>
        <el-descriptions-item v-if="sharedDetail.layer"
                              :label="t('grants.layer')">
          {{ sharedDetail.layer }}
        </el-descriptions-item>
        <el-descriptions-item v-if="sharedDetail.materialization"
                              :label="t('grants.materialization')">
          {{ sharedDetail.materialization }}
        </el-descriptions-item>
        <el-descriptions-item v-if="sharedDetail.target"
                              :label="t('grants.targetTable')">
          <span class="mono">{{ sharedDetail.target }}</span>
        </el-descriptions-item>
      </el-descriptions>
      <el-table :data="sharedDetail.columns || []" size="small"
                style="margin-top: 10px">
        <el-table-column prop="name" :label="t('quality.column')" />
        <el-table-column prop="type" :label="t('grants.colType')" />
      </el-table>
      <el-table v-if="sharedDetail.params && sharedDetail.params.length"
                :data="sharedDetail.params" size="small"
                style="margin-top: 10px">
        <el-table-column prop="name" :label="t('grants.params')" />
        <el-table-column prop="type" :label="t('grants.colType')" />
      </el-table>
      <template #footer>
        <el-button @click="sharedOpen = false">{{ t("common.close") }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="sharedPreviewOpen"
               :title="t('grants.previewTitle')" width="760px">
      <el-table v-if="sharedPreview.rows && sharedPreview.rows.length"
                :data="sharedPreview.rows" size="small" height="380" border>
        <el-table-column v-for="c in sharedPreview.columns" :key="c"
                         :prop="c" :label="c" min-width="130"
                         show-overflow-tooltip />
      </el-table>
      <el-empty v-else :description="t('grants.noPreview')"
                :image-size="60" />
      <template #footer>
        <el-button @click="sharedPreviewOpen = false">
          {{ t("common.close") }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="requestOpen" :title="t('grants.dialogTitle')"
               width="480px">
      <p class="hint">
        {{ tr("grants.targetHint",
              { name: target?.name, project: target?.owner_project }) }}
      </p>
      <el-input v-model="note" type="textarea" :rows="3"
                :placeholder="t('grants.notePlaceholder')" />
      <template #footer>
        <el-button @click="requestOpen = false">
          {{ t("grants.cancel") }}
        </el-button>
        <el-button type="primary" :loading="saving" @click="submitRequest">
          {{ t("grants.submitRequest") }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg, getProject } from "../api";
import { fmtDate, t } from "../i18n";
import PageHeader from "../components/PageHeader.vue";

function tr(key, vars = {}) {
  return Object.entries(vars).reduce(
    (s, [k, v]) => s.split(`{${k}}`).join(v ?? ""), t(key));
}

const tab = ref("catalog");
const catalog = ref([]);
const outgoing = ref([]);
const incoming = ref([]);
const grants = ref([]);
const shared = ref([]);
const sharedOpen = ref(false);
const sharedLoading = ref(false);
const sharedDetail = reactive({ columns: [], params: [] });
const sharedPreviewOpen = ref(false);
const sharedPreview = ref({ columns: [], rows: [] });
const loading = ref(false);
const saving = ref(false);
const requestOpen = ref(false);
const target = ref(null);
const note = ref("");
const keys = ref([]);
const newKey = ref(null);
const issuing = ref(false);

async function loadKeys() {
  const pid = getProject() || 1;
  try {
    keys.value = await api.get(`/projects/${pid}/aksk`);
  } catch (e) {
    keys.value = [];
  }
}

async function issueKey() {
  const pid = getProject() || 1;
  try {
    await ElMessageBox.confirm(
      t("grants.issueConfirm"), t("grants.issueTitle"));
  } catch (e) {
    return;
  }
  issuing.value = true;
  try {
    newKey.value = await api.post(`/projects/${pid}/aksk`);
    await loadKeys();
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    issuing.value = false;
  }
}

async function revokeKey(row) {
  const pid = getProject() || 1;
  try {
    await ElMessageBox.confirm(
      tr("grants.revokeKeyConfirm", { ak: row.ak }),
      t("grants.revokeKeyTitle"), { type: "warning" });
    await api.del(`/projects/${pid}/aksk/${encodeURIComponent(row.ak)}`);
    await loadKeys();
    ElMessage.success(t("grants.revokedMsg"));
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

function fmt(v) {
  if (!v) return "-";
  return fmtDate(v);
}
function typeLabel(type) {
  return {
    api: t("grants.typeApi"), dataset: t("grants.typeDataset"),
    model: t("grants.typeModel"),
  }[type] || type;
}

async function openShared(row) {
  sharedLoading.value = true;
  sharedOpen.value = true;
  try {
    const data = await api.get(`/shared-assets/${row.asset_id}`);
    Object.assign(sharedDetail, { columns: [], params: [], ...data });
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    sharedLoading.value = false;
  }
}

async function previewShared(row) {
  try {
    const data = await api.get(
      `/shared-assets/${row.asset_id}/preview?limit=50`);
    sharedPreview.value = { columns: data.columns || [],
                            rows: data.rows || [] };
    sharedPreviewOpen.value = true;
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

function statusTone(s) {
  return { approved: "success", pending: "warning",
           rejected: "danger" }[s] || "info";
}

async function loadAll() {
  loading.value = true;
  try {
    const [c, o, i, g, sh] = await Promise.all([
      api.get("/asset-catalog"),
      api.get("/asset-requests?direction=outgoing"),
      api.get("/asset-requests?direction=incoming"),
      api.get("/asset-grants"),
      api.get("/shared-assets"),
    ]);
    catalog.value = c;
    outgoing.value = o;
    incoming.value = i;
    grants.value = g;
    shared.value = sh;
    await loadKeys();
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

function openRequest(row) {
  target.value = row;
  note.value = "";
  requestOpen.value = true;
}

async function submitRequest() {
  saving.value = true;
  try {
    await api.post("/asset-requests", {
      asset_id: target.value.id, note: note.value,
    });
    ElMessage.success(t("grants.requestSubmitted"));
    requestOpen.value = false;
    await loadAll();
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

async function decide(row, approve) {
  try {
    await ElMessageBox.confirm(
      tr("grants.decideConfirm", {
        action: t(approve ? "grants.approve" : "grants.reject"),
        asset: row.asset_name,
        project: row.grantee_project,
      }), t("grants.decideTitle"));
    await api.post(`/asset-requests/${row.id}/${approve ? "approve"
      : "reject"}`);
    ElMessage.success(t(approve ? "grants.approvedMsg" : "grants.rejectedMsg"));
    await loadAll();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

async function revoke(row) {
  try {
    await ElMessageBox.confirm(
      tr("grants.revokeConfirm", {
        project: row.grantee_project, asset: row.asset_name,
      }), t("grants.revokeGrantTitle"));
    await api.del(`/asset-grants/${row.id}`);
    ElMessage.success(t("grants.grantRevoked"));
    await loadAll();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

onMounted(loadAll);
</script>

<style scoped>
.toolbar { display: flex; gap: 10px; align-items: center;
           margin-bottom: 12px; }
.title { font-size: 16px; font-weight: 700; color: #0f172a; }
.spacer { flex: 1; }
.mono { font-family: ui-monospace, monospace; font-size: 11px; }
.hint { color: #6b7280; font-size: 12px; }
.keys-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
</style>
