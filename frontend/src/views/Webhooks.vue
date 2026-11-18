<template>
  <div class="page">
    <div class="toolbar">
      <el-tag size="small" type="info">HMAC Webhook</el-tag>
      <div class="spacer" />
      <el-button size="small" @click="load" :loading="loading">
        {{ t("hooks.refresh") }}
      </el-button>
      <el-button v-if="canEdit" type="primary" size="small"
                 @click="openCreate">
        {{ t("hooks.create") }}
      </el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="rows" size="small" :empty-text="t('hooks.empty')">
        <el-table-column prop="name" :label="t('hooks.colName')"
                         min-width="140" />
        <el-table-column prop="url" :label="t('hooks.colUrl')" min-width="240"
                         show-overflow-tooltip />
        <el-table-column :label="t('hooks.colEvents')" min-width="180">
          <template #default="{ row }">
            <span v-if="!row.events?.length" class="hint">
              {{ t("hooks.allEvents") }}
            </span>
            <el-tag v-for="e in row.events" :key="e" size="small"
                    style="margin-right: 4px">{{ e }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('hooks.colStatus')" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="row.enabled ? 'success' : 'info'">
              {{ row.enabled ? t("hooks.enabled") : t("hooks.disabled") }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('hooks.colLastDelivery')" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.last_status" size="small"
                    :type="row.last_status === 'success' ? 'success'
                      : 'danger'">
              {{ row.last_status }}
            </el-tag>
            <span v-else class="hint">-</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('hooks.colActions')" width="230">
          <template #default="{ row }">
            <el-button link @click="showDeliveries(row)">
              {{ t("hooks.records") }}
            </el-button>
            <el-button v-if="canEdit" link @click="test(row)">
              {{ t("hooks.test") }}
            </el-button>
            <el-button v-if="canEdit" link @click="openEdit(row)">
              {{ t("hooks.edit") }}
            </el-button>
            <el-button v-if="canEdit" link type="danger"
                       @click="remove(row)">
              {{ t("hooks.delete") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialog"
               :title="form.id ? t('hooks.editTitle') : t('hooks.createTitle')"
               width="560px">
      <el-form label-width="90px">
        <el-form-item :label="t('hooks.name')" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item :label="t('hooks.url')" required>
          <el-input v-model="form.url"
                    placeholder="https://example.com/hooks/odf" />
        </el-form-item>
        <el-form-item :label="t('hooks.events')">
          <el-select v-model="form.events" multiple clearable
                     :placeholder="t('hooks.eventsPlaceholder')"
                     style="width: 100%">
            <el-option v-for="e in eventOptions" :key="e" :value="e"
                       :label="e" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('hooks.enable')">
          <el-switch v-model="form.enabled" />
        </el-form-item>
        <el-form-item v-if="!form.id" :label="t('hooks.signingSecret')">
          <el-input v-model="form.secret"
                    :placeholder="t('hooks.secretPlaceholder')" />
        </el-form-item>
        <el-form-item v-else :label="t('hooks.secret')">
          <el-checkbox v-model="form.rotate_secret">
            {{ t("hooks.rotateSecret") }}
          </el-checkbox>
        </el-form-item>
      </el-form>
      <el-alert v-if="createdSecret" type="success" :closable="false"
                :title="t('hooks.secretAlert')">
        <div class="mono">{{ createdSecret }}</div>
      </el-alert>
      <template #footer>
        <el-button @click="dialog = false">{{ t("hooks.cancel") }}</el-button>
        <el-button type="primary" :loading="saving" @click="save">
          {{ t("hooks.save") }}
        </el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="drawer" :title="t('hooks.drawerTitle')" size="620px"
               @open="loadDeliveries">
      <el-table :data="deliveries" size="small"
                :empty-text="t('hooks.emptyDeliveries')">
        <el-table-column prop="event" :label="t('hooks.colEvent')"
                         width="150" />
        <el-table-column :label="t('hooks.colStatus')" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'success'
              ? 'success' : (row.status === 'failed' ? 'danger' : 'warning')">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="attempts" :label="t('hooks.colAttempts')"
                         width="70" />
        <el-table-column prop="response_status" label="HTTP" width="70" />
        <el-table-column prop="error" :label="t('hooks.colError')"
                         min-width="160" show-overflow-tooltip />
        <el-table-column :label="t('hooks.colTime')" width="160">
          <template #default="{ row }">{{ fmt(row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg, getRole } from "../api";
import { t } from "../i18n";

function tr(key, vars = {}) {
  return Object.entries(vars).reduce(
    (s, [k, v]) => s.split(`{${k}}`).join(v ?? ""), t(key));
}

const canEdit = ["editor", "approver", "admin"].includes(getRole());
const rows = ref([]);
const eventOptions = ref([]);
const loading = ref(false);
const saving = ref(false);
const dialog = ref(false);
const drawer = ref(false);
const deliveries = ref([]);
const current = ref(null);
const createdSecret = ref("");
const form = reactive({ id: null, name: "", url: "", events: [],
                        enabled: true, secret: "", rotate_secret: false });

function fmt(v) {
  if (!v) return "-";
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? v : d.toLocaleString("zh-CN");
}

async function load() {
  loading.value = true;
  try {
    rows.value = await api.get("/webhooks");
    eventOptions.value = await api.get("/webhooks/events");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

function reset() {
  Object.assign(form, { id: null, name: "", url: "", events: [],
                        enabled: true, secret: "", rotate_secret: false });
  createdSecret.value = "";
}

function openCreate() {
  reset();
  dialog.value = true;
}

function openEdit(row) {
  reset();
  Object.assign(form, { id: row.id, name: row.name, url: row.url,
                        events: [...(row.events || [])],
                        enabled: row.enabled });
  dialog.value = true;
}

async function save() {
  if (!form.name.trim() || !form.url.trim()) {
    ElMessage.error(t("hooks.nameUrlRequired"));
    return;
  }
  saving.value = true;
  try {
    let r;
    if (form.id) {
      r = await api.put(`/webhooks/${form.id}`, {
        name: form.name, url: form.url, events: form.events,
        enabled: form.enabled, rotate_secret: form.rotate_secret,
      });
    } else {
      r = await api.post("/webhooks", {
        name: form.name, url: form.url, events: form.events,
        enabled: form.enabled, secret: form.secret || null,
      });
    }
    if (r?.secret) {
      createdSecret.value = r.secret;
      form.id = r.id;
      form.rotate_secret = false;
    } else {
      dialog.value = false;
    }
    ElMessage.success(t("hooks.saved"));
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

async function test(row) {
  try {
    await api.post(`/webhooks/${row.id}/test`);
    ElMessage.success(t("hooks.testQueued"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(
      tr("hooks.deleteConfirm", { name: row.name }), t("hooks.deleteTitle"));
    await api.del(`/webhooks/${row.id}`);
    ElMessage.success(t("hooks.deleted"));
    await load();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

async function showDeliveries(row) {
  current.value = row;
  drawer.value = true;
}

async function loadDeliveries() {
  if (!current.value) return;
  try {
    deliveries.value = await api.get(
      `/webhooks/${current.value.id}/deliveries`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

onMounted(load);
</script>

<style scoped>
.toolbar { display: flex; gap: 10px; align-items: center;
           margin-bottom: 12px; }
.title { font-size: 16px; font-weight: 700; color: #0f172a; }
.spacer { flex: 1; }
.hint { color: #6b7280; font-size: 12px; }
.mono { font-family: ui-monospace, monospace; font-size: 12px;
        word-break: break-all; }
</style>
