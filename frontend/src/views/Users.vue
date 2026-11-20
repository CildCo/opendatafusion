<template>
  <div class="page">
    <page-header icon="user" :title="t('menu.users')"
                 :intro="t('users.intro')" />
    <div class="toolbar">
      <el-input v-model="q" :placeholder="t('users.searchPlaceholder')" clearable
                style="width: 220px" :prefix-icon="Search" />
      <div class="spacer" />
      <el-button @click="load" :loading="loading">{{ t("users.refresh") }}</el-button>
      <el-button @click="openMembers">{{ t("users.members") }}</el-button>
      <el-button type="primary" @click="dialog = true">{{ t("users.create") }}</el-button>
    </div>

    <el-card class="card" shadow="never">
      <el-table :data="filtered" size="small" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column :label="t('users.username')" min-width="190">
          <template #default="{ row }">
            <span class="entity-cell">
              <entity-icon type="user" :size="20" />
              <b>{{ row.username }}</b>
            </span>
          </template>
        </el-table-column>
        <el-table-column :label="t('users.role')" width="180">
          <template #default="{ row }">
            <el-select :model-value="row.role" size="small" style="width: 140px"
                       :disabled="locked(row)" :title="lockReason(row)"
                       @change="(v) => changeRole(row, v)">
              <el-option value="viewer" label="viewer" />
              <el-option value="editor" label="editor" />
              <el-option value="approver" label="approver" />
              <el-option value="admin" label="admin" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column :label="t('users.active')" width="100">
          <template #default="{ row }">
            <el-switch :model-value="row.active" :disabled="locked(row)"
                       :title="lockReason(row)"
                       @change="(v) => changeActive(row, v)" />
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !filtered.length"
                :description="t('users.empty')" />
    </el-card>

    <el-dialog v-model="dialog" :title="t('users.create')" width="480px">
      <el-form label-width="80px">
        <el-form-item :label="t('users.username')" required>
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item :label="t('users.password')" required>
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-form-item :label="t('users.role')">
          <el-select v-model="form.role" style="width: 100%">
            <el-option value="viewer" label="viewer" />
            <el-option value="editor" label="editor" />
            <el-option value="approver" label="approver" />
            <el-option value="admin" label="admin" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">{{ t("users.cancel") }}</el-button>
        <el-button type="primary" :loading="saving" @click="create">{{ t("users.save") }}</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="membersOpen" :title="t('users.members')" size="560px"
               @open="loadProjects">
      <el-select v-model="memberProject" style="width: 100%"
                 :placeholder="t('users.selectProject')" @change="loadMembers">
        <el-option v-for="p in projects" :key="p.id" :value="p.id"
                   :label="`${p.name} (${p.code})`" />
      </el-select>
      <div class="member-add">
        <el-select v-model="memberForm.user_id" filterable
                   :placeholder="t('users.selectUser')" style="width: 200px">
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
                   @click="addMember">{{ t("users.add") }}</el-button>
      </div>
      <el-table :data="members" size="small">
        <el-table-column :label="t('users.user')" min-width="150">
          <template #default="{ row }">{{ userName(row.user_id) }}</template>
        </el-table-column>
        <el-table-column prop="role" :label="t('users.projectRole')" width="120" />
        <el-table-column :label="t('users.actions')" width="90">
          <template #default="{ row }">
            <el-button link type="danger" @click="removeMember(row)">
              {{ t("users.remove") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!members.length" :description="t('users.emptyMembers')"
                :image-size="60" />
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Search } from "@element-plus/icons-vue";
import { api, errMsg } from "../api";
import { t } from "../i18n";
import PageHeader from "../components/PageHeader.vue";
import EntityIcon from "../components/EntityIcon.vue";

const rows = ref([]);
const loading = ref(false);
const saving = ref(false);
const dialog = ref(false);
const q = ref("");
const me = ref("");
const activeAdmins = computed(() =>
  rows.value.filter((u) => u.role === "admin" && u.active));

function locked(row) {
  if (row.username === me.value) return true;
  return row.role === "admin" && row.active && activeAdmins.value.length === 1;
}

function lockReason(row) {
  if (row.username === me.value) return t("users.selfLockHint");
  if (row.role === "admin" && row.active && activeAdmins.value.length === 1) {
    return t("users.lastAdminHint");
  }
  return "";
}
const form = reactive({ username: "", password: "", role: "viewer" });
const membersOpen = ref(false);
const projects = ref([]);
const members = ref([]);
const memberProject = ref(null);
const memberForm = reactive({ user_id: null, role: "viewer" });

function userName(id) {
  const u = rows.value.find((x) => x.id === id);
  return u ? u.username : `${t("users.user")} ${id}`;
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
    ElMessage.warning(t("users.selectProjectUser"));
    return;
  }
  try {
    await api.post(`/projects/${memberProject.value}/members`,
                   { user_id: memberForm.user_id, role: memberForm.role });
    memberForm.user_id = null;
    await loadMembers();
    ElMessage.success(t("users.added"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function removeMember(row) {
  try {
    await ElMessageBox.confirm(
      t("users.removeConfirm").replace("{name}", userName(row.user_id)),
      t("users.removeTitle"),
      { type: "warning" });
  } catch (e) {
    return;
  }
  try {
    await api.del(`/projects/${memberProject.value}/members/${row.user_id}`);
    await loadMembers();
    ElMessage.success(t("users.removed"));
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
    me.value = (await api.get("/auth/me")).username || "";
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

async function create() {
  if (!form.username || !form.password) {
    ElMessage.warning(t("users.requiredUserPass"));
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
    ElMessage.success(t("users.created"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

async function changeRole(row, role) {
  try {
    await ElMessageBox.confirm(
      t("users.changeRoleConfirm")
        .replace("{name}", row.username).replace("{role}", role),
      t("users.changeRoleTitle"), { type: "warning" });
    await api.put(`/users/${row.id}/role?role=${encodeURIComponent(role)}`);
    await load();
    ElMessage.success(t("users.updated"));
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

async function changeActive(row, active) {
  try {
    await api.put(`/users/${row.id}/active?active=${active ? "true" : "false"}`);
    await load();
    ElMessage.success(t(active ? "users.enabled" : "users.disabled"));
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
