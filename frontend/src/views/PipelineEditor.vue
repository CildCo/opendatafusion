<template>
  <StudioShell :title="title" :cron="cron" :published="published"
               :enabled="enabled" :saving="saving"
               :can-undo="canUndo" :can-redo="canRedo"
               @undo="history.undo" @redo="history.redo"
               @rename="title = $event" @rename-save="renameSave"
               @schedule="saveSchedule" @save="save" @validate="validate"
               @preview="preview" @run="run" @backfill="backfillOpen = true"
               @cursors="openCursors" @toggle="toggle"
               @publish="publishDialog = true"
               @versions="versionsOpen = true"
               @governance="governanceOpen = true">
    <template #tree>
      <AssetTree :items="treeItems" :active-id="id" @select="openOther" />
    </template>
    <PipelineCanvas ref="canvasRef" :content="content" :runtime="runtime"
                    @select="selected = $event" @change="onCanvasChange" />
    <template #config>
      <NodeConfig :node="selected" :datasources="datasources"
                  @update="onNodeUpdate" />
    </template>
    <template #console>
      <PreviewPanel ref="previewRef" :asset-id="id"
                    :node-id="selected?.id || ''"
                    :content-fn="currentContent" />
    </template>
  </StudioShell>
  <VersionDrawer v-model="versionsOpen" :asset-id="id" @changed="load" />
  <GovernanceDrawer v-model="governanceOpen" :asset-id="id" />
  <PublishDialog v-model="publishDialog" @confirm="publish" />
  <el-dialog v-model="cursorsOpen" :title="t('ped.cursorsTitle')" width="680px">
    <el-alert type="warning" :closable="false" show-icon
              :title="t('ped.cursorsHint')"
              style="margin-bottom: 14px" />
    <el-table :data="cursors.sources" size="small">
      <el-table-column prop="node_id" :label="t('ped.colNode')" width="90" />
      <el-table-column prop="table" :label="t('ped.colTable')" min-width="120" />
      <el-table-column prop="cursor_column" :label="t('ped.colCursorColumn')" width="120" />
      <el-table-column :label="t('ped.colCurrentCursor')" min-width="260">
        <template #default="{ row }">
          <el-input v-model="row.edit" size="small"
                    :placeholder="t('ped.clearCursorPlaceholder')" />
        </template>
      </el-table-column>
      <el-table-column label="" width="80">
        <template #default="{ row }">
          <el-button link type="primary" @click="saveCursor(row)">{{ t('ped.save') }}</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!cursors.sources.length" :description="t('ped.noSourceNodes')"
              :image-size="60" />
  </el-dialog>

  <el-dialog v-model="validationOpen" :title="t('ped.validationTitle')"
             width="560px">
    <el-alert v-if="validationOk" type="success" :closable="false"
              :title="t('ped.validationPassed')" />
    <el-table v-else :data="validationRows" size="small">
      <el-table-column prop="node_id" :label="t('ped.colNode')" width="140">
        <template #default="{ row }">{{ row.node_id || "-" }}</template>
      </el-table-column>
      <el-table-column prop="field" :label="t('ped.validationField')"
                       width="130" />
      <el-table-column prop="message" :label="t('ped.validationMessage')" />
    </el-table>
    <template #footer>
      <el-button @click="validationOpen = false">{{ t("common.close") }}</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="backfillOpen" :title="t('ped.backfillTitle')" width="540px">
    <el-alert type="info" :closable="false" show-icon
              :title="t('ped.backfillHint')"
              style="margin-bottom: 14px" />
    <el-form label-width="96px">
      <el-form-item :label="t('ped.startCursor')" required>
        <el-input v-model="backfillForm.start_cursor"
                  :placeholder="t('ped.startCursorPlaceholder')" />
      </el-form-item>
      <el-form-item :label="t('ped.endCursor')">
        <el-input v-model="backfillForm.end_cursor"
                  :placeholder="t('ped.endCursorPlaceholder')" />
      </el-form-item>
      <el-form-item :label="t('ped.batchSize')">
        <el-input-number v-model="backfillForm.batch" :min="1"
                         :max="100000" :placeholder="t('ped.batchPlaceholder')" />
      </el-form-item>
      <el-form-item :label="t('ped.maxBatches')">
        <el-input-number v-model="backfillForm.max_batches" :min="1"
                         :max="1000" />
      </el-form-item>
    </el-form>
    <el-alert v-if="backfillPreview" type="info" :closable="false"
              style="margin-top: 8px">
      <p class="preview-line">
        {{ t("ped.previewSummary")
          .replace("{sources}", backfillPreview.sources.length)
          .replace("{batch}", backfillPreview.batch)
          .replace("{max}", backfillPreview.max_batches) }}
      </p>
      <p v-for="(warning, i) in backfillPreview.warnings" :key="i"
         class="preview-line">· {{ warning }}</p>
    </el-alert>
    <template #footer>
      <el-button @click="backfillOpen = false">{{ t('ped.cancel') }}</el-button>
      <el-button :loading="previewingBackfill"
                 @click="previewBackfill">{{ t('ped.previewBackfill') }}</el-button>
      <el-button type="primary" :loading="backfilling"
                 @click="startBackfill">{{ t('ped.startBackfill') }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../api";
import { t } from "../i18n";
import { useDraftSafety } from "../draftSafety";
import StudioShell from "../studio/StudioShell.vue";
import AssetTree from "../studio/AssetTree.vue";
import PipelineCanvas from "../studio/pipeline/PipelineCanvas.vue";
import NodeConfig from "../studio/pipeline/NodeConfig.vue";
import PreviewPanel from "../studio/pipeline/PreviewPanel.vue";
import VersionDrawer from "../studio/pipeline/VersionDrawer.vue";
import PublishDialog from "../studio/pipeline/PublishDialog.vue";
import GovernanceDrawer from "../components/GovernanceDrawer.vue";
import { bindHistoryKeys, useHistory } from "../composables/useHistory";

const route = useRoute();
const router = useRouter();
const id = Number(route.params.id);
const title = ref("");
const draftVersion = ref(null);
const savedTitle = ref("");
const cron = ref("");
const content = ref({ nodes: [], edges: [], settings: {} });
const history = useHistory(content);
const { canUndo, canRedo } = history;
bindHistoryKeys(history);
const selected = ref(null);
const datasources = ref([]);
const treeItems = ref([]);
const published = ref(false);
const enabled = ref(true);
const saving = ref(false);
const dirty = ref(false);
const versionsOpen = ref(false);
const governanceOpen = ref(false);
const publishDialog = ref(false);
const backfillOpen = ref(false);
const validationOpen = ref(false);
const validationOk = ref(true);
const validationRows = ref([]);
const cursorsOpen = ref(false);
const cursors = reactive({ cursors: {}, sources: [] });
const backfilling = ref(false);
const previewingBackfill = ref(false);
const backfillPreview = ref(null);
const backfillForm = reactive({ start_cursor: "", end_cursor: "",
                                batch: null, max_batches: 100 });
const settings = ref({ batch: 1000 });
const canvasRef = ref(null);
const runtime = ref({});
const previewRef = ref(null);

async function load() {
  try {
    const a = await api.get(`/pipelines/${id}`);
    title.value = a.name;
    draftVersion.value = a.draft_version;
    savedTitle.value = a.name;
    cron.value = a.cron || "";
    content.value = a.draft || { nodes: [], edges: [], settings: {} };
    history.reset();
    settings.value = content.value.settings || { batch: 1000 };
    published.value = Boolean(a.published);
    enabled.value = a.enabled !== false;
    selected.value = null;
    treeItems.value = (await api.get("/pipelines?page_size=200")).items || [];
    datasources.value = await api.get("/datasources");
    dirty.value = false;
    draftGuard.reset();
    await loadRuntime();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

function openOther(p) {
  if (p.id !== id) router.push(`/pipelines/${p.id}`);
}

function normalized(c) {
  for (const n of c.nodes || []) {
    if (n.type === "rename") {
      n.config.mapping = Object.fromEntries(
        (n.config.pairs || []).map((p) => [p.from, p.to]));
      delete n.config.pairs;
    }
    if (n.type === "cast") {
      n.config.mapping = Object.fromEntries(
        (n.config.pairs || []).map((p) => [p.column, p.type]));
      delete n.config.pairs;
    }
  }
  return c;
}

function currentContent() {
  if (!canvasRef.value) return null;
  return normalized(canvasRef.value.serialize(settings.value));
}

async function save(silent = false) {
  if (!canvasRef.value) return false;
  saving.value = true;
  try {
    const c = currentContent();
    const body = { content: c };
    if (draftVersion.value !== null) body.base_version = draftVersion.value;
    const result = await api.put(`/pipelines/${id}/draft`, body);
    draftVersion.value = result.version;
    dirty.value = false;
    if (!silent) ElMessage.success(t("ped.draftSaved"));
    return true;
  } catch (e) {
    if (/draft changed/i.test(e.message || "")) {
      ElMessageBox.confirm(t("draft.conflict"), t("draft.conflictTitle"),
        { type: "warning" })
        .then(() => load()).catch(() => {});
    } else if (!silent) {
      ElMessage.error(errMsg(e));
    }
    return false;
  } finally {
    saving.value = false;
  }
}

const draftGuard = useDraftSafety({ content, save });

async function validate() {
  try {
    const c = currentContent();
    const r = await api.post(`/pipelines/${id}/validate`, { content: c });
    validationOk.value = Boolean(r.valid);
    validationRows.value = r.errors || [];
    validationOpen.value = true;
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function renameSave(name) {
  if (!name || name === savedTitle.value) return;
  try {
    const a = await api.put(`/pipelines/${id}`, { name });
    title.value = a.name;
    savedTitle.value = a.name;
    ElMessage.success(t("ped.nameSaved"));
  } catch (e) {
    title.value = savedTitle.value;
    ElMessage.error(errMsg(e));
  }
}

async function saveSchedule(value) {
  try {
    const a = await api.put(`/pipelines/${id}`, { cron: value });
    cron.value = a.cron || "";
    ElMessage.success(a.cron ? t("ped.scheduleSaved") : t("ped.scheduleCleared"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

function preview() {
  if (!selected.value) {
    ElMessage.info(t("ped.selectNodeFirst"));
    return;
  }
  previewRef.value?.run();
}

async function publish() {
  try {
    await save();
    await api.applyChange("publish_pipeline", id);
    publishDialog.value = false;
    await load();
    ElMessage.success(t("ped.published"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function run() {
  try {
    const r = await api.post(`/pipelines/${id}/run`);
    ElMessage.success(`${t("ped.queuedJob")} ${r.job_id}`);
    pollJob(r.job_id);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function openCursors() {
  try {
    const r = await api.get(`/pipelines/${id}/cursors`);
    cursors.cursors = r.cursors || {};
    cursors.sources = (r.sources || []).map((x) => ({
      ...x, edit: x.cursor || "",
    }));
    cursorsOpen.value = true;
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function saveCursor(row) {
  try {
    const r = await api.put(`/pipelines/${id}/cursors`, {
      node_id: row.node_id,
      cursor: row.edit ? row.edit : null,
    });
    cursors.cursors = r.cursors || {};
    row.cursor = r.cursors?.[row.node_id] || null;
    ElMessage.success(`${t("ped.cursorUpdated")}${row.node_id}`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function previewBackfill() {
  previewingBackfill.value = true;
  try {
    backfillPreview.value = await api.post(
      `/pipelines/${id}/backfill/preview`, {
        start_cursor: backfillForm.start_cursor,
        end_cursor: backfillForm.end_cursor || null,
        batch: backfillForm.batch || null,
        max_batches: backfillForm.max_batches || 100,
      });
  } catch (e) {
    backfillPreview.value = null;
    ElMessage.error(errMsg(e));
  } finally {
    previewingBackfill.value = false;
  }
}

async function startBackfill() {
  if (!backfillForm.start_cursor) {
    ElMessage.warning(t("ped.startCursorRequired"));
    return;
  }
  backfilling.value = true;
  try {
    const r = await api.post(`/pipelines/${id}/backfill`, {
      start_cursor: backfillForm.start_cursor,
      end_cursor: backfillForm.end_cursor || null,
      batch: backfillForm.batch || null,
      max_batches: backfillForm.max_batches,
    });
    backfillOpen.value = false;
    ElMessage.success(`${t("ped.backfillQueued")} ${r.job_id}`);
    pollJob(r.job_id);
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    backfilling.value = false;
  }
}

function onCanvasChange() {
  if (!canvasRef.value) {
    dirty.value = true;
    return;
  }
  const snapshot = canvasRef.value.serialize(settings.value);
  content.value = {
    nodes: snapshot.nodes, edges: snapshot.edges,
    settings: snapshot.settings,
  };
  dirty.value = true;
}

function onNodeUpdate() {
  dirty.value = true;
  canvasRef.value?.notify();
}

async function loadRuntime() {
  try {
    const jobs = await api.get(`/pipelines/${id}/jobs`);
    const latest = jobs.find((job) => (job.nodes || []).length) || jobs[0];
    const map = {};
    for (const node of latest?.nodes || []) map[node.node_id] = node;
    runtime.value = map;
  } catch {
    runtime.value = {};
  }
}

async function pollJob(jobId) {
  for (let i = 0; i < 30; i++) {
    await new Promise((r) => setTimeout(r, 2000));
    try {
      const jobs = await api.get(`/pipelines/${id}/jobs`);
      const j = jobs.find((x) => x.id === jobId);
      if (j && (j.status === "success" || j.status === "failed")) {
        ElMessage[j.status === "success" ? "success" : "error"](
          `${t("ped.jobLabel")} ${jobId}: ${j.status}`);
        await loadRuntime();
        return;
      }
    } catch (e) {
      /* keep polling */
    }
  }
}

async function toggle() {
  try {
    await api.applyChange(
      enabled.value ? "pause_pipeline" : "resume_pipeline", id);
    await load();
    ElMessage.success(t("ped.updated"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

onMounted(load);
</script>
