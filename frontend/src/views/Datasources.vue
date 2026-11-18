<template>
  <div class="page">
    <div class="toolbar">
      <el-input v-model="q" :placeholder="t('ds.searchPlaceholder')" clearable
                style="width: 240px" :prefix-icon="Search" />
      <el-select v-model="kind" clearable :placeholder="t('ds.allKinds')" style="width: 150px">
        <el-option value="postgres" label="PostgreSQL" />
        <el-option value="mysql" label="MySQL" />
        <el-option value="mariadb" label="MariaDB" />
        <el-option value="sqlite" label="SQLite" />
        <el-option value="http" label="HTTP API" />
        <el-option value="es" label="Elasticsearch" />
        <el-option value="oracle" label="Oracle" />
        <el-option value="mssql" label="SQL Server" />
        <el-option value="clickhouse" label="ClickHouse" />
        <el-option value="trino" label="Trino / Iceberg" />
        <el-option value="file" :label="t('ds.fileKind')" />
      </el-select>
      <div class="spacer" />
      <el-button @click="load" :loading="loading">{{ t("ds.refresh") }}</el-button>
      <el-button type="primary" @click="openCreate">{{ t("ds.new") }}</el-button>
    </div>

    <el-card shadow="never" class="card">
      <el-table :data="paged" size="small" v-loading="loading">
        <el-table-column prop="id" :label="t('ds.colId')" width="70" />
        <el-table-column prop="name" :label="t('ds.colName')" min-width="140" />
        <el-table-column prop="kind" :label="t('ds.colKind')" width="120">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.kind }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="dsn" :label="t('ds.colDsn')" min-width="320" />
        <el-table-column :label="t('ds.colActions')" width="320" fixed="right">
          <template #default="{ row }">
            <el-button link @click="test(row)">{{ t("ds.test") }}</el-button>
            <el-button link @click="sync(row)">{{ t("ds.sync") }}</el-button>
            <el-button link @click="showTables(row)">{{ t("ds.tablesButton") }}</el-button>
            <el-button link @click="openEdit(row)">{{ t("ds.edit") }}</el-button>
            <el-button link type="danger" @click="remove(row)">{{ t("ds.delete") }}</el-button>
            <el-button v-if="row.kind === 'trino'" link
                       @click="openMaintain(row)">{{ t("ds.maintain") }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !filtered.length" :description="t('ds.noDatasources')" />
      <div class="pager">
        <el-pagination v-model:current-page="page" :page-size="pageSize"
                       :total="filtered.length" layout="total, prev, pager, next"
                       small />
      </div>
    </el-card>

    <el-dialog v-model="editOpen" :title="t('ds.editTitle')" width="560px">
      <el-form label-width="90px">
        <el-form-item :label="t('ds.name')" required>
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item :label="t('ds.dsn')">
          <el-input v-model="editForm.dsn" type="textarea" :rows="3"
                    :placeholder="editPlaceholder" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editOpen = false">{{ t("ds.cancel") }}</el-button>
        <el-button type="primary" :loading="savingEdit"
                   @click="saveEdit">{{ t("ds.save") }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="dialog" :title="t('ds.new')" width="560px">
      <el-form label-width="90px">
        <el-form-item :label="t('ds.name')" required>
          <el-input v-model="form.name" :placeholder="t('ds.namePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('ds.colKind')" required>
          <el-select v-model="form.kind" style="width: 100%">
            <el-option value="postgres" label="PostgreSQL" />
            <el-option value="mysql" label="MySQL" />
            <el-option value="mariadb" label="MariaDB" />
            <el-option value="sqlite" label="SQLite" />
            <el-option value="http" label="HTTP API" />
            <el-option value="es" label="Elasticsearch" />
            <el-option value="oracle" label="Oracle" />
            <el-option value="mssql" label="SQL Server" />
            <el-option value="clickhouse" label="ClickHouse" />
        <el-option value="trino" label="Trino / Iceberg" />
            <el-option value="file" :label="t('ds.fileKind')" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('ds.dsn')" required>
          <el-input v-model="form.dsn" type="textarea" :rows="3"
                    :placeholder="dsnPlaceholder" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">{{ t("ds.cancel") }}</el-button>
        <el-button type="primary" :loading="saving" @click="create">{{ t("ds.save") }}</el-button>
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
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Search } from "@element-plus/icons-vue";
import { api, errMsg } from "../api";
import { t } from "../i18n";

const rows = ref([]);
const tables = ref([]);
const loading = ref(false);
const saving = ref(false);
const dialog = ref(false);
const editOpen = ref(false);
const savingEdit = ref(false);
const editRow = ref({});
const editForm = reactive({ name: "", dsn: "" });
const tablesDrawer = ref(false);
const current = ref({});
const q = ref("");
const kind = ref("");
const page = ref(1);
const pageSize = 10;
const form = reactive({ name: "", kind: "postgres", dsn: "" });
const maintainOpen = ref(false);
const maintain = reactive({ datasource_id: 0, schema: "", tables: "",
                            optimize: true, expire: true, retention: "7d",
                            running: false, results: [] });
const placeholders = {
  postgres: "postgresql+psycopg://user:pass@host:5432/db",
  mysql: "mysql://user:pass@host:3306/db",
  mariadb: "mariadb://user:pass@host:3306/db",
  sqlite: "sqlite:////data/odf/app.db",
  oracle: "oracle://user:pass@host:1521/service",
  mssql: "mssql://user:pass@host:1433/db",
  clickhouse: "clickhouse://user:pass@host:8123/db",
  trino: "trino://user@host:8080/iceberg/schema",
  file: "",
};
const localizedPlaceholders = {
  clickhouse: "ds.phClickhouse",
  trino: "ds.phTrino",
  file: "ds.phFile",
};
const dsnPlaceholder = computed(() => {
  const key = localizedPlaceholders[form.kind];
  return key ? t(key) : (placeholders[form.kind] || t("ds.dsn"));
});
const editPlaceholder = computed(() =>
  t("ds.editPlaceholderPrefix") + (editRow.value.dsn || ""));

const filtered = computed(() =>
  rows.value.filter((r) => {
    const hitQ = !q.value || (r.name + r.kind).toLowerCase().includes(q.value.toLowerCase());
    const hitK = !kind.value || r.kind === kind.value;
    return hitQ && hitK;
  })
);
const paged = computed(() =>
  filtered.value.slice((page.value - 1) * pageSize, page.value * pageSize)
);

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
  form.name = "";
  form.kind = "postgres";
  form.dsn = "";
  dialog.value = true;
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

function openEdit(row) {
  editRow.value = row;
  editForm.name = row.name;
  editForm.dsn = "";
  editOpen.value = true;
}

async function saveEdit() {
  if (!editForm.name) {
    ElMessage.warning(t("ds.nameRequired"));
    return;
  }
  savingEdit.value = true;
  try {
    const body = { name: editForm.name };
    if (editForm.dsn.trim()) body.dsn = editForm.dsn.trim();
    await api.put(`/datasources/${editRow.value.id}`, body);
    editOpen.value = false;
    await load();
    ElMessage.success(t("ds.saved"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    savingEdit.value = false;
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

async function create() {
  if (!form.name || !form.dsn) {
    ElMessage.warning(t("ds.nameDsnRequired"));
    return;
  }
  saving.value = true;
  try {
    await api.post("/datasources", form);
    dialog.value = false;
    await load();
    ElMessage.success(t("ds.created"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}
async function test(row) {
  try {
    const r = await api.post(`/datasources/${row.id}/test`);
    ElMessage[r.ok ? "success" : "error"](r.ok ? t("ds.connOk") : t("ds.connFailed"));
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
onMounted(load);
</script>

<style scoped>
.card {
  border-radius: 12px;
  border: 1px solid #e5e7eb;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}
</style>
