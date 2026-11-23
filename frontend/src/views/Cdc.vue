<template>
  <div class="page">
    <page-header icon="cdc" :title="t('menu.cdc')" :intro="t('cdc.intro')" />
    <div class="toolbar">
      <el-select v-model="status" clearable :placeholder="t('cdc.allStatus')" style="width: 140px">
        <el-option value="running" :label="t('cdc.running')" />
        <el-option value="paused" :label="t('cdc.paused')" />
        <el-option value="failed" :label="t('cdc.failed')" />
      </el-select>
      <div class="spacer" />
      <el-button v-if="canEdit" type="primary" @click="openCreate">{{ t("cdc.newSource") }}</el-button>
      <el-button :loading="loading" @click="load">{{ t("cdc.refresh") }}</el-button>
    </div>

    <el-card class="card" shadow="never">
      <el-table :data="filtered" size="small" v-loading="loading"
                @row-click="openDetail" row-class-name="clickable">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column :label="t('cdc.name')" min-width="200">
          <template #default="{ row }">
            <span class="entity-cell">
              <entity-icon type="cdc" :size="20" />
              <b>{{ row.name }}</b>
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="connector_name" :label="t('cdc.connector')" min-width="200" />
        <el-table-column :label="t('cdc.engine')" width="110">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">
              {{ (row.config && row.config.engine) || "postgres" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('cdc.subscribedTables')" min-width="200">
          <template #default="{ row }">
            {{ (row.config && row.config.table_list) || "-" }}
          </template>
        </el-table-column>
        <el-table-column :label="t('cdc.status')" width="110">
          <template #default="{ row }">
            <status-dot :status="row.status" :label="statusLabel(row.status)" />
          </template>
        </el-table-column>
        <el-table-column :label="t('cdc.createdAt')" width="200">
          <template #default="{ row }">{{ fmtDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column :label="t('cdc.actions')" width="240" fixed="right">
          <template #default="{ row }">
            <el-button link @click.stop="openDetail(row)">
              {{ t("cdc.viewDetail") }}
            </el-button>
            <el-button v-if="canEdit" link @click.stop="toggle(row)">
              {{ row.status === "paused" ? t("cdc.resume") : t("cdc.pause") }}
            </el-button>
            <el-button link @click.stop="refreshOne(row)">{{ t("cdc.refreshStatus") }}</el-button>
            <el-button v-if="canEdit" link type="danger" @click.stop="remove(row)">{{ t("cdc.delete") }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <empty-state v-if="!loading && !filtered.length"
                   :title="t('cdc.empty')"
                   :description="t('cdc.intro')"
                   :action-text="canEdit ? t('cdc.newSource') : ''"
                   @action="openCreate" />
    </el-card>

    <el-dialog v-model="dialog" :title="t('cdc.newSource')" width="560px">
      <el-form label-width="96px">
        <el-form-item :label="t('cdc.name')" required>
          <el-input v-model="form.name" :placeholder="t('cdc.namePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('cdc.engine')">
          <el-select v-model="form.engine" style="width: 100%"
                     @change="onEngine">
            <el-option value="postgres" label="PostgreSQL" />
            <el-option value="mysql" label="MySQL" />
            <el-option value="oracle" label="Oracle" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('cdc.host')" required>
          <el-input v-model="form.host" placeholder="cdc-postgres.stream.svc" />
        </el-form-item>
        <el-form-item :label="t('cdc.port')">
          <el-input-number v-model="form.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item :label="t('cdc.database')" required>
          <el-input v-model="form.database" />
        </el-form-item>
        <el-form-item :label="t('cdc.user')" required>
          <el-input v-model="form.user" />
        </el-form-item>
        <el-form-item :label="t('cdc.password')" required>
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="Schema">
          <el-input v-model="form.schema_list" :placeholder="schemaHint" />
        </el-form-item>
        <el-form-item :label="t('cdc.table')">
          <el-input v-model="form.table_list" :placeholder="tableHint" />
        </el-form-item>
        <el-form-item :label="t('cdc.kafkaBootstrap')">
          <el-input v-model="form.kafka_bootstrap" placeholder="kafka:9092" />
        </el-form-item>
        <el-form-item :label="t('cdc.topicPrefix')">
          <el-input v-model="form.topic_prefix" placeholder="odf" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">{{ t("cdc.cancel") }}</el-button>
        <el-button type="primary" :loading="saving" @click="create">{{ t("cdc.save") }}</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailOpen" :title="detail.name || t('cdc.detail')"
               size="560px">
      <el-descriptions :column="1" border v-loading="detailLoading">
        <el-descriptions-item :label="t('cdc.connector')">
          <span class="mono">{{ detail.connector_name }}</span>
        </el-descriptions-item>
        <el-descriptions-item :label="t('cdc.engine')">
          {{ (detail.config && detail.config.engine) || "postgres" }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('cdc.connectorState')">
          <el-tag :type="statusType(detail.status)" size="small">
            {{ statusLabel(detail.status) }}
          </el-tag>
          <span v-if="detail.state" class="hint" style="margin-left: 8px">
            {{ detail.state }}
          </span>
        </el-descriptions-item>
        <el-descriptions-item :label="t('cdc.failedTasks')">
          {{ detail.failed_tasks || 0 }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('cdc.createdAt')">
          {{ fmtDate(detail.created_at) }}
        </el-descriptions-item>
      </el-descriptions>

      <h4>{{ t("cdc.tasks") }}</h4>
      <el-table :data="detail.tasks || []" size="small">
        <el-table-column prop="id" :label="t('cdc.taskId')" width="70" />
        <el-table-column prop="state" :label="t('cdc.taskState')"
                         width="110" />
        <el-table-column :label="t('cdc.trace')">
          <template #default="{ row }">
            <span class="mono">{{ row.trace || "-" }}</span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!(detail.tasks || []).length"
                :description="t('cdc.noTasks')" :image-size="50" />

      <h4>{{ t("cdc.editTables") }}</h4>
      <div class="tables-row">
        <el-input v-model="tablesText"
                  placeholder="public.events,public.orders" />
        <el-button type="primary" :loading="savingTables"
                   @click="saveTables">{{ t("cdc.save") }}</el-button>
      </div>
      <div class="drawer-actions">
        <el-button @click="toggle(detail)">
          {{ detail.status === "paused" ? t("cdc.resume") : t("cdc.pause") }}
        </el-button>
        <el-button @click="refreshOne(detail)">
          {{ t("cdc.refreshStatus") }}
        </el-button>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, canWrite, errMsg } from "../api";
import { fmtDate, t } from "../i18n";
import EmptyState from "../components/EmptyState.vue";
import EntityIcon from "../components/EntityIcon.vue";
import PageHeader from "../components/PageHeader.vue";
import StatusDot from "../components/StatusDot.vue";

const rows = ref([]);
const canEdit = canWrite();
const loading = ref(false);
const saving = ref(false);
const dialog = ref(false);
const status = ref("");
const detailOpen = ref(false);
const detail = ref({});
const detailLoading = ref(false);
const tablesText = ref("");
const savingTables = ref(false);

const blank = () => ({
  engine: "postgres", name: "", host: "cdc-postgres.stream.svc", port: 5432,
  database: "cdc", user: "cdc", password: "",
  schema_list: "public", table_list: "", topic_prefix: "odf",
  kafka_bootstrap: "kafka:9092",
});

const PORTS = { postgres: 5432, mysql: 3306, oracle: 1521 };
const schemaHint = computed(() => ({
  postgres: "public", mysql: "shop", oracle: "ODF",
}[form.engine] || "public"));
const tableHint = computed(() => ({
  postgres: "public.events,public.orders",
  mysql: "shop.orders,shop.items",
  oracle: "ODF.EVENTS,ODF.ORDERS",
}[form.engine] || "public.events"));

function onEngine(value) {
  form.port = PORTS[value] || form.port;
  form.schema_list = { postgres: "public", mysql: "shop",
                       oracle: "ODF" }[value] || "public";
  form.table_list = "";
  if (/^cdc-postgres/.test(form.host)) form.host = "";
}
const form = reactive(blank());

const filtered = computed(() =>
  rows.value.filter((r) => !status.value || r.status === status.value));

function statusLabel(s) {
  return {
    running: t("cdc.running"), paused: t("cdc.paused"),
    failed: t("cdc.failed"), pending: t("cdc.pending"),
    stopped: t("cdc.stopped"), unknown: t("cdc.unknown"),
  }[s] || s;
}

function statusType(s) {
  return { running: "success", paused: "warning", failed: "danger" }[s]
    || "info";
}

async function load() {
  loading.value = true;
  try {
    rows.value = await api.get("/cdc/sources");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  Object.assign(form, blank());
  dialog.value = true;
}

async function create() {
  saving.value = true;
  try {
    const { name, password, ...config } = form;
    await api.post("/cdc/sources", { name, password, config });
    ElMessage.success(t("cdc.created"));
    dialog.value = false;
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

async function toggle(row) {
  const action = row.status === "paused" ? "resume" : "pause";
  try {
    await api.post(`/cdc/sources/${row.id}/${action}`);
    await load();
    if (detailOpen.value && detail.value.id === row.id) {
      await openDetail(row);
    }
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function refreshOne(row) {
  try {
    await api.post(`/cdc/sources/${row.id}/status`);
    await load();
    if (detailOpen.value && detail.value.id === row.id) {
      await openDetail(row);
    }
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function openDetail(row) {
  if (!row || !row.id) return;
  detailOpen.value = true;
  detailLoading.value = true;
  try {
    detail.value = await api.get(`/cdc/sources/${row.id}/detail`);
    tablesText.value = (detail.value.config || {}).table_list || "";
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    detailLoading.value = false;
  }
}

async function saveTables() {
  if (!detail.value.id) return;
  savingTables.value = true;
  try {
    await api.put(`/cdc/sources/${detail.value.id}/tables`,
                  { table_list: tablesText.value });
    ElMessage.success(t("cdc.tablesSaved"));
    await openDetail(detail.value);
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    savingTables.value = false;
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(
      t("cdc.deleteConfirm").replace("{name}", row.name),
      t("cdc.deleteTitle"), { type: "warning" });
  } catch (e) {
    return;
  }
  try {
    await api.del(`/cdc/sources/${row.id}`);
    ElMessage.success(t("cdc.deleted"));
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

onMounted(load);
</script>

<style scoped>
.entity-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.card { border-radius: 12px; border: 1px solid #e5e7eb; }
.mono { font-family: Consolas, "Courier New", monospace; font-size: 12px; }
.hint { color: #6b7280; font-size: 12px; }
.tables-row { display: flex; gap: 8px; align-items: center; }
.drawer-actions { display: flex; gap: 10px; margin-top: 16px; }
:deep(.clickable) { cursor: pointer; }
</style>
