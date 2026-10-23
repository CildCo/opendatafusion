<template>
  <div class="page">
    <div class="toolbar">
      <el-input v-model="q" placeholder="搜索名称 / 类型" clearable
                style="width: 240px" :prefix-icon="Search" />
      <el-select v-model="kind" clearable placeholder="全部类型" style="width: 150px">
        <el-option value="postgres" label="PostgreSQL" />
        <el-option value="mysql" label="MySQL" />
        <el-option value="mariadb" label="MariaDB" />
        <el-option value="sqlite" label="SQLite" />
        <el-option value="http" label="HTTP API" />
        <el-option value="es" label="Elasticsearch" />
        <el-option value="oracle" label="Oracle" />
        <el-option value="mssql" label="SQL Server" />
        <el-option value="clickhouse" label="ClickHouse" />
        <el-option value="file" label="本地文件 (CSV/Excel/Parquet/JSON)" />
      </el-select>
      <div class="spacer" />
      <el-button @click="load" :loading="loading">刷新</el-button>
      <el-button type="primary" @click="openCreate">新建数据源</el-button>
    </div>

    <el-card shadow="never" class="card">
      <el-table :data="paged" size="small" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="kind" label="类型" width="120">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.kind }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="dsn" label="连接串（脱敏）" min-width="320" />
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button link @click="test(row)">测试</el-button>
            <el-button link @click="sync(row)">同步元数据</el-button>
            <el-button link @click="showTables(row)">表</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !filtered.length" description="还没有数据源" />
      <div class="pager">
        <el-pagination v-model:current-page="page" :page-size="pageSize"
                       :total="filtered.length" layout="total, prev, pager, next"
                       small />
      </div>
    </el-card>

    <el-dialog v-model="dialog" title="新建数据源" width="560px">
      <el-form label-width="90px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="例如：生产 PG" />
        </el-form-item>
        <el-form-item label="类型" required>
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
            <el-option value="file" label="本地文件 (CSV/Excel/Parquet/JSON)" />
          </el-select>
        </el-form-item>
        <el-form-item label="连接串" required>
          <el-input v-model="form.dsn" type="textarea" :rows="3"
                    :placeholder="dsnPlaceholder" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="create">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="tablesDrawer" :title="'表 · ' + current.name" size="520px">
      <el-table :data="tables" size="small">
        <el-table-column prop="schema" label="Schema" width="100" />
        <el-table-column prop="table" label="表" />
        <el-table-column label="字段数" width="90">
          <template #default="{ row }">{{ (row.columns || []).length }}</template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!tables.length" description="尚未同步，请先点“同步元数据”" />
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { Search } from "@element-plus/icons-vue";
import { api, errMsg } from "../api";

const rows = ref([]);
const tables = ref([]);
const loading = ref(false);
const saving = ref(false);
const dialog = ref(false);
const tablesDrawer = ref(false);
const current = ref({});
const q = ref("");
const kind = ref("");
const page = ref(1);
const pageSize = 10;
const form = reactive({ name: "", kind: "postgres", dsn: "" });
const placeholders = {
  postgres: "postgresql+psycopg://user:pass@host:5432/db",
  mysql: "mysql://user:pass@host:3306/db",
  mariadb: "mariadb://user:pass@host:3306/db",
  sqlite: "sqlite:////data/odf/app.db",
  oracle: "oracle://user:pass@host:1521/service",
  mssql: "mssql://user:pass@host:1433/db",
  clickhouse: "clickhouse://user:pass@host:8123/db（TLS 用 8443）",
  file: "/data/odf/files/sales.csv 或 file:///data/odf/files/orders.xlsx",
};
const dsnPlaceholder = computed(() => placeholders[form.kind] || "连接串");

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
async function create() {
  if (!form.name || !form.dsn) {
    ElMessage.warning("名称和连接串必填");
    return;
  }
  saving.value = true;
  try {
    await api.post("/datasources", form);
    dialog.value = false;
    await load();
    ElMessage.success("已创建");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}
async function test(row) {
  try {
    const r = await api.post(`/datasources/${row.id}/test`);
    ElMessage[r.ok ? "success" : "error"](r.ok ? "连接正常" : "连接失败");
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}
async function sync(row) {
  try {
    const r = await api.post(`/datasources/${row.id}/sync`);
    ElMessage.success(`已同步 ${r.tables} 张表`);
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
