<template>
  <div class="page">
    <page-header icon="user" :title="t('members.title')"
                 :intro="t('members.intro')" />
    <el-card class="card" shadow="never">
      <div class="bar">
        <el-select v-model="projectId" style="width: 260px"
                   @change="load">
          <el-option v-for="p in projects" :key="p.id" :value="p.id"
                     :label="p.name" />
        </el-select>
        <el-button @click="load" :loading="loading">
          {{ t("users.refresh") }}
        </el-button>
      </div>
      <el-table :data="members" size="small" v-loading="loading">
        <el-table-column :label="t('users.user')" min-width="220">
          <template #default="{ row }">
            <span class="entity-cell">
              <entity-icon type="user" :size="20" />
              <b>{{ row.username || row.user_id }}</b>
              <el-tag v-if="row.user_id === meId" size="small" type="info">
                {{ t("members.you") }}
              </el-tag>
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="role" :label="t('users.projectRole')"
                         width="140" />
        <el-table-column :label="t('users.actions')" width="110">
          <template #default="{ row }">
            <el-button link type="danger"
                       :disabled="row.user_id === meId"
                       :title="row.user_id === meId ? t('members.selfHint') : ''"
                       @click="remove(row)">
              {{ t("users.remove") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <empty-state v-if="!loading && !members.length"
                   :title="t('users.emptyMembers')" :image-size="60" />
    </el-card>

    <el-card class="card add-card" shadow="never">
      <h4>{{ t("members.addTitle") }}</h4>
      <div class="add-row">
        <el-input v-model="username" style="width: 220px"
                  :placeholder="t('members.usernamePlaceholder')"
                  @keyup.enter="lookup" />
        <el-button @click="lookup" :loading="looking">
          {{ t("members.lookup") }}
        </el-button>
        <el-tag v-if="found" :type="found.member ? 'info' : 'success'">
          {{ found.member ? t("members.already")
             : (found.active ? t("members.found") : t("members.inactive")) }}
        </el-tag>
        <el-select v-model="role" style="width: 140px">
          <el-option value="viewer" label="viewer" />
          <el-option value="editor" label="editor" />
          <el-option value="approver" label="approver" />
          <el-option value="admin" label="admin" />
        </el-select>
        <el-button type="primary" :disabled="!found || found.member"
                   :loading="adding" @click="add">
          {{ t("users.add") }}
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg, getProject } from "../api";
import { t } from "../i18n";
import EmptyState from "../components/EmptyState.vue";
import EntityIcon from "../components/EntityIcon.vue";
import PageHeader from "../components/PageHeader.vue";

const projects = ref([]);
const projectId = ref(getProject());
const members = ref([]);
const loading = ref(false);
const username = ref("");
const found = ref(null);
const role = ref("viewer");
const looking = ref(false);
const adding = ref(false);
const meId = ref(null);

watch(username, () => { found.value = null; });

async function loadProjects() {
  projects.value = await api.get("/projects/mine");
  if (!projects.value.some((p) => p.id === projectId.value)) {
    projectId.value = projects.value.length ? projects.value[0].id : null;
  }
}

async function load() {
  if (!projectId.value) return;
  loading.value = true;
  try {
    members.value = await api.get(`/projects/${projectId.value}/members`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

async function lookup() {
  const name = username.value.trim();
  if (!name || !projectId.value) return;
  looking.value = true;
  try {
    found.value = await api.get(
      `/projects/${projectId.value}/users/lookup?username=${encodeURIComponent(name)}`);
  } catch (e) {
    found.value = null;
    ElMessage.error(errMsg(e));
  } finally {
    looking.value = false;
  }
}

async function add() {
  if (!found.value || !projectId.value) return;
  adding.value = true;
  try {
    await api.post(`/projects/${projectId.value}/members`, {
      user_id: found.value.id, role: role.value,
    });
    ElMessage.success(t("users.added"));
    username.value = "";
    found.value = null;
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    adding.value = false;
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(
      t("users.removeConfirm").replace("{name}", row.username || row.user_id),
      t("users.removeTitle"), { type: "warning" });
  } catch (e) {
    return;
  }
  try {
    await api.del(`/projects/${projectId.value}/members/${row.user_id}`);
    ElMessage.success(t("users.removed"));
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

onMounted(async () => {
  try {
    const me = await api.get("/auth/me");
    meId.value = me.id;
  } catch (e) {
    meId.value = null;
  }
  try {
    await loadProjects();
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
});
</script>

<style scoped>
.bar {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
}
.add-card { margin-top: 16px; }
.add-card h4 { margin: 0 0 12px; font-size: 14px; }
.add-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.entity-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.card { border-radius: 12px; border: 1px solid #e5e7eb; }
</style>
