<template>
  <StudioShell :title="title" :cron="cron" :published="published"
               :enabled="enabled" :saving="saving"
               @rename="title = $event" @rename-save="renameSave"
               @schedule="saveSchedule" @save="save" @validate="validate"
               @preview="preview" @run="run" @backfill="backfillOpen = true"
               @cursors="openCursors" @toggle="toggle"
               @publish="publishDialog = true"
               @versions="versionsOpen = true">
    <template #tree>
      <AssetTree :items="treeItems" :active-id="id" @select="openOther" />
    </template>
    <PipelineCanvas ref="canvasRef" :content="content"
                    @select="selected = $event" @change="dirty = true" />
    <template #config>
      <NodeConfig :node="selected" :datasources="datasources"
                  @update="dirty = true" />
    </template>
    <template #console>
      <PreviewPanel ref="previewRef" :asset-id="id"
                    :node-id="selected?.id || ''"
                    :content-fn="currentContent" />
    </template>
  </StudioShell>
  <VersionDrawer v-model="versionsOpen" :asset-id="id" @changed="load" />
  <PublishDialog v-model="publishDialog" @confirm="publish" />
  <el-dialog v-model="cursorsOpen" title="增量游标" width="680px">
    <el-alert type="warning" :closable="false" show-icon
              title="修改游标会改变下一次增量读取的起点，请确认后再保存。"
              style="margin-bottom: 14px" />
    <el-table :data="cursors.sources" size="small">
      <el-table-column prop="node_id" label="节点" width="90" />
      <el-table-column prop="table" label="表" min-width="120" />
      <el-table-column prop="cursor_column" label="游标列" width="120" />
      <el-table-column label="当前游标" min-width="260">
        <template #default="{ row }">
          <el-input v-model="row.edit" size="small"
                    placeholder="留空表示清除" />
        </template>
      </el-table-column>
      <el-table-column label="" width="80">
        <template #default="{ row }">
          <el-button link type="primary" @click="saveCursor(row)">保存</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!cursors.sources.length" description="没有 source 节点"
              :image-size="60" />
  </el-dialog>

  <el-dialog v-model="backfillOpen" title="历史回填" width="540px">
    <el-alert type="info" :closable="false" show-icon
              title="从起始游标重放已发布管道；不会改动生产游标。结束游标可留空表示读到末尾。"
              style="margin-bottom: 14px" />
    <el-form label-width="96px">
      <el-form-item label="起始游标" required>
        <el-input v-model="backfillForm.start_cursor"
                  placeholder="例如 2026-01-01 或 1000" />
      </el-form-item>
      <el-form-item label="结束游标">
        <el-input v-model="backfillForm.end_cursor"
                  placeholder="可选，包含该值" />
      </el-form-item>
      <el-form-item label="批大小">
        <el-input-number v-model="backfillForm.batch" :min="1"
                         :max="100000" placeholder="使用管道设置" />
      </el-form-item>
      <el-form-item label="最大批数">
        <el-input-number v-model="backfillForm.max_batches" :min="1"
                         :max="1000" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="backfillOpen = false">取消</el-button>
      <el-button type="primary" :loading="backfilling"
                 @click="startBackfill">开始回填</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { api, errMsg } from "../api";
import StudioShell from "../studio/StudioShell.vue";
import AssetTree from "../studio/AssetTree.vue";
import PipelineCanvas from "../studio/pipeline/PipelineCanvas.vue";
import NodeConfig from "../studio/pipeline/NodeConfig.vue";
import PreviewPanel from "../studio/pipeline/PreviewPanel.vue";
import VersionDrawer from "../studio/pipeline/VersionDrawer.vue";
import PublishDialog from "../studio/pipeline/PublishDialog.vue";

const route = useRoute();
const router = useRouter();
const id = Number(route.params.id);
const title = ref("");
const savedTitle = ref("");
const cron = ref("");
const content = ref({ nodes: [], edges: [], settings: {} });
const selected = ref(null);
const datasources = ref([]);
const treeItems = ref([]);
const published = ref(false);
const enabled = ref(true);
const saving = ref(false);
const dirty = ref(false);
const versionsOpen = ref(false);
const publishDialog = ref(false);
const backfillOpen = ref(false);
const cursorsOpen = ref(false);
const cursors = reactive({ cursors: {}, sources: [] });
const backfilling = ref(false);
const backfillForm = reactive({ start_cursor: "", end_cursor: "",
                                batch: null, max_batches: 100 });
const settings = ref({ batch: 1000 });
const canvasRef = ref(null);
const previewRef = ref(null);

async function load() {
  try {
    const a = await api.get(`/pipelines/${id}`);
    title.value = a.name;
    savedTitle.value = a.name;
    cron.value = a.cron || "";
    content.value = a.draft || { nodes: [], edges: [], settings: {} };
    settings.value = content.value.settings || { batch: 1000 };
    published.value = Boolean(a.published);
    enabled.value = a.enabled !== false;
    selected.value = null;
    treeItems.value = await api.get("/pipelines");
    datasources.value = await api.get("/datasources");
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

async function save() {
  if (!canvasRef.value) return;
  saving.value = true;
  try {
    const c = currentContent();
    await api.put(`/pipelines/${id}/draft`, { content: c });
    dirty.value = false;
    ElMessage.success("已保存草稿");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

async function validate() {
  try {
    const c = currentContent();
    const r = await api.post(`/pipelines/${id}/validate`, { content: c });
    if (r.valid) ElMessage.success("校验通过");
    else ElMessage.error(r.errors.map(
      (e) => `${e.node_id || "-"}: ${e.message}`).join("; "));
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
    ElMessage.success("名称已保存");
  } catch (e) {
    title.value = savedTitle.value;
    ElMessage.error(errMsg(e));
  }
}

async function saveSchedule(value) {
  try {
    const a = await api.put(`/pipelines/${id}`, { cron: value });
    cron.value = a.cron || "";
    ElMessage.success(a.cron ? "调度已保存" : "已取消调度");
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

function preview() {
  if (!selected.value) {
    ElMessage.info("先选中画布上的节点");
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
    ElMessage.success("已发布");
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function run() {
  try {
    const r = await api.post(`/pipelines/${id}/run`);
    ElMessage.success(`已入队 job ${r.job_id}`);
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
    ElMessage.success(`游标已更新：${row.node_id}`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function startBackfill() {
  if (!backfillForm.start_cursor) {
    ElMessage.warning("起始游标必填");
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
    ElMessage.success(`回填已入队 job ${r.job_id}`);
    pollJob(r.job_id);
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    backfilling.value = false;
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
          `job ${jobId}: ${j.status}`);
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
    ElMessage.success("已更新");
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

onMounted(load);
</script>
