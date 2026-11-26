<template>
  <div class="app-component" :class="`type-${component.type}`">
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <template v-else-if="component.type === 'form'">
      <AppForm :component="component" :on-submit="onSubmit"
               @change="$emit('change', $event)" />
    </template>
    <div v-else-if="component.type === 'heading'" class="heading"
         :style="contentStyle">
      {{ text }}
    </div>
    <div v-else-if="component.type === 'text'" class="text"
         :style="contentStyle">{{ text }}</div>
    <el-divider v-else-if="component.type === 'divider'" />
    <el-image v-else-if="component.type === 'image'" :src="component.url"
              :alt="component.alt || ''" fit="cover" class="image">
      <template #error>
        <div class="image-fallback">{{ component.alt || component.url }}</div>
      </template>
    </el-image>
    <el-button v-else-if="component.type === 'button'" type="primary"
               @click="act">
      {{ label }}
    </el-button>
    <el-progress v-else-if="component.type === 'progress'"
                 :percentage="percentage" :stroke-width="14"
                 :status="percentage >= 100 ? 'success' : ''" />
    <div v-else-if="component.type === 'metric'" class="value">
      {{ metricValue() }}
    </div>
    <template v-else-if="component.type === 'table'">
      <el-table :data="entry?.rows || []" size="small" border stripe
                @row-click="$emit('row', $event)">
        <el-table-column v-for="col in tableColumns()" :key="col" :prop="col"
                         :label="col" min-width="110"
                         show-overflow-tooltip />
      </el-table>
      <div class="count">
        {{ t("acomp.total") }} {{ entry?.row_count || 0 }}
        {{ t("acomp.rows") }}
      </div>
    </template>
    <template v-else-if="component.type === 'list'">
      <div class="list-box">
        <div v-for="(row, index) in entry?.rows || []" :key="index"
             class="list-row" @click="$emit('row', row)">
          <div class="list-main">
            <b>{{ listText(row, component.title_column) }}</b>
            <span v-if="component.subtitle_column">
              {{ listText(row, component.subtitle_column) }}
            </span>
          </div>
          <span v-if="component.value_column" class="list-value">
            {{ listText(row, component.value_column) }}
          </span>
        </div>
        <el-empty v-if="!(entry?.rows || []).length"
                  :description="t('cat.noMatches')" :image-size="40" />
      </div>
      <div class="count">
        {{ t("acomp.total") }} {{ entry?.row_count || 0 }}
        {{ t("acomp.rows") }}
      </div>
    </template>
    <template v-else-if="component.type === 'upload'">
      <el-upload :show-file-list="false" :accept="acceptText"
                 :http-request="uploadFile" :disabled="design">
        <el-button :loading="uploading" :disabled="design">
          {{ label }}
        </el-button>
      </el-upload>
      <div v-if="uploaded" class="uploaded">
        <span>{{ uploaded.name }}</span>
        <el-button link type="primary" @click="downloadFile">
          {{ t("acomp.open") }}
        </el-button>
      </div>
      <el-alert v-if="uploadError" :title="uploadError" type="warning"
                :closable="false" />
      <p class="hint">{{ uploadHint }}</p>
    </template>
    <template v-else-if="component.type === 'approval'">
      <div class="approval-head">
        <b>{{ component.title || t('acomp.approvalQueue') }}</b>
        <el-button link size="small" :loading="approvalLoading"
                   @click="loadApprovals">{{ t("common.refresh") }}</el-button>
      </div>
      <el-table :data="approvals" size="small" border
                :empty-text="t('acomp.noApprovals')">
        <el-table-column prop="target_name" :label="t('acomp.target')"
                         min-width="160" />
        <el-table-column prop="action" :label="t('acomp.action')"
                         width="150" />
        <el-table-column prop="actor" :label="t('acomp.requester')"
                         width="100" />
        <el-table-column :label="t('acomp.createdAt')" width="160">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column v-if="canApprove" :label="t('acomp.actions')"
                         width="90">
          <template #default="{ row }">
            <el-button link type="primary" :loading="row.saving"
                       @click.stop="approve(row)">
              {{ t("acomp.approve") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { api, errMsg, getRole } from "../../api";
import { t } from "../../i18n";
import AppForm from "./AppForm.vue";
import { interpolate, progressValue } from "./bindings";

const props = defineProps({
  component: { type: Object, required: true },
  entry: { type: Object, default: null },
  params: { type: Object, default: () => ({}) },
  components: { type: Object, default: () => ({}) },
  visual: { type: Object, default: () => ({}) },
  onSubmit: { type: Function, default: null },
  design: Boolean,
});
const emit = defineEmits(["navigate", "row", "change", "action"]);
const uploading = ref(false);
const uploaded = ref(null);
const uploadError = ref("");
const approvals = ref([]);
const approvalLoading = ref(false);
const canApprove = computed(() =>
  ["approver", "admin"].includes(getRole()));
const acceptText = computed(() => (props.component.accept || [])
  .map((item) => `.${item}`).join(","));
const uploadHint = computed(() => {
  const max = props.component.max_mb || 20;
  const types = (props.component.accept || []).join(",");
  return types ? `${types} · ≤ ${max} MB` : `≤ ${max} MB`;
});

const error = computed(() => props.entry?.error || "");
const text = computed(() => interpolate(
  props.component.text ?? props.entry?.text ?? "",
  props.params, { keepMissing: props.design,
                  components: props.components }));
const label = computed(() => interpolate(
  props.component.label || props.component.text || t("acomp.open"),
  props.params, { keepMissing: props.design,
                  components: props.components }));
const percentage = computed(() =>
  progressValue(props.component, props.params));
const contentStyle = computed(() => {
  const out = {};
  if (props.visual.color) out.color = props.visual.color;
  if (props.visual.textAlign) out.textAlign = props.visual.textAlign;
  if (props.visual.fontSize) out.fontSize = props.visual.fontSize;
  return out;
});

function metricValue() {
  const row = props.entry?.rows?.[0] || {};
  const cols = props.entry?.columns || [];
  const col = props.component.value_column || cols[cols.length - 1]
    || "value";
  const value = row[col];
  if (value === null || value === undefined) return "-";
  return typeof value === "number"
    ? value.toLocaleString("zh-CN") : value;
}

function listText(row, key) {
  if (key && row && row[key] !== undefined && row[key] !== null) {
    return row[key];
  }
  const columns = tableColumns();
  return row && columns.length ? row[columns[0]] : "";
}

function fmtTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value
    : date.toLocaleString("zh-CN", { hour12: false });
}

async function uploadFile({ file }) {
  const max = props.component.max_mb || 20;
  if (file.size > max * 1024 * 1024) {
    uploadError.value = t("acomp.fileTooLarge").replace("{n}", max);
    return;
  }
  uploading.value = true;
  uploadError.value = "";
  try {
    const result = await api.upload(file);
    uploaded.value = result;
    emit("change", { file: {
      id: result.id, name: result.name, size: result.size,
      content_type: result.content_type,
      url: `/api/v1/files/${result.id}/download`,
    }});
  } catch (error) {
    uploadError.value = errMsg(error);
  } finally {
    uploading.value = false;
  }
}

async function downloadFile() {
  if (!uploaded.value) return;
  try {
    await api.download(`/files/${uploaded.value.id}/download`,
                       uploaded.value.name || "file");
  } catch (error) {
    ElMessage.error(errMsg(error));
  }
}

async function loadApprovals() {
  if (props.design) return;
  approvalLoading.value = true;
  try {
    const rows = await api.get("/changes?status=proposed");
    approvals.value = (rows || []).slice(0, props.component.limit || 10);
  } catch (error) {
    ElMessage.error(errMsg(error));
  } finally {
    approvalLoading.value = false;
  }
}

async function approve(row) {
  row.saving = true;
  try {
    const approved = await api.post(`/changes/${row.id}/approve`);
    await api.post(`/changes/${row.id}/apply?approval_token=${
      encodeURIComponent(approved.approval_token)}`);
    ElMessage.success(t("acomp.approved"));
    await loadApprovals();
  } catch (error) {
    ElMessage.error(errMsg(error));
  } finally {
    row.saving = false;
  }
}

function tableColumns() {
  return props.component.columns?.length ? props.component.columns
    : (props.entry?.columns || []);
}

onMounted(() => {
  if (props.component.type === "approval" && !props.design) {
    loadApprovals();
  }
});

function act() {
  if (props.design) return;
  if (props.component.actions?.length) {
    emit("action", props.component.actions);
    return;
  }
  if (props.component.target_page) {
    emit("navigate", props.component.target_page);
  } else if (props.component.url) {
    window.open(props.component.url, "_blank", "noopener,noreferrer");
  }
}
</script>

<style scoped>
.app-component { min-height: 20px; }
.heading { font-size: 22px; font-weight: 700; color: #0f172a;
           line-height: 1.35; }
.text { font-size: 13px; color: #334155; white-space: pre-wrap;
        line-height: 1.65; }
.value { font-size: 30px; font-weight: 700; color: #0f172a; }
.count { font-size: 11px; color: #6b7280; margin-top: 6px; }
.list-box { display: flex; flex-direction: column; gap: 6px; }
.list-row { display: flex; align-items: center; justify-content: space-between;
            gap: 10px; padding: 8px 10px; border: 1px solid #e5e7eb;
            border-radius: 7px; background: #fff; cursor: pointer; }
.list-row:hover { border-color: #93c5fd; background: #eff6ff; }
.list-main { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.list-main b { font-size: 13px; color: #0f172a; }
.list-main span { font-size: 11px; color: #64748b; }
.list-value { font-size: 14px; font-weight: 600; color: #0f172a; }
.uploaded { display: flex; align-items: center; gap: 8px; margin-top: 6px;
            font-size: 12px; color: #334155; }
.hint { font-size: 11px; color: #94a3b8; margin: 6px 0 0; }
.approval-head { display: flex; align-items: center; justify-content:
                 space-between; margin-bottom: 6px; }
.image { width: 100%; height: 100%; min-height: 80px; border-radius: 4px;
         background: #f1f5f9; }
.image-fallback { display: flex; align-items: center; justify-content: center;
                  height: 100%; min-height: 80px; padding: 8px;
                  font-size: 12px; color: #64748b; }
</style>
