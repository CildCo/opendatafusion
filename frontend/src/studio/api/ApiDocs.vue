<template>
  <el-drawer :model-value="modelValue" title="接口文档" size="620px"
             @update:model-value="$emit('update:modelValue', $event)">
    <div v-if="docs">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="路径">
          <span class="mono">POST {{ docs.path }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="鉴权">
          AK/SK + projectKey
        </el-descriptions-item>
      </el-descriptions>
      <h4>参数</h4>
      <el-table :data="docs.params" size="small">
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="type" label="类型" width="90" />
        <el-table-column prop="required" label="必填" width="70">
          <template #default="{ row }">{{ row.required ? "是" : "否" }}</template>
        </el-table-column>
        <el-table-column prop="example" label="示例" />
      </el-table>
      <h4>curl</h4>
      <pre class="code">{{ docs.curl }}</pre>
      <h4>Python</h4>
      <pre class="code">{{ docs.python }}</pre>
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { api, errMsg } from "../../api";

const props = defineProps({
  modelValue: Boolean,
  assetId: { type: Number, required: true },
});
defineEmits(["update:modelValue"]);
const docs = ref(null);

watch(() => props.modelValue, async (open) => {
  if (!open) return;
  try {
    docs.value = await api.get(`/apis/${props.assetId}/docs`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
});
</script>

<style scoped>
.mono { font-family: ui-monospace, monospace; }
.code { background: #0f172a; color: #e2e8f0; padding: 10px;
        border-radius: 6px; font-size: 12px; white-space: pre-wrap; }
h4 { margin: 14px 0 6px; }
</style>
