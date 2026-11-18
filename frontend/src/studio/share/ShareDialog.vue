<template>
  <el-button size="small" :disabled="!published" @click="open">
    {{ t("share.share") }}
  </el-button>
  <el-dialog v-model="visible" :title="t('share.title')" width="600px">
    <div class="row">
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
    </el-alert>
    <el-table :data="shares" size="small" :empty-text="t('share.empty')"
              style="margin-top: 12px">
      <el-table-column prop="id" label="ID" width="70" />
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
import { ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../../api";
import { t } from "../../i18n";

const props = defineProps({
  kind: { type: String, required: true },
  assetId: { type: Number, required: true },
  published: Boolean,
});
const visible = ref(false);
const days = ref(7);
const creating = ref(false);
const createdUrl = ref("");
const shares = ref([]);

function fmt(v) {
  if (!v) return "-";
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? v : d.toLocaleString("zh-CN");
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
                             { expires_days: days.value });
    createdUrl.value =
      `${location.origin}${location.pathname}#/share/${r.token}`;
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
</style>
