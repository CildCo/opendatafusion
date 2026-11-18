<template>
  <el-drawer :model-value="modelValue" :title="t('apic.docsTitle')" size="620px"
             @update:model-value="$emit('update:modelValue', $event)">
    <div v-if="docs">
      <el-descriptions :column="1" border>
        <el-descriptions-item :label="t('apic.path')">
          <span class="mono">POST {{ docs.path }}</span>
        </el-descriptions-item>
        <el-descriptions-item :label="t('apic.auth')">
          AK/SK + projectKey
        </el-descriptions-item>
      </el-descriptions>
      <h4>{{ t("apic.params") }}</h4>
      <el-table :data="docs.params" size="small">
        <el-table-column prop="name" :label="t('apic.name')" />
        <el-table-column prop="type" :label="t('apic.type')" width="90" />
        <el-table-column prop="required" :label="t('apic.required')" width="70">
          <template #default="{ row }">{{ row.required ? t("apic.yes") : t("apic.no") }}</template>
        </el-table-column>
        <el-table-column prop="example" :label="t('apic.example')" />
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
import { t } from "../../i18n";

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
