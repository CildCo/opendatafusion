<template>
  <div class="page">
    <page-header icon="pipeline" :title="t('menu.pipelines')"
                 :intro="t('pipe.intro')" />
    <div class="toolbar">
      <el-button @click="load" :loading="loading">{{ t("pipe.refresh") }}</el-button>
      <el-button v-if="canEdit" type="danger" :disabled="!selected.length"
                 @click="removeSelected">
        {{ t("pipe.deleteSelected").replace("{n}", selected.length) }}
      </el-button>
      <el-button v-if="canEdit" type="primary" @click="create">{{ t("pipe.newPipeline") }}</el-button>
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
        <el-table-column :label="t('pipe.actions')" width="170" fixed="right">
          <template #default="{ row }">
            <el-button link @click.stop="openRuns(row)">
              {{ t("pipe.runs") }}
            </el-button>
            <el-button v-if="canEdit" link type="danger"
                       @click.stop="remove(row)">
              {{ t("pipe.delete") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <empty-state v-if="!loading && !rows.length"
                   :title="t('pipe.empty')" :description="t('pipe.intro')"
                   :action-text="canEdit ? t('pipe.newPipeline') : ''"
                   @action="create" />
    </el-card>

    <el-drawer v-model="runsOpen" :title="t('pipe.runs')" size="660px">
      <p class="runs-sub">{{ currentName }}</p>
      <empty-state v-if="!runs.length" :title="t('pipe.noRuns')"
                   :image-size="60" />
      <div v-for="job in runs" :key="job.id" class="run-block">
        <div class="run-head">
          <b>#{{ job.id }}</b>
          <el-tag size="small" :type="job.status === 'success'
            ? 'success' : (job.status === 'failed' ? 'danger' : 'info')">
            {{ job.status }}
          </el-tag>
          <span class="muted">{{ t("pipe.attempts") }} {{ job.attempts }}</span>
          <span v-if="job.created_at" class="muted">
            {{ fmtDate(job.created_at) }}
          </span>
        </div>
        <div v-if="job.last_error" class="run-error">{{ job.last_error }}</div>
        <el-table v-if="job.nodes.length" :data="job.nodes" size="small">
          <el-table-column prop="node_id" :label="t('pipe.node')"
                           min-width="150" />
          <el-table-column prop="status" :label="t('pipe.status')"
                           width="100" />
          <el-table-column prop="in_num" :label="t('pipe.inNum')" width="90" />
          <el-table-column prop="out_num" :label="t('pipe.outNum')"
                           width="90" />
          <el-table-column prop="ms" :label="t('pipe.ms')" width="90" />
          <el-table-column prop="error" :label="t('pipe.error')"
                           min-width="160" />
        </el-table>
        <p v-else class="muted">{{ t("pipe.noNodes") }}</p>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, canWrite, errMsg } from "../api";
import { fmtDate, t } from "../i18n";
import EmptyState from "../components/EmptyState.vue";
import EntityIcon from "../components/EntityIcon.vue";
import PageHeader from "../components/PageHeader.vue";
import StatusDot from "../components/StatusDot.vue";

const rows = ref([]);
const selected = ref([]);
const canEdit = canWrite();
const loading = ref(false);
const runsOpen = ref(false);
const runs = ref([]);
const currentName = ref("");
const router = useRouter();
const route = useRoute();

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

async function openRuns(row) {
  currentName.value = row.name;
  runs.value = [];
  runsOpen.value = true;
  try {
    runs.value = await api.get(`/pipelines/${row.id}/jobs`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

function open(row) {
  router.push(`/pipelines/${row.id}`);
}

onMounted(load);
onMounted(() => { if (route.query.new && canEdit) create(); });
</script>

<style scoped>
.entity-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.card { border-radius: 12px; border: 1px solid #e5e7eb; }
:deep(.clickable) { cursor: pointer; }
.runs-sub { margin: 0 0 12px; color: #64748b; font-size: 12px; }
.run-block {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 12px;
}
.run-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.run-error {
  color: #b91c1c;
  font-size: 12px;
  margin-bottom: 8px;
  word-break: break-all;
}
.muted { color: #64748b; font-size: 12px; }
</style>
