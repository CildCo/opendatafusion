<template>
  <div class="page">
    <page-header icon="api" :title="t('menu.apis')" :intro="t('api.intro')" />
    <div class="toolbar">
      <el-input v-model="q" :placeholder="t('api.search')" clearable
                style="width: 260px" />
      <div class="spacer" />
      <el-button @click="load" :loading="loading">{{ t("api.refresh") }}</el-button>
      <el-button type="primary" @click="create">{{ t("api.new") }}</el-button>
    </div>
    <el-card shadow="never">
      <el-table :data="filtered" size="small" v-loading="loading">
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
            <el-button link type="danger" @click="remove(row)">
              {{ t("api.delete") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <empty-state v-if="!loading && !filtered.length"
                   :title="t('api.empty')" :description="t('api.intro')"
                   :action-text="t('api.new')" @action="create" />
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../api";
import { t } from "../i18n";
import EmptyState from "../components/EmptyState.vue";
import EntityIcon from "../components/EntityIcon.vue";
import PageHeader from "../components/PageHeader.vue";
import StatusDot from "../components/StatusDot.vue";

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
    rows.value = await api.get("/apis");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
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
</style>
