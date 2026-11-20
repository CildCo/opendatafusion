<template>
  <div class="page">
    <div class="toolbar">
      <el-button @click="load" :loading="loading">{{ t("pipe.refresh") }}</el-button>
      <el-button type="danger" :disabled="!selected.length"
                 @click="removeSelected">
        {{ t("pipe.deleteSelected").replace("{n}", selected.length) }}
      </el-button>
      <el-button type="primary" @click="create">{{ t("pipe.newPipeline") }}</el-button>
    </div>

    <p class="page-intro">{{ t("pipe.intro") }}</p>

    <el-card class="card" shadow="never">
      <el-table :data="rows" size="small" v-loading="loading"
                row-class-name="clickable" @row-click="open"
                @selection-change="selected = $event">
        <el-table-column type="selection" width="42" />
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" :label="t('pipe.name')" min-width="160" />
        <el-table-column prop="cron" :label="t('pipe.schedule')" width="160" />
        <el-table-column prop="enabled" :label="t('pipe.status')" width="100">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
              {{ row.enabled ? t("pipe.enabled") : t("pipe.disabled") }}
            </el-tag>
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
      <el-empty v-if="!loading && !rows.length" :description="t('pipe.empty')">
        <el-button type="primary" @click="create">
          {{ t("pipe.newPipeline") }}
        </el-button>
      </el-empty>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../api";
import { t } from "../i18n";

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
.card { border-radius: 12px; border: 1px solid #e5e7eb; }
:deep(.clickable) { cursor: pointer; }
</style>
