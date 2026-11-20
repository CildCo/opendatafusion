<template>
  <div class="page">
    <page-header icon="pipeline" :title="t('menu.pipelines')"
                 :intro="t('pipe.intro')" />
    <div class="toolbar">
      <el-button @click="load" :loading="loading">{{ t("pipe.refresh") }}</el-button>
      <el-button type="danger" :disabled="!selected.length"
                 @click="removeSelected">
        {{ t("pipe.deleteSelected").replace("{n}", selected.length) }}
      </el-button>
      <el-button type="primary" @click="create">{{ t("pipe.newPipeline") }}</el-button>
    </div>

    <el-card class="card" shadow="never">
      <el-table :data="rows" size="small" v-loading="loading"
                row-class-name="clickable" @row-click="open"
                @selection-change="selected = $event">
        <el-table-column type="selection" width="42" />
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column :label="t('pipe.name')" min-width="200">
          <template #default="{ row }">
            <span class="entity-cell">
              <entity-icon type="pipeline" :size="20" />
              <b>{{ row.name }}</b>
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="cron" :label="t('pipe.schedule')" width="160" />
        <el-table-column :label="t('pipe.status')" width="110">
          <template #default="{ row }">
            <status-dot :status="row.enabled"
                        :label="row.enabled
                          ? t('pipe.enabled') : t('pipe.disabled')" />
          </template>
        </el-table-column>
        <el-table-column :label="t('pipe.actions')" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="danger" @click.stop="remove(row)">
              {{ t("pipe.delete") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <empty-state v-if="!loading && !rows.length"
                   :title="t('pipe.empty')" :description="t('pipe.intro')"
                   :action-text="t('pipe.newPipeline')" @action="create" />
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../api";
import { t } from "../i18n";
import EmptyState from "../components/EmptyState.vue";
import EntityIcon from "../components/EntityIcon.vue";
import PageHeader from "../components/PageHeader.vue";
import StatusDot from "../components/StatusDot.vue";

const rows = ref([]);
const selected = ref([]);
const loading = ref(false);
const router = useRouter();

async function load() {
  loading.value = true;
  try {
    rows.value = await api.get("/pipelines");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

async function removeSelected() {
  if (!selected.value.length) return;
  try {
    await ElMessageBox.confirm(
      t("pipe.deleteSelectedConfirm").replace("{n}", selected.value.length),
      t("pipe.deleteTitle"), { type: "warning" });
  } catch (e) {
    return;
  }
  let failed = 0;
  for (const row of selected.value) {
    try {
      await api.del(`/pipelines/${row.id}`);
    } catch (e) {
      failed += 1;
    }
  }
  selected.value = [];
  await load();
  if (failed) {
    ElMessage.error(t("pipe.deleteFailed").replace("{n}", failed));
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(
      t("pipe.deleteConfirm").replace("{name}", row.name),
      t("pipe.deleteTitle"), { type: "warning" });
  } catch (e) {
    return;
  }
  try {
    await api.del(`/pipelines/${row.id}`);
    ElMessage.success(t("pipe.deleted"));
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function create() {
  try {
    const a = await api.post("/pipelines", {
      name: t("pipe.newDefaultName"),
      content: { nodes: [], edges: [], settings: { batch: 1000 } },
    });
    await load();
    router.push(`/pipelines/${a.id}`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

function open(row) {
  router.push(`/pipelines/${row.id}`);
}

onMounted(load);
</script>

<style scoped>
.entity-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.card { border-radius: 12px; border: 1px solid #e5e7eb; }
:deep(.clickable) { cursor: pointer; }
</style>
