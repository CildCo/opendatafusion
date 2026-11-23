<template>
  <div class="rule-builder">
    <el-form-item :label="t('rule.kind')">
      <el-select :model-value="modelValue.kind" style="width: 100%"
                 @change="setKind">
        <el-option value="mute" :label="t('rule.kindMute')" />
        <el-option value="custom" :label="t('rule.kindCustom')" />
      </el-select>
    </el-form-item>

    <template v-if="modelValue.kind === 'mute'">
      <el-form-item :label="t('rule.titleContains')">
        <el-input :model-value="modelValue.config.title_contains || ''"
                  :placeholder="t('rule.titlePlaceholder')"
                  @update:model-value="(v) => setField('title_contains', v)" />
      </el-form-item>
      <el-form-item :label="t('rule.severity')">
        <el-select :model-value="modelValue.config.severity || ''"
                   clearable style="width: 100%"
                   @update:model-value="(v) => setField('severity', v)">
          <el-option value="" :label="t('rule.any')" />
          <el-option value="warning" label="warning" />
          <el-option value="error" label="error" />
          <el-option value="critical" label="critical" />
        </el-select>
      </el-form-item>
      <p class="rule-hint">{{ t("rule.muteHint") }}</p>
    </template>

    <template v-else>
      <el-form-item :label="t('rule.customConfig')">
        <el-input :model-value="customText" type="textarea" :rows="5"
                  @update:model-value="setCustom" />
      </el-form-item>
      <el-alert v-if="jsonError" :title="jsonError" type="error"
                :closable="false" />
    </template>

    <details class="rule-preview">
      <summary>{{ t("rule.preview") }}</summary>
      <pre>{{ preview }}</pre>
    </details>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import { t } from "../i18n";

const props = defineProps({
  modelValue: { type: Object, required: true },
});
const emit = defineEmits(["update:modelValue"]);

const customText = ref(JSON.stringify(props.modelValue.config || {}, null, 2));
const jsonError = ref("");

const preview = computed(() => JSON.stringify({
  kind: props.modelValue.kind,
  config: props.modelValue.config || {},
}, null, 2));

function setKind(kind) {
  emit("update:modelValue", {
    kind,
    config: kind === "mute" ? { ...props.modelValue.config } : {},
  });
  if (kind === "custom") {
    customText.value = JSON.stringify(props.modelValue.config || {}, null, 2);
  }
}

function setField(field, value) {
  const config = { ...props.modelValue.config };
  if (value === "" || value === null || value === undefined) delete config[field];
  else config[field] = value;
  emit("update:modelValue", { kind: "mute", config });
}

function setCustom(text) {
  customText.value = text;
  try {
    const parsed = text.trim() ? JSON.parse(text) : {};
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
      jsonError.value = t("rule.invalidJson");
      return;
    }
    jsonError.value = "";
    emit("update:modelValue", { kind: "custom", config: parsed });
  } catch {
    jsonError.value = t("rule.invalidJson");
  }
}
</script>

<style scoped>
.rule-hint { color: #64748b; font-size: 12px; margin: 0 0 12px 110px; }
.rule-preview { margin-top: 4px; }
.rule-preview summary {
  cursor: pointer;
  color: #94a3b8;
  font-size: 12px;
}
.rule-preview pre {
  background: #0f172a;
  color: #e2e8f0;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 11px;
  overflow: auto;
}
</style>
