<template>
  <div class="page">
    <div class="toolbar">
      <el-input v-model="q" :placeholder="t('apps.search')" clearable
                style="width: 260px" @keyup.enter="search"
                @clear="search" />
      <div class="spacer" />
      <el-button @click="load" :loading="loading">{{ t("apps.refresh") }}</el-button>
      <el-button v-if="canEdit" type="primary" @click="create">{{ t("apps.new") }}</el-button>
    </div>
    <el-card shadow="never">
      <el-table :data="rows" size="small" v-loading="loading">
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
            <el-button v-if="canEdit" link type="danger" @click="remove(row)">
              {{ t("apps.delete") }}
            </el-button>
            <el-button link :disabled="!row.published"
                       @click="$router.push(`/apps/${row.id}/run`)">
              {{ t("apps.run") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-if="total > pageSize" class="pager"
                     layout="total, prev, pager, next"
                     :total="total" :page-size="pageSize"
                     :current-page="page" @current-change="changePage" />
      <el-empty v-if="!loading && !rows.length"
                :description="t('apps.empty')" />
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, canWrite, errMsg } from "../api";
import { t } from "../i18n";

const router = useRouter();
const route = useRoute();
const rows = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(50);
const canEdit = canWrite();
const q = ref("");
const loading = ref(false);

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
    const params = new URLSearchParams({
      page: String(page.value), page_size: String(pageSize.value),
    });
    if (q.value.trim()) params.set("q", q.value.trim());
    const result = await api.get(`/apps?${params.toString()}`);
    rows.value = result.items || [];
    total.value = result.total || 0;
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

function search() {
  page.value = 1;
  load();
}

function changePage(next) {
  page.value = next;
  load();
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
onMounted(() => { if (route.query.new && canEdit) create(); });
</script>

<style scoped>
.toolbar { display: flex; gap: 10px; margin-bottom: 12px; align-items: center; }
.spacer { flex: 1; }
.mono { font-family: ui-monospace, monospace; font-size: 11px; }
.pager { margin-top: 12px; justify-content: flex-end; }
</style>
