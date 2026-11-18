<template>
  <div class="page">
    <el-tabs v-model="tab" @tab-change="go">
      <el-tab-pane :label="t('model.datasets')" name="datasets" />
      <el-tab-pane :label="t('model.metrics')" name="metrics" />
    </el-tabs>
    <div class="toolbar">
      <el-input v-model="q" :placeholder="t('model.search')" clearable
                style="width: 260px" />
      <div class="spacer" />
      <el-button @click="load" :loading="loading">{{ t("model.refresh") }}</el-button>
      <el-button type="primary" @click="create">
        {{ t(tab === "datasets" ? "model.newDataset" : "model.newMetric") }}
      </el-button>
    </div>
    <el-card shadow="never">
      <el-table :data="filtered" size="small" v-loading="loading">
        <el-table-column prop="name" :label="t('model.name')" min-width="160" />
        <el-table-column prop="key" :label="t('model.key')" min-width="240">
          <template #default="{ row }">
            <span class="mono">{{ row.key }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('model.status')" width="110">
          <template #default="{ row }">
            <el-tag :type="row.published ? 'success' : 'info'" size="small">
              {{ row.published ? t("model.published") : t("model.draft") }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('model.actions')" width="170">
          <template #default="{ row }">
            <el-button link @click="$router.push(`/${tab}/${row.id}`)">
              {{ t("model.edit") }}
            </el-button>
            <el-button link type="danger" @click="remove(row)">
              {{ t("model.delete") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !filtered.length" :description="t('model.empty')" />
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../api";
import { t } from "../i18n";

const route = useRoute();
const router = useRouter();
const tab = ref(route.path.startsWith("/metrics") ? "metrics" : "datasets");
const rows = ref([]);
const q = ref("");
const loading = ref(false);
const filtered = computed(() => rows.value.filter(
  (r) => !q.value || (r.name + r.key).toLowerCase()
    .includes(q.value.toLowerCase())));

async function remove(row) {
  try {
    await ElMessageBox.confirm(
      t("model.deleteConfirm").replace("{name}", row.name),
      t("model.deleteTitle"), { type: "warning" });
  } catch (e) {
    return;
  }
  try {
    await api.del(`/${tab.value}/${row.id}`);
    ElMessage.success(t("model.deleted"));
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function load() {
  loading.value = true;
  try {
    rows.value = await api.get(`/${tab.value}`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

function go() {
  router.push(`/${tab.value}`);
}

async function create() {
  try {
    const { value } = await ElMessageBox.prompt(t("model.namePrompt"), t("model.createTitle"), {
      inputPattern: /\S+/, inputErrorMessage: t("model.nameRequired"),
    });
    const r = await api.post(`/${tab.value}`, { name: value });
    router.push(`/${tab.value}/${r.id}`);
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

watch(() => route.path, () => {
  tab.value = route.path.startsWith("/metrics") ? "metrics" : "datasets";
  load();
});
onMounted(load);
</script>

<style scoped>
.toolbar { display: flex; gap: 10px; margin: 12px 0; align-items: center; }
.spacer { flex: 1; }
.mono { font-family: ui-monospace, monospace; font-size: 11px; }
</style>
