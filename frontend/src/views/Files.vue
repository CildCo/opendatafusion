<template>
  <div class="page">
    <div class="toolbar">
      <el-tag size="small" type="info">{{ t("files.storage") }}</el-tag>
      <div class="spacer" />
      <el-button size="small" @click="load" :loading="loading">{{ t("files.refresh") }}</el-button>
      <el-upload :show-file-list="false" :http-request="upload">
        <el-button type="primary" size="small" :loading="uploading">
          {{ t("files.upload") }}
        </el-button>
      </el-upload>
    </div>

    <el-card shadow="never">
      <el-table :data="rows" size="small" :empty-text="t('files.empty')">
        <el-table-column prop="name" :label="t('files.name')" min-width="200" />
        <el-table-column prop="content_type" :label="t('files.type')" width="150" />
        <el-table-column :label="t('files.size')" width="110">
          <template #default="{ row }">{{ sizeText(row.size) }}</template>
        </el-table-column>
        <el-table-column prop="created_by" :label="t('files.uploader')" width="110" />
        <el-table-column :label="t('files.time')" width="170">
          <template #default="{ row }">{{ fmt(row.created_at) }}</template>
        </el-table-column>
        <el-table-column :label="t('files.actions')" width="130">
          <template #default="{ row }">
            <el-button link @click="download(row)">{{ t("files.download") }}</el-button>
            <el-button v-if="canEdit" link type="danger"
                       @click="remove(row)">{{ t("files.delete") }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg, getRole, getToken } from "../api";
import { locale, t } from "../i18n";

const canEdit = ["editor", "approver", "admin"].includes(getRole());
const rows = ref([]);
const loading = ref(false);
const uploading = ref(false);

function fmt(v) {
  if (!v) return "-";
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? v : d.toLocaleString(locale.value === "en" ? "en-US" : "zh-CN");
}
function sizeText(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

async function load() {
  loading.value = true;
  try {
    rows.value = await api.get("/files");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

async function upload({ file }) {
  uploading.value = true;
  try {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch("/api/v1/files", {
      method: "POST",
      headers: { Authorization: "Bearer " + getToken() },
      body: fd,
    });
    if (!r.ok) {
      let msg = `HTTP ${r.status}`;
      try {
        const b = await r.json();
        msg = typeof b.detail === "string" ? b.detail : msg;
      } catch (e) {
        /* ignore */
      }
      throw new Error(msg);
    }
    ElMessage.success(t("files.uploaded"));
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    uploading.value = false;
  }
}

async function download(row) {
  try {
    const r = await fetch(`/api/v1/files/${row.id}/download`, {
      headers: { Authorization: "Bearer " + getToken() },
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const blob = await r.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = row.name;
    a.click();
    URL.revokeObjectURL(a.href);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(
      `${t("files.deleteConfirmPrefix")}${row.name}${t("files.deleteConfirmSuffix")}`,
      t("files.deleteTitle"));
    await api.del(`/files/${row.id}`);
    ElMessage.success(t("files.deleted"));
    await load();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

onMounted(load);
</script>

<style scoped>
.toolbar { display: flex; gap: 10px; align-items: center;
           margin-bottom: 12px; }
.title { font-size: 16px; font-weight: 700; color: #0f172a; }
.spacer { flex: 1; }
</style>
