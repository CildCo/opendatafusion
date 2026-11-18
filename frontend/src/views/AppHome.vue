<template>
  <div class="page">
    <div class="toolbar">
      <el-input v-model="q" :placeholder="t('apps.search')" clearable
                style="width: 260px" />
      <div class="spacer" />
      <el-button @click="load" :loading="loading">{{ t("apps.refresh") }}</el-button>
      <el-button type="primary" @click="create">{{ t("apps.new") }}</el-button>
    </div>
    <el-card shadow="never">
      <el-table :data="filtered" size="small" v-loading="loading">
        <el-table-column prop="name" :label="t('apps.name')" min-width="180" />
        <el-table-column prop="key" :label="t('apps.key')" min-width="240">
          <template #default="{ row }">
            <span class="mono">{{ row.key }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('apps.status')" width="110">
          <template #default="{ row }">
            <el-tag :type="row.published ? 'success' : 'info'" size="small">
              {{ row.published ? t("apps.published") : t("apps.draft") }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('apps.actions')" width="230">
          <template #default="{ row }">
            <el-button link @click="$router.push(`/apps/${row.id}`)">
              {{ t("apps.edit") }}
            </el-button>
            <el-button link type="danger" @click="remove(row)">
              {{ t("apps.delete") }}
            </el-button>
            <el-button link :disabled="!row.published"
                       @click="$router.push(`/apps/${row.id}/run`)">
              {{ t("apps.run") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !filtered.length"
                :description="t('apps.empty')" />
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../api";
import { t } from "../i18n";

const router = useRouter();
const rows = ref([]);
const q = ref("");
const loading = ref(false);
const filtered = computed(() => rows.value.filter(
  (r) => !q.value || (r.name + r.key).toLowerCase()
    .includes(q.value.toLowerCase())));

async function remove(row) {
  try {
    await ElMessageBox.confirm(
      t("apps.deleteConfirm").replace("{name}", row.name),
      t("apps.deleteTitle"), { type: "warning" });
  } catch (e) {
    return;
  }
  try {
    await api.del(`/apps/${row.id}`);
    ElMessage.success(t("apps.deleted"));
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function load() {
  loading.value = true;
  try {
    rows.value = await api.get("/apps");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

async function create() {
  try {
    const { value } = await ElMessageBox.prompt(t("apps.namePrompt"), t("apps.new"), {
      inputPattern: /\S+/, inputErrorMessage: t("apps.nameRequired"),
    });
    const r = await api.post("/apps", { name: value });
    router.push(`/apps/${r.id}`);
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

onMounted(load);
</script>

<style scoped>
.toolbar { display: flex; gap: 10px; margin-bottom: 12px; align-items: center; }
.spacer { flex: 1; }
.mono { font-family: ui-monospace, monospace; font-size: 11px; }
</style>
