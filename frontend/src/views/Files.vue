<template>
  <div class="page">
    <div class="toolbar">
      <el-tag size="small" type="info">内容寻址存储</el-tag>
      <div class="spacer" />
      <el-button size="small" @click="load" :loading="loading">刷新</el-button>
      <el-upload :show-file-list="false" :http-request="upload">
        <el-button type="primary" size="small" :loading="uploading">
          上传文件
        </el-button>
      </el-upload>
    </div>

    <el-card shadow="never">
      <el-table :data="rows" size="small" empty-text="还没有文件">
        <el-table-column prop="name" label="名称" min-width="200" />
        <el-table-column prop="content_type" label="类型" width="150" />
        <el-table-column label="大小" width="110">
          <template #default="{ row }">{{ sizeText(row.size) }}</template>
        </el-table-column>
        <el-table-column prop="created_by" label="上传人" width="110" />
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ fmt(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="130">
          <template #default="{ row }">
            <el-button link @click="download(row)">下载</el-button>
            <el-button v-if="canEdit" link type="danger"
                       @click="remove(row)">删除</el-button>
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

const canEdit = ["editor", "approver", "admin"].includes(getRole());
const rows = ref([]);
const loading = ref(false);
const uploading = ref(false);

function fmt(v) {
  if (!v) return "-";
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? v : d.toLocaleString("zh-CN");
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
    ElMessage.success("已上传");
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
    await ElMessageBox.confirm(`删除文件「${row.name}」？`, "删除确认");
    await api.del(`/files/${row.id}`);
    ElMessage.success("已删除");
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
