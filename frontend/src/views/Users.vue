<template>
  <div class="page">
    <div class="toolbar">
      <el-input v-model="q" placeholder="搜索用户名" clearable style="width: 220px"
                :prefix-icon="Search" />
      <div class="spacer" />
      <el-button @click="load" :loading="loading">刷新</el-button>
      <el-button @click="openMembers">项目成员</el-button>
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

    <el-drawer v-model="membersOpen" title="项目成员" size="560px"
               @open="loadProjects">
      <el-select v-model="memberProject" style="width: 100%"
                 placeholder="选择项目" @change="loadMembers">
        <el-option v-for="p in projects" :key="p.id" :value="p.id"
                   :label="`${p.name} (${p.code})`" />
      </el-select>
      <div class="member-add">
        <el-select v-model="memberForm.user_id" filterable
                   placeholder="选择用户" style="width: 200px">
          <el-option v-for="u in rows" :key="u.id" :value="u.id"
                     :label="u.username" />
        </el-select>
        <el-select v-model="memberForm.role" style="width: 120px">
          <el-option value="viewer" label="viewer" />
          <el-option value="editor" label="editor" />
          <el-option value="approver" label="approver" />
          <el-option value="admin" label="admin" />
        </el-select>
        <el-button type="primary" :disabled="!memberProject"
                   @click="addMember">添加</el-button>
      </div>
      <el-table :data="members" size="small">
        <el-table-column label="用户" min-width="150">
          <template #default="{ row }">{{ userName(row.user_id) }}</template>
        </el-table-column>
        <el-table-column prop="role" label="项目角色" width="120" />
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button link type="danger" @click="removeMember(row)">
              移除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!members.length" description="还没有成员" :image-size="60" />
    </el-drawer>
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
const membersOpen = ref(false);
const projects = ref([]);
const members = ref([]);
const memberProject = ref(null);
const memberForm = reactive({ user_id: null, role: "viewer" });

function userName(id) {
  const u = rows.value.find((x) => x.id === id);
  return u ? u.username : `用户 ${id}`;
}

function openMembers() {
  membersOpen.value = true;
}

async function loadProjects() {
  try {
    projects.value = await api.get("/projects");
    if (!memberProject.value && projects.value.length) {
      memberProject.value = projects.value[0].id;
      await loadMembers();
    }
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function loadMembers() {
  if (!memberProject.value) return;
  try {
    members.value = await api.get(`/projects/${memberProject.value}/members`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function addMember() {
  if (!memberProject.value || !memberForm.user_id) {
    ElMessage.warning("请选择项目和用户");
    return;
  }
  try {
    await api.post(`/projects/${memberProject.value}/members`,
                   { user_id: memberForm.user_id, role: memberForm.role });
    memberForm.user_id = null;
    await loadMembers();
    ElMessage.success("已添加");
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function removeMember(row) {
  try {
    await ElMessageBox.confirm(
      `将 ${userName(row.user_id)} 移出该项目？`, "移除成员",
      { type: "warning" });
  } catch (e) {
    return;
  }
  try {
    await api.del(`/projects/${memberProject.value}/members/${row.user_id}`);
    await loadMembers();
    ElMessage.success("已移除");
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

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
.member-add {
  display: flex;
  gap: 8px;
  align-items: center;
  margin: 14px 0;
}
</style>
