<template>
  <div class="page">
    <div class="toolbar">
      <el-input v-model="q" placeholder="搜索用户名" clearable style="width: 220px"
                :prefix-icon="Search" />
      <div class="spacer" />
      <el-button @click="load" :loading="loading">刷新</el-button>
      <el-button type="primary" @click="dialog = true">新建用户</el-button>
    </div>

    <el-card class="card" shadow="never">
      <el-table :data="filtered" size="small" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="username" label="用户名" min-width="150" />
        <el-table-column label="角色" width="180">
          <template #default="{ row }">
            <el-select :model-value="row.role" size="small" style="width: 140px"
                       @change="(v) => changeRole(row, v)">
              <el-option value="viewer" label="viewer" />
              <el-option value="editor" label="editor" />
              <el-option value="approver" label="approver" />
              <el-option value="admin" label="admin" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="100">
          <template #default="{ row }">
            <el-switch :model-value="row.active"
                       @change="(v) => changeActive(row, v)" />
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !filtered.length" description="没有用户" />
    </el-card>

    <el-dialog v-model="dialog" title="新建用户" width="480px">
      <el-form label-width="80px">
        <el-form-item label="用户名" required>
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item label="密码" required>
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role" style="width: 100%">
            <el-option value="viewer" label="viewer" />
            <el-option value="editor" label="editor" />
            <el-option value="approver" label="approver" />
            <el-option value="admin" label="admin" />
          </el-select>
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
import { Search } from "@element-plus/icons-vue";
import { api, errMsg } from "../api";

const rows = ref([]);
const loading = ref(false);
const saving = ref(false);
const dialog = ref(false);
const q = ref("");
const form = reactive({ username: "", password: "", role: "viewer" });

const filtered = computed(() =>
  rows.value.filter((u) => !q.value || u.username.toLowerCase().includes(q.value.toLowerCase()))
);

async function load() {
  loading.value = true;
  try {
    rows.value = await api.get("/users");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

async function create() {
  if (!form.username || !form.password) {
    ElMessage.warning("用户名和密码必填");
    return;
  }
  saving.value = true;
  try {
    await api.post("/users", form);
    dialog.value = false;
    form.username = "";
    form.password = "";
    form.role = "viewer";
    await load();
    ElMessage.success("已创建");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

async function changeRole(row, role) {
  try {
    await ElMessageBox.confirm(
      `将 ${row.username} 的角色改为 ${role}？`, "角色变更", { type: "warning" });
    await api.put(`/users/${row.id}/role?role=${encodeURIComponent(role)}`);
    await load();
    ElMessage.success("已更新");
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

async function changeActive(row, active) {
  try {
    await api.put(`/users/${row.id}/active?active=${active ? "true" : "false"}`);
    await load();
    ElMessage.success(active ? "已启用" : "已停用");
  } catch (e) {
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
</style>
