<template>
  <el-dialog :model-value="modelValue" :title="t('tpl.title')" width="680px"
             @update:model-value="close" @open="load">
    <div class="tpl-grid">
      <button v-for="item in templates" :key="item.id" type="button"
              class="tpl-card" :class="{ active: selected === item.id }"
              @click="pick(item)">
        <b>{{ text(item, 'title') }}</b>
        <span>{{ text(item, 'description') }}</span>
      </button>
    </div>
    <el-form v-if="selected" label-width="120px" class="tpl-form">
      <el-form-item :label="t('tpl.name')">
        <el-input v-model="form.name" />
      </el-form-item>
      <el-form-item :label="mode === 'pipeline'
                      ? t('tpl.sourceDatasource') : t('tpl.datasource')">
        <el-select v-model="form.datasource_id" style="width: 100%">
          <el-option v-for="d in sourceOptions" :key="d.id" :value="d.id"
                     :label="`${d.name} (${d.kind})`" />
        </el-select>
      </el-form-item>
      <el-form-item :label="mode === 'pipeline'
                      ? t('tpl.sourceTable') : t('tpl.table')">
        <el-input v-model="form.table" placeholder="schema.table" />
      </el-form-item>
      <template v-if="mode === 'pipeline'">
        <el-form-item :label="t('tpl.targetDatasource')">
          <el-select v-model="form.target_datasource_id" style="width: 100%">
            <el-option v-for="d in sinkOptions" :key="d.id" :value="d.id"
                       :label="`${d.name} (${d.kind})`" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('tpl.targetTable')">
          <el-input v-model="form.target_table" placeholder="schema.table" />
        </el-form-item>
        <el-form-item label="PK">
          <el-input v-model="form.pk" placeholder="id" />
        </el-form-item>
      </template>
      <el-form-item v-else :label="t('tpl.schema')">
        <el-input v-model="form.schema_name"
                  :placeholder="t('tpl.schemaHint')" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="close(false)">{{ t("common.cancel") }}</el-button>
      <el-button type="primary" :loading="saving" :disabled="!selected"
                 @click="submit">
        {{ t("tpl.create") }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { api, errMsg } from "../api";
import { locale, t } from "../i18n";

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  mode: { type: String, default: "model" },
});
const emit = defineEmits(["update:modelValue", "created"]);
const templates = ref([]);
const datasources = ref([]);
const selected = ref("");
const saving = ref(false);
const form = reactive({
  name: "", datasource_id: null, table: "", schema_name: "",
  target_datasource_id: null, target_table: "", pk: "id",
});

const sourceOptions = computed(() => datasources.value.filter(
  (d) => d.capabilities && (props.mode === "pipeline"
    ? d.capabilities.source : d.capabilities.query)));
const sinkOptions = computed(() => datasources.value.filter(
  (d) => d.capabilities && d.capabilities.sink));

function text(item, key) {
  if (locale.value === "en") return item[`${key}_en`] || item[key];
  return item[key];
}

function close(value) {
  emit("update:modelValue", value);
}

async function load() {
  try {
    const [list, ds] = await Promise.all([
      api.get(`/templates?type=${props.mode}`),
      api.get("/datasources"),
    ]);
    templates.value = list.items || [];
    datasources.value = ds || [];
    if (templates.value.length && !selected.value) pick(templates.value[0]);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

function pick(item) {
  selected.value = item.id;
  form.name = text(item, "title");
}

async function submit() {
  if (!form.datasource_id || !form.table) {
    ElMessage.error(t("tpl.required"));
    return;
  }
  saving.value = true;
  try {
    const result = await api.post(`/templates/${selected.value}/apply`, {
      name: form.name,
      datasource_id: form.datasource_id,
      table: form.table,
      schema_name: form.schema_name,
      target_datasource_id: form.target_datasource_id,
      target_table: form.target_table,
      pk: form.pk,
    });
    ElMessage.success(t("tpl.created"));
    close(false);
    emit("created", result);
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.tpl-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px;
            margin-bottom: 14px; }
.tpl-card { text-align: left; border: 1px solid #e5e7eb; border-radius: 8px;
            background: #fff; padding: 10px 12px; cursor: pointer;
            display: flex; flex-direction: column; gap: 4px; }
.tpl-card b { font-size: 13px; color: #0f172a; }
.tpl-card span { font-size: 12px; color: #64748b; }
.tpl-card.active { border-color: #2563eb; box-shadow: 0 0 0 1px #2563eb33; }
</style>
