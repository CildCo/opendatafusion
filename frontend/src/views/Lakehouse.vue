<template>
  <div class="page">
    <page-header icon="lakehouse" :title="t('lh.title')"
                 :intro="t('lh.intro')" />
    <div class="toolbar">
      <el-select v-model="datasource" filterable style="width: 230px"
                 @change="load">
        <el-option v-for="d in datasources" :key="d.id" :value="d.id"
                   :label="`${d.name} (${d.kind})`" />
      </el-select>
      <el-input v-model="schema" :placeholder="t('lh.schema')"
                clearable style="width: 180px" @change="load" />
      <div class="spacer" />
      <el-button @click="load" :loading="loading">{{ t("lh.refresh") }}</el-button>
      <el-button :disabled="!datasource" @click="openSchedule">
        {{ t("lh.schedules") }}
      </el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="tables" size="small" v-loading="loading">
        <el-table-column prop="table" :label="t('lh.table')" min-width="200">
          <template #default="{ row }">
            <span class="mono">{{ row.table }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('lh.columns')" width="100">
          <template #default="{ row }">{{ row.columns?.length || 0 }}</template>
        </el-table-column>
        <el-table-column :label="t('lh.actions')" min-width="420">
          <template #default="{ row }">
            <el-button link @click="openHealth(row)">{{ t("lh.health") }}</el-button>
            <el-button link @click="openSnapshots(row)">{{ t("lh.snapshots") }}</el-button>
            <el-button link @click="openTimeTravel(row)">{{ t("lh.timeTravel") }}</el-button>
            <el-button link @click="openMaintain(row)">{{ t("lh.maintain") }}</el-button>
            <el-button link @click="scheduleFor(row)">{{ t("lh.schedule") }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <empty-state v-if="!loading && !tables.length" :title="t('lh.empty')"
                   :description="t('lh.intro')" />
    </el-card>

    <el-drawer v-model="healthOpen" :title="t('lh.health')" size="560px">
      <template v-if="health">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item :label="t('lh.status')">
            <el-tag size="small" :type="healthTone">
              {{ health.status }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="t('lh.files')">
            {{ health.files }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('lh.size')">
            {{ fmtSize(health.size_bytes) }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('lh.smallFiles')">
            {{ health.small_files }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('lh.snapshots')">
            {{ health.snapshots }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('lh.partitions')">
            {{ health.partitions }}
          </el-descriptions-item>
        </el-descriptions>
        <ul v-if="health.issues?.length" class="issues">
          <li v-for="issue in health.issues" :key="issue">{{ issue }}</li>
        </ul>
      </template>
    </el-drawer>

    <el-drawer v-model="snapshotOpen" :title="t('lh.snapshots')" size="720px">
      <el-table :data="snapshots" size="small">
        <el-table-column prop="snapshot_id" label="ID" width="150" />
        <el-table-column prop="committed_at" :label="t('lh.time')"
                         min-width="170" />
        <el-table-column prop="operation" :label="t('lh.operation')"
                         width="110" />
        <el-table-column prop="summary" :label="t('lh.summary')" />
      </el-table>
    </el-drawer>

    <el-dialog v-model="travelOpen" :title="t('lh.timeTravel')" width="760px">
      <el-form label-width="110px" size="small">
        <el-form-item :label="t('lh.snapshot')">
          <el-select v-model="travel.snapshot_id" filterable clearable
                     style="width: 100%">
            <el-option v-for="s in snapshots" :key="s.snapshot_id"
                       :value="s.snapshot_id"
                       :label="`${s.snapshot_id} · ${s.committed_at}`" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('lh.timestamp')">
          <el-input v-model="travel.timestamp"
                    placeholder="2026-11-24 10:00:00" />
        </el-form-item>
      </el-form>
      <div class="actions">
        <el-button size="small" type="primary" :loading="traveling"
                   @click="runTravel">{{ t("lh.query") }}</el-button>
      </div>
      <el-table v-if="travelRows.length" :data="travelRows" size="small"
                height="320" style="margin-top: 10px">
        <el-table-column v-for="c in travelColumns" :key="c" :prop="c"
                         :label="c" min-width="120" />
      </el-table>
    </el-dialog>

    <el-dialog v-model="maintainOpen" :title="t('lh.maintain')" width="560px">
      <el-form label-width="120px" size="small">
        <el-form-item :label="t('lh.optimize')">
          <el-switch v-model="maintain.optimize" />
        </el-form-item>
        <el-form-item :label="t('lh.expire')">
          <el-switch v-model="maintain.expire_snapshots" />
        </el-form-item>
        <el-form-item :label="t('lh.retention')">
          <el-input v-model="maintain.retention" placeholder="7d" />
        </el-form-item>
        <el-form-item :label="t('lh.threshold')">
          <el-input v-model="maintain.file_size_threshold"
                    placeholder="128MB" />
        </el-form-item>
      </el-form>
      <el-table v-if="maintain.results.length" :data="maintain.results"
                size="small">
        <el-table-column prop="table" :label="t('lh.table')" />
        <el-table-column prop="optimize" :label="t('lh.optimize')" />
        <el-table-column prop="expire" :label="t('lh.expire')" />
      </el-table>
      <template #footer>
        <el-button @click="maintainOpen = false">{{ t("lh.close") }}</el-button>
        <el-button type="primary" :loading="maintain.running"
                   @click="runMaintain">{{ t("lh.execute") }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="scheduleOpen" :title="t('lh.schedules')" width="760px">
      <el-form label-width="120px" size="small">
        <el-form-item :label="t('lh.table')">
          <el-input v-model="schedule.table_name"
                    :placeholder="t('lh.allTables')" />
        </el-form-item>
        <el-form-item :label="t('lh.cron')">
          <el-input v-model="schedule.cron" placeholder="0 0 3 * * *" />
        </el-form-item>
        <el-form-item :label="t('lh.enabled')">
          <el-switch v-model="schedule.enabled" />
        </el-form-item>
        <el-form-item :label="t('lh.optimize')">
          <el-switch v-model="schedule.optimize" />
          <el-switch v-model="schedule.expire_snapshots"
                     style="margin-left: 16px" />
        </el-form-item>
        <el-form-item :label="t('lh.retention')">
          <el-input v-model="schedule.retention" placeholder="7d" />
        </el-form-item>
        <el-form-item :label="t('lh.threshold')">
          <el-input v-model="schedule.file_size_threshold"
                    placeholder="128MB" />
        </el-form-item>
      </el-form>
      <el-button size="small" type="primary" :loading="saving"
                 @click="saveSchedule">{{ t("lh.saveSchedule") }}</el-button>
      <el-table :data="schedules" size="small" style="margin-top: 12px">
        <el-table-column prop="table_name" :label="t('lh.table')" min-width="120">
          <template #default="{ row }">{{ row.table_name || "*" }}</template>
        </el-table-column>
        <el-table-column prop="cron" :label="t('lh.cron')" width="130" />
        <el-table-column prop="last_status" :label="t('lh.status')" width="90" />
        <el-table-column :label="t('lh.actions')" width="150">
          <template #default="{ row }">
            <el-button link @click="runSchedule(row)">{{ t("lh.runNow") }}</el-button>
            <el-button link type="danger" @click="removeSchedule(row)">
              {{ t("lh.delete") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../api";
import { t } from "../i18n";
import PageHeader from "../components/PageHeader.vue";
import EmptyState from "../components/EmptyState.vue";

const datasources = ref([]);
const datasource = ref(null);
const schema = ref("");
const tables = ref([]);
const loading = ref(false);
const healthOpen = ref(false);
const snapshotOpen = ref(false);
const travelOpen = ref(false);
const maintainOpen = ref(false);
const scheduleOpen = ref(false);
const health = ref(null);
const snapshots = ref([]);
const travelRows = ref([]);
const travelColumns = ref([]);
const traveling = ref(false);
const maintain = reactive({ row: null, optimize: true,
                            expire_snapshots: true, retention: "7d",
                            file_size_threshold: "128MB", results: [],
                            running: false });
const schedule = reactive({ table_name: "", cron: "0 0 3 * * *",
                            enabled: true, optimize: true,
                            expire_snapshots: true, retention: "7d",
                            file_size_threshold: "128MB" });
const schedules = ref([]);
const saving = ref(false);
const travel = reactive({ snapshot_id: null, timestamp: "" });

const healthTone = computed(() => ({
  ok: "success", warning: "warning", critical: "danger",
}[health.value?.status] || "info"));

function fmtSize(value) {
  const n = Number(value || 0);
  if (n > 1024 ** 3) return (n / 1024 ** 3).toFixed(1) + " GB";
  if (n > 1024 ** 2) return (n / 1024 ** 2).toFixed(1) + " MB";
  if (n > 1024) return (n / 1024).toFixed(1) + " KB";
  return n + " B";
}

function params(row) {
  return `datasource_id=${datasource.value}` +
    (schema.value ? `&schema=${encodeURIComponent(schema.value)}` : "") +
    (row ? `&table=${encodeURIComponent(row)}` : "");
}

async function load() {
  if (!datasource.value) return;
  loading.value = true;
  try {
    const q = `datasource_id=${datasource.value}` +
      (schema.value ? `&schema=${encodeURIComponent(schema.value)}` : "");
    const r = await api.get(`/lakehouse/tables?${q}`);
    tables.value = r.tables || [];
    schema.value = r.schema || schema.value;
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

async function openHealth(row) {
  try {
    health.value = await api.get(
      `/lakehouse/tables/${encodeURIComponent(row.table)}/health?` +
      params());
    healthOpen.value = true;
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function openSnapshots(row) {
  try {
    const r = await api.get(
      `/lakehouse/tables/${encodeURIComponent(row.table)}/snapshots?` +
      params());
    snapshots.value = r.snapshots || [];
    snapshotOpen.value = true;
    maintain.row = row.table;
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function openTimeTravel(row) {
  maintain.row = row.table;
  await openSnapshots(row);
  snapshotOpen.value = false;
  travel.snapshot_id = snapshots.value[0]?.snapshot_id || null;
  travel.timestamp = "";
  travelRows.value = [];
  travelOpen.value = true;
}

async function runTravel() {
  traveling.value = true;
  try {
    const r = await api.post(
      `/lakehouse/tables/${encodeURIComponent(maintain.row)}/time-travel`, {
        datasource_id: datasource.value,
        schema_name: schema.value || null,
        snapshot_id: travel.snapshot_id || null,
        timestamp: travel.snapshot_id ? null : (travel.timestamp || null),
        limit: 100,
      });
    travelColumns.value = r.columns || [];
    travelRows.value = r.rows || [];
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    traveling.value = false;
  }
}

function openMaintain(row) {
  maintain.row = row.table;
  maintain.results = [];
  maintainOpen.value = true;
}

async function runMaintain() {
  maintain.running = true;
  try {
    const r = await api.post("/lakehouse/maintain", {
      datasource_id: datasource.value,
      schema_name: schema.value || null,
      tables: [maintain.row],
      optimize: maintain.optimize,
      expire_snapshots: maintain.expire_snapshots,
      retention: maintain.retention,
      file_size_threshold: maintain.file_size_threshold,
    });
    maintain.results = r.results || [];
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    maintain.running = false;
  }
}

async function openSchedule() {
  scheduleOpen.value = true;
  try {
    schedules.value = await api.get(
      `/lakehouse/maintenance?datasource_id=${datasource.value}`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

function scheduleFor(row) {
  schedule.table_name = row.table;
  openSchedule();
}

async function saveSchedule() {
  saving.value = true;
  try {
    await api.put("/lakehouse/maintenance", {
      datasource_id: datasource.value,
      schema_name: schema.value || null,
      ...schedule,
    });
    ElMessage.success(t("lh.saved"));
    await openSchedule();
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

async function runSchedule(row) {
  try {
    await api.post(`/lakehouse/maintenance/${row.id}/run`, {});
    ElMessage.success(t("lh.queued"));
    await openSchedule();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function removeSchedule(row) {
  try {
    await ElMessageBox.confirm(t("lh.deleteConfirm"), t("lh.schedules"));
    await api.del(`/lakehouse/maintenance/${row.id}`);
    await openSchedule();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

onMounted(async () => {
  try {
    const rows = await api.get("/datasources");
    datasources.value = rows.filter((d) => d.kind === "trino");
    if (datasources.value.length) {
      datasource.value = datasources.value[0].id;
      await load();
    }
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
});
</script>

<style scoped>
.toolbar { display: flex; gap: 8px; align-items: center; margin-bottom: 12px;
           flex-wrap: wrap; }
.spacer { flex: 1; }
.mono { font-family: ui-monospace, monospace; font-size: 12px; }
.issues { margin: 12px 0 0; padding-left: 18px; color: #b45309;
          font-size: 12px; }
.actions { display: flex; justify-content: flex-end; }
</style>
