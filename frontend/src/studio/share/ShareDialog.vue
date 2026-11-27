<template>
  <el-button v-if="canShare" size="small" :disabled="!published"
             @click="open">
    {{ t("share.share") }}
  </el-button>
  <el-dialog v-model="visible" :title="t('share.title')" width="600px">
    <div class="row">
      <el-radio-group v-model="mode" size="small">
        <el-radio-button value="share">{{ t("share.modeShare") }}</el-radio-button>
        <el-radio-button value="embed">{{ t("share.modeEmbed") }}</el-radio-button>
      </el-radio-group>
      <span class="hint">{{ t("share.validity") }}</span>
      <el-select v-model="days" size="small" style="width: 120px">
        <el-option :value="1" :label="t('share.days1')" />
        <el-option :value="7" :label="t('share.days7')" />
        <el-option :value="30" :label="t('share.days30')" />
      </el-select>
      <div class="spacer" />
      <el-button size="small" type="primary" :loading="creating"
                 @click="create">{{ t("share.generate") }}</el-button>
    </div>
    <el-alert v-if="createdUrl" type="success" :closable="false"
              :title="t('share.created')">
      <el-input :model-value="createdUrl" readonly size="small">
        <template #append>
          <el-button @click="copy">{{ t("share.copy") }}</el-button>
        </template>
      </el-input>
      <div class="embed">
        <div class="hint">{{ t("share.embedHint") }}</div>
        <el-input :model-value="embedCode" type="textarea" :rows="3"
                  readonly size="small" />
        <el-button size="small" style="margin-top: 6px"
                   @click="copyEmbed">{{ t("share.copyEmbed") }}</el-button>
      </div>
    </el-alert>
    <el-table :data="shares" size="small" :empty-text="t('share.empty')"
              style="margin-top: 12px">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column :label="t('share.mode')" width="90">
        <template #default="{ row }">
          {{ row.mode === "embed" ? t("share.modeEmbed")
            : t("share.modeShare") }}
        </template>
      </el-table-column>
      <el-table-column :label="t('share.createdAt')" width="170">
        <template #default="{ row }">{{ fmt(row.created_at) }}</template>
      </el-table-column>
      <el-table-column :label="t('share.expiresAt')" width="170">
        <template #default="{ row }">{{ fmt(row.expires_at) }}</template>
      </el-table-column>
      <el-table-column :label="t('share.status')" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="row.active ? 'success' : 'info'">
            {{ row.active ? t("share.active") : t("share.expired") }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('share.actions')" width="90">
        <template #default="{ row }">
          <el-button v-if="row.active" link type="danger"
                     @click="revoke(row)">{{ t("share.revoke") }}</el-button>
        </template>
      </el-table-column>
    </el-table>
    <p class="hint">
      {{ t("share.hint") }}
    </p>
  </el-dialog>
</template>

<script setup>
import { computed, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg, getRole } from "../../api";
import { fmtDate, t } from "../../i18n";

const props = defineProps({
  kind: { type: String, required: true },
  assetId: { type: Number, required: true },
  published: Boolean,
});
const canShare = computed(() =>
  ["editor", "approver", "admin"].includes(getRole()));
const visible = ref(false);
const days = ref(7);
const mode = ref("share");
const creating = ref(false);
const createdUrl = ref("");
const createdToken = ref("");
const shares = ref([]);
const embedCode = computed(() => {
  if (!createdUrl.value) return "";
  if (mode.value === "share") {
    return `<iframe src="${createdUrl.value}" width="100%" height="720" ` +
      `style="border:0" loading="lazy"></iframe>`;
  }
  const base = `${location.origin}${location.pathname}`;
  return `<div id="weft-embed"></div>
` +
    `<script src="${base}weft-embed.js"><\/script>
` +
    `<script>WeftEmbed.mount({target:"#weft-embed", ` +
    `token:"${createdToken.value}", height:720});<\/script>`;
});

function fmt(v) {
  if (!v) return "-";
  return fmtDate(v);
}

async function load() {
  try {
    shares.value = await api.get(`/${props.kind}/${props.assetId}/shares`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

function open() {
  visible.value = true;
  createdUrl.value = "";
  load();
}

async function create() {
  creating.value = true;
  try {
    const r = await api.post(`/${props.kind}/${props.assetId}/share`,
                             { expires_days: days.value, mode: mode.value });
    createdToken.value = r.token;
    createdUrl.value = `${location.origin}${location.pathname}`
      + (r.mode === "embed" ? "#/embed/" : "#/share/") + r.token;
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    creating.value = false;
  }
}

async function copy() {
  try {
    await navigator.clipboard.writeText(createdUrl.value);
    ElMessage.success(t("share.copied"));
  } catch (e) {
    ElMessage.error(t("share.copyFailed"));
  }
}

async function copyEmbed() {
  try {
    await navigator.clipboard.writeText(embedCode.value);
    ElMessage.success(t("share.copied"));
  } catch (e) {
    ElMessage.error(t("share.copyFailed"));
  }
}

async function revoke(row) {
  try {
    await ElMessageBox.confirm(t("share.revokeConfirm"), t("share.revokeTitle"));
    await api.post(`/${props.kind}/${props.assetId}/shares/${row.id}/revoke`);
    ElMessage.success(t("share.revoked"));
    await load();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}
</script>

<style scoped>
.row { display: flex; gap: 8px; align-items: center; }
.spacer { flex: 1; }
.hint { font-size: 12px; color: #6b7280; }
.embed { margin-top: 10px; }
</style>
