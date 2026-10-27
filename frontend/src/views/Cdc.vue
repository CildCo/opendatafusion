<template>
  <div class="page">
    <div class="toolbar">
      <el-select v-model="status" clearable placeholder="全部状态" style="width: 140px">
        <el-option value="running" label="运行中" />
        <el-option value="paused" label="已暂停" />
        <el-option value="failed" label="失败" />
      </el-select>
      <div class="spacer" />
      <el-button type="primary" @click="openCreate">新建 CDC 源</el-button>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </div>

    <el-card class="card" shadow="never">
      <el-table :data="filtered" size="small" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column prop="connector_name" label="连接器" min-width="200" />
        <el-table-column label="订阅表" min-width="200">
          <template #default="{ row }">
            {{ (row.config && row.config.table_list) || "-" }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="200" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link @click="toggle(row)">
              {{ row.status === "paused" ? "恢复" : "暂停" }}
            </el-button>
            <el-button link @click="refreshOne(row)">同步状态</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !filtered.length"
                description="还没有 CDC 源，先建一个" />
    </el-card>

    <el-dialog v-model="dialog" title="新建 CDC 源" width="560px">
      <el-form label-width="96px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="例如：订单库增量" />
        </el-form-item>
        <el-form-item label="主机" required>
          <el-input v-model="form.host" placeholder="cdc-postgres.stream.svc" />
        </el-form-item>
        <el-form-item label="端口">
          <el-input-number v-model="form.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="数据库" required>
          <el-input v-model="form.database" />
        </el-form-item>
        <el-form-item label="用户" required>
          <el-input v-model="form.user" />
        </el-form-item>
        <el-form-item label="密码" required>
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="Schema">
          <el-input v-model="form.schema_list" placeholder="public" />
        </el-form-item>
        <el-form-item label="表">
          <el-input v-model="form.table_list"
                    placeholder="public.events,public.orders" />
        </el-form-item>
        <el-form-item label="Topic 前缀">
          <el-input v-model="form.topic_prefix" placeholder="odf" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="create">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../api";

const rows = ref([]);
const loading = ref(false);
const saving = ref(false);
const dialog = ref(false);
const status = ref("");

const blank = () => ({
  name: "", host: "cdc-postgres.stream.svc", port: 5432,
  database: "cdc", user: "cdc", password: "",
  schema_list: "public", table_list: "", topic_prefix: "odf",
});
const form = reactive(blank());

const filtered = computed(() =>
  rows.value.filter((r) => !status.value || r.status === status.value));

function statusLabel(s) {
  return { running: "运行中", paused: "已暂停", failed: "失败",
           pending: "等待中", stopped: "已停止", unknown: "未知" }[s] || s;
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
    ElMessage.success("已创建");
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
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function refreshOne(row) {
  try {
    await api.post(`/cdc/sources/${row.id}/status`);
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`删除 CDC 源 ${row.name}？连接器会一并移除。`,
      "删除", { type: "warning" });
  } catch (e) {
    return;
  }
  try {
    await api.del(`/cdc/sources/${row.id}`);
    ElMessage.success("已删除");
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

onMounted(load);
</script>
