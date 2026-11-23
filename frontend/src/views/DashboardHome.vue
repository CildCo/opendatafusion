<template>
  <div class="page">
    <div class="toolbar">
      <el-input v-model="q" :placeholder="t('dash.search')" clearable
                style="width: 260px" />
      <div class="spacer" />
      <el-button @click="load" :loading="loading">{{ t("dash.refresh") }}</el-button>
      <el-button v-if="canEdit" type="primary" @click="create">{{ t("dash.new") }}</el-button>
    </div>
    <el-card shadow="never">
      <el-table :data="filtered" size="small" v-loading="loading">
        <el-table-column prop="name" :label="t('dash.name')" min-width="180" />
        <el-table-column prop="key" :label="t('dash.key')" min-width="240">
          <template #default="{ row }">
            <span class="mono">{{ row.key }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('dash.status')" width="110">
          <template #default="{ row }">
            <el-tag :type="row.published ? 'success' : 'info'" size="small">
              {{ row.published ? t("dash.published") : t("dash.draft") }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('dash.actions')" width="230">
          <template #default="{ row }">
            <el-button link @click="$router.push(`/dashboards/${row.id}`)">
              {{ t("dash.edit") }}
            </el-button>
            <el-button v-if="canEdit" link type="danger" @click="remove(row)">
              {{ t("dash.delete") }}
            </el-button>
            <el-button link :disabled="!row.published"
                       @click="$router.push(`/dashboards/${row.id}/run`)">
              {{ t("dash.run") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !filtered.length" :description="t('dash.empty')" />
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, canWrite, errMsg } from "../api";
import { t } from "../i18n";

const router = useRouter();
const route = useRoute();
const rows = ref([]);
const canEdit = canWrite();
const q = ref("");
const loading = ref(false);
const filtered = computed(() => rows.value.filter(
  (r) => !q.value || (r.name + r.key).toLowerCase()
    .includes(q.value.toLowerCase())));

async function remove(row) {
  try {
    await ElMessageBox.confirm(
      t("dash.deleteConfirm").replace("{name}", row.name),
      t("dash.deleteTitle"), { type: "warning" });
  } catch (e) {
    return;
  }
  try {
    await api.del(`/dashboards/${row.id}`);
    ElMessage.success(t("dash.deleted"));
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function load() {
  loading.value = true;
  try {
    rows.value = await api.get("/dashboards");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

async function create() {
  try {
    const { value } = await ElMessageBox.prompt(t("dash.namePrompt"), t("dash.new"), {
      inputPattern: /\S+/, inputErrorMessage: t("dash.nameRequired"),
    });
    const r = await api.post("/dashboards", { name: value });
    router.push(`/dashboards/${r.id}`);
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

onMounted(load);
onMounted(() => { if (route.query.new && canEdit) create(); });
</script>

<style scoped>
.toolbar { display: flex; gap: 10px; margin-bottom: 12px; align-items: center; }
.spacer { flex: 1; }
.mono { font-family: ui-monospace, monospace; font-size: 11px; }
</style>
