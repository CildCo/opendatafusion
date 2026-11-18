<template>
  <el-drawer :model-value="modelValue" :title="t('pver.title')" size="520px"
             @update:model-value="$emit('update:modelValue', $event)">
    <el-table :data="versions" size="small">
      <el-table-column prop="version" :label="t('pver.colVersion')" width="80" />
      <el-table-column prop="status" :label="t('pver.colStatus')" width="110" />
      <el-table-column prop="created_by" :label="t('pver.colCreatedBy')" width="120" />
      <el-table-column prop="created_at" :label="t('pver.colTime')" />
      <el-table-column :label="t('pver.colActions')" width="110">
        <template #default="{ row }">
          <el-button link
                     :disabled="row.current || row.status === 'draft'"
                     @click="rollback(row)">{{ t("pver.rollback") }}</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!versions.length" :description="t('pver.empty')" :image-size="70" />
  </el-drawer>
</template>

<script setup>
import { ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../../api";
import { t } from "../../i18n";

const props = defineProps({
  modelValue: Boolean,
  assetId: { type: Number, required: true },
});
const emit = defineEmits(["update:modelValue", "changed"]);
const versions = ref([]);

async function load() {
  try {
    versions.value = await api.get(`/pipelines/${props.assetId}/versions`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}
watch(() => props.modelValue, (v) => { if (v) load(); });

async function rollback(row) {
  try {
    await ElMessageBox.confirm(
      `${t("pver.rollbackToVersion")} ${row.version}${t("pver.question")}`,
      t("pver.confirmTitle"), { type: "warning" });
    await api.applyChange("rollback_pipeline", props.assetId,
                          { version: row.version });
    await load();
    emit("changed");
    ElMessage.success(t("pver.rolledBack"));
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}
</script>
