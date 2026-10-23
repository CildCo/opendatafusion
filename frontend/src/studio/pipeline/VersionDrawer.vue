<template>
  <el-drawer :model-value="modelValue" title="版本" size="520px"
             @update:model-value="$emit('update:modelValue', $event)">
    <el-table :data="versions" size="small">
      <el-table-column prop="version" label="版本" width="80" />
      <el-table-column prop="status" label="状态" width="110" />
      <el-table-column prop="created_by" label="创建人" width="120" />
      <el-table-column prop="created_at" label="时间" />
      <el-table-column label="操作" width="110">
        <template #default="{ row }">
          <el-button link
                     :disabled="row.current || row.status === 'draft'"
                     @click="rollback(row)">回滚</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!versions.length" description="还没有版本" :image-size="70" />
  </el-drawer>
</template>

<script setup>
import { ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../../api";

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
    await ElMessageBox.confirm(`回滚到版本 ${row.version}？`, "回滚确认",
                               { type: "warning" });
    await api.applyChange("rollback_pipeline", props.assetId,
                          { version: row.version });
    await load();
    emit("changed");
    ElMessage.success("已回滚");
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}
</script>
