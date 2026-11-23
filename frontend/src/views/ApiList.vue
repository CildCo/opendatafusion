<template>
  <div class="page">
    <page-header icon="api" :title="t('menu.apis')" :intro="t('api.intro')" />
    <div class="toolbar">
      <el-input v-model="q" :placeholder="t('api.search')" clearable
                style="width: 260px" @keyup.enter="search"
                @clear="search" />
      <div class="spacer" />
      <el-button @click="load" :loading="loading">{{ t("api.refresh") }}</el-button>
      <el-button v-if="canEdit" type="primary" @click="create">{{ t("api.new") }}</el-button>
    </div>
    <el-card shadow="never">
      <el-table :data="rows" size="small" v-loading="loading">
        <el-table-column :label="t('api.name')" min-width="210">
          <template #default="{ row }">
            <span class="entity-cell">
              <entity-icon type="api" :size="20" />
              <b>{{ row.name }}</b>
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="key" :label="t('api.key')" min-width="240">
          <template #default="{ row }">
            <span class="mono">{{ row.key }}</span>
            <el-button link @click="copy(row.key)">{{ t("api.copy") }}</el-button>
          </template>
        </el-table-column>
        <el-table-column :label="t('api.status')" width="120">
          <template #default="{ row }">
            <status-dot :status="row.enabled"
                        :label="row.enabled
                          ? t('api.published') : t('api.draft')" />
          </template>
        </el-table-column>
        <el-table-column :label="t('api.actions')" width="180">
          <template #default="{ row }">
            <el-button link @click="$router.push(`/apis/${row.id}`)">
              {{ t("api.edit") }}
            </el-button>
            <el-button v-if="canEdit" link type="danger" @click="remove(row)">
              {{ t("api.delete") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-if="total > pageSize" class="pager"
                     layout="total, prev, pager, next"
                     :total="total" :page-size="pageSize"
                     :current-page="page" @current-change="changePage" />
      <empty-state v-if="!loading && !rows.length"
                   :title="t('api.empty')" :description="t('api.intro')"
                   :action-text="canEdit ? t('api.new') : ''" @action="create" />
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, canWrite, errMsg } from "../api";
import { t } from "../i18n";
import EmptyState from "../components/EmptyState.vue";
import EntityIcon from "../components/EntityIcon.vue";
import PageHeader from "../components/PageHeader.vue";
import StatusDot from "../components/StatusDot.vue";

const router = useRouter();
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
      t("api.deleteConfirm").replace("{name}", row.name),
      t("api.deleteTitle"), { type: "warning" });
  } catch (e) {
    return;
  }
  try {
    await api.del(`/apis/${row.id}`);
    ElMessage.success(t("api.deleted"));
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
    const result = await api.get(`/apis?${params.toString()}`);
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
    const { value } = await ElMessageBox.prompt(t("api.namePrompt"), t("api.new"), {
      inputPattern: /\S+/, inputErrorMessage: t("api.nameRequired"),
    });
    const r = await api.post("/apis", { name: value });
    router.push(`/apis/${r.id}`);
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success(t("api.copied"));
  } catch (e) {
    ElMessage.error(t("api.copyFailed"));
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
.toolbar { display: flex; gap: 10px; margin-bottom: 12px; align-items: center; }
.spacer { flex: 1; }
.mono { font-family: ui-monospace, monospace; font-size: 12px; }
.pager { margin-top: 12px; justify-content: flex-end; }
</style>
