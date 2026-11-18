<template>
  <div class="page">
    <div class="toolbar">
      <el-select v-model="status" clearable :placeholder="t('cdc.allStatus')" style="width: 140px">
        <el-option value="running" :label="t('cdc.running')" />
        <el-option value="paused" :label="t('cdc.paused')" />
        <el-option value="failed" :label="t('cdc.failed')" />
      </el-select>
      <div class="spacer" />
      <el-button type="primary" @click="openCreate">{{ t("cdc.newSource") }}</el-button>
      <el-button :loading="loading" @click="load">{{ t("cdc.refresh") }}</el-button>
    </div>

    <el-card class="card" shadow="never">
      <el-table :data="filtered" size="small" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" :label="t('cdc.name')" min-width="160" />
        <el-table-column prop="connector_name" :label="t('cdc.connector')" min-width="200" />
        <el-table-column :label="t('cdc.subscribedTables')" min-width="200">
          <template #default="{ row }">
            {{ (row.config && row.config.table_list) || "-" }}
          </template>
        </el-table-column>
        <el-table-column prop="status" :label="t('cdc.status')" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" :label="t('cdc.createdAt')" width="200" />
        <el-table-column :label="t('cdc.actions')" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link @click="toggle(row)">
              {{ row.status === "paused" ? t("cdc.resume") : t("cdc.pause") }}
            </el-button>
            <el-button link @click="refreshOne(row)">{{ t("cdc.refreshStatus") }}</el-button>
            <el-button link type="danger" @click="remove(row)">{{ t("cdc.delete") }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !filtered.length"
                :description="t('cdc.empty')" />
    </el-card>

    <el-dialog v-model="dialog" :title="t('cdc.newSource')" width="560px">
      <el-form label-width="96px">
        <el-form-item :label="t('cdc.name')" required>
          <el-input v-model="form.name" :placeholder="t('cdc.namePlaceholder')" />
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
          <el-input v-model="form.schema_list" placeholder="public" />
        </el-form-item>
        <el-form-item :label="t('cdc.table')">
          <el-input v-model="form.table_list"
                    placeholder="public.events,public.orders" />
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
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../api";
import { t } from "../i18n";

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
