<template>
  <div class="admin-page">
    <div class="toolbar">
      <div class="spacer" />
      <el-button @click="load" :loading="loading">{{ t("adm.refresh") }}</el-button>
      <el-button type="primary" @click="openCreate">{{ t("adm.newProject") }}</el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="projects" size="small" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column :label="t('adm.projectName')" min-width="180">
          <template #default="{ row }">
            <span class="entity-cell">
              <entity-icon type="workspace" :size="20" />
              <b>{{ row.name }}</b>
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="code" :label="t('adm.projectCode')"
                         width="150" />
        <el-table-column :label="t('adm.status')" width="110">
          <template #default="{ row }">
            <status-dot :status="row.status === 1"
                        :label="row.status === 1
                          ? t('adm.enabled') : t('adm.disabled')" />
          </template>
        </el-table-column>
        <el-table-column :label="t('adm.quota')" min-width="200">
          <template #default="{ row }">
            <span class="muted">{{ quotaText(row.quota) }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('adm.actions')" width="230" fixed="right">
          <template #default="{ row }">
            <el-button link @click="openMembers(row)">{{ t("adm.members") }}</el-button>
            <el-button link @click="openQuota(row)">{{ t("adm.quotaEdit") }}</el-button>
            <el-button link @click="openEdit(row)">{{ t("adm.edit") }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <empty-state v-if="!loading && !projects.length"
                   :title="t('adm.noProjects')"
                   :action-text="t('adm.newProject')" @action="openCreate" />
    </el-card>

    <el-dialog v-model="dialog" :title="t('adm.newProject')" width="480px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item :label="t('adm.projectCode')" prop="code">
          <el-input v-model="form.code" placeholder="sales" />
        </el-form-item>
        <el-form-item :label="t('adm.projectName')" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">{{ t("adm.cancel") }}</el-button>
        <el-button type="primary" :loading="saving" @click="create">
          {{ t("adm.save") }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editOpen" :title="t('adm.editProject')" width="480px">
      <el-form label-width="90px">
        <el-form-item :label="t('adm.projectName')">
          <el-input v-model="edit.name" />
        </el-form-item>
        <el-form-item :label="t('adm.status')">
          <el-switch v-model="edit.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editOpen = false">{{ t("adm.cancel") }}</el-button>
        <el-button type="primary" :loading="saving" @click="saveEdit">
          {{ t("adm.save") }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="quotaOpen" :title="t('adm.quotaEdit')" width="520px">
      <el-form label-width="110px">
        <el-form-item label="CPU">
          <el-input v-model="quota.cpu" placeholder="4" />
        </el-form-item>
        <el-form-item :label="t('adm.memory')">
          <el-input v-model="quota.memory" placeholder="8Gi" />
        </el-form-item>
        <el-form-item label="Pods">
          <el-input v-model="quota.pods" placeholder="20" />
        </el-form-item>
        <el-form-item :label="t('adm.storage')">
          <el-input v-model="quota.storage" placeholder="100Gi" />
        </el-form-item>
        <p class="hint">{{ t("adm.quotaHint") }}</p>
      </el-form>
      <template #footer>
        <el-button @click="quotaOpen = false">{{ t("adm.cancel") }}</el-button>
        <el-button type="primary" :loading="saving" @click="saveQuota">
          {{ t("adm.save") }}
        </el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="membersOpen" :title="t('adm.membersTitle')"
               size="600px">
      <div class="member-add">
        <el-select v-model="memberForm.user_id" filterable
                   :placeholder="t('adm.selectUser')" style="width: 200px">
          <el-option v-for="u in users" :key="u.id" :value="u.id"
                     :label="u.username" />
        </el-select>
        <el-select v-model="memberForm.role" style="width: 130px">
          <el-option value="viewer" label="viewer" />
          <el-option value="editor" label="editor" />
          <el-option value="approver" label="approver" />
          <el-option value="admin" label="admin" />
        </el-select>
        <el-button type="primary" @click="addMember">
          {{ t("adm.addMember") }}
        </el-button>
      </div>
      <el-table :data="members" size="small">
        <el-table-column :label="t('adm.user')" min-width="160">
          <template #default="{ row }">{{ userName(row.user_id) }}</template>
        </el-table-column>
        <el-table-column prop="role" :label="t('adm.projectRole')"
                         width="120" />
        <el-table-column :label="t('adm.actions')" width="90">
          <template #default="{ row }">
            <el-button link type="danger" @click="removeMember(row)">
              {{ t("adm.remove") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <empty-state v-if="!members.length" :title="t('adm.noMembers')" />
    </el-drawer>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../../api";
import { t } from "../../i18n";
import EmptyState from "../../components/EmptyState.vue";
import EntityIcon from "../../components/EntityIcon.vue";
import StatusDot from "../../components/StatusDot.vue";

const projects = ref([]);
const users = ref([]);
const members = ref([]);
const loading = ref(false);
const saving = ref(false);
const dialog = ref(false);
const editOpen = ref(false);
const quotaOpen = ref(false);
const membersOpen = ref(false);
const current = ref(null);
const formRef = ref(null);
const form = reactive({ code: "", name: "" });
const edit = reactive({ name: "", enabled: true });
const quota = reactive({ cpu: "", memory: "", pods: "", storage: "" });
const memberForm = reactive({ user_id: null, role: "viewer" });

const rules = {
  code: [{ required: true, message: t("adm.codeRequired"), trigger: "blur" }],
  name: [{ required: true, message: t("adm.nameRequired"), trigger: "blur" }],
};

async function load() {
  loading.value = true;
  try {
    projects.value = await api.get("/projects");
    users.value = await api.get("/users");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

function userName(id) {
  return users.value.find((u) => u.id === id)?.username || `#${id}`;
}

function quotaText(q) {
  if (!q || !Object.keys(q).length) return "—";
  return ["cpu", "memory", "pods", "storage"]
    .filter((key) => q[key]).map((key) => `${key} ${q[key]}`).join(" · ");
}

function openCreate() {
  form.code = "";
  form.name = "";
  dialog.value = true;
}

async function create() {
  try {
    await formRef.value.validate();
  } catch {
    return;
  }
  saving.value = true;
  try {
    await api.post("/projects", { code: form.code.trim(),
                                  name: form.name.trim() });
    dialog.value = false;
    await load();
    ElMessage.success(t("adm.created"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

function openEdit(row) {
  current.value = row;
  edit.name = row.name;
  edit.enabled = row.status === 1;
  editOpen.value = true;
}

async function saveEdit() {
  saving.value = true;
  try {
    await api.put(`/projects/${current.value.id}`, {
      name: edit.name, status: edit.enabled ? 1 : 0,
    });
    editOpen.value = false;
    await load();
    ElMessage.success(t("adm.saved"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

function openQuota(row) {
  current.value = row;
  Object.assign(quota, { cpu: "", memory: "", pods: "", storage: "" },
                row.quota || {});
  quotaOpen.value = true;
}

async function saveQuota() {
  const payload = Object.fromEntries(
    Object.entries(quota).filter(([, value]) => String(value ?? "").trim()));
  saving.value = true;
  try {
    await api.put(`/projects/${current.value.id}`, { quota: payload });
    quotaOpen.value = false;
    await load();
    ElMessage.success(t("adm.saved"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

async function openMembers(row) {
  current.value = row;
  membersOpen.value = true;
  memberForm.user_id = null;
  memberForm.role = "viewer";
  await loadMembers();
}

async function loadMembers() {
  try {
    members.value = await api.get(`/projects/${current.value.id}/members`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function addMember() {
  if (!memberForm.user_id) return;
  try {
    await api.post(`/projects/${current.value.id}/members`, {
      user_id: memberForm.user_id, role: memberForm.role,
    });
    await loadMembers();
    ElMessage.success(t("adm.memberAdded"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function removeMember(row) {
  try {
    await ElMessageBox.confirm(t("adm.removeMemberConfirm"),
                               t("adm.removeMember"), { type: "warning" });
  } catch {
    return;
  }
  try {
    await api.del(`/projects/${current.value.id}/members/${row.user_id}`);
    await loadMembers();
    ElMessage.success(t("adm.memberRemoved"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

onMounted(load);
</script>

<style scoped>
.toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
.spacer { flex: 1; }
.entity-cell { display: inline-flex; align-items: center; gap: 8px; }
.muted { color: #64748b; font-size: 12px; }
.hint { color: #94a3b8; font-size: 12px; margin: 0 0 0 110px; }
.member-add { display: flex; gap: 8px; margin-bottom: 12px; }
</style>
