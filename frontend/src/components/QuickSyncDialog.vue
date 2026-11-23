<template>
  <el-dialog :model-value="modelValue" :title="t('quick.title')" width="620px"
             @update:model-value="$emit('update:modelValue', $event)">
    <p class="hint">{{ t("quick.intro") }}</p>
    <el-form label-width="110px">
      <el-form-item :label="t('quick.name')" required>
        <el-input v-model="name" :placeholder="t('quick.namePlaceholder')" />
      </el-form-item>
      <el-form-item :label="t('quick.source')" required>
        <el-select v-model="sourceId" style="width: 100%"
                   @change="loadSourceTables">
          <el-option v-for="d in sourceOptions" :key="d.id" :value="d.id"
                     :label="`${d.name} (${kindLabel(d.kind)})`" />
        </el-select>
      </el-form-item>
      <el-form-item :label="t('quick.sourceTable')" required>
        <el-select v-model="sourceTable" filterable style="width: 100%"
                   @change="pickPk">
          <el-option v-for="x in sourceTables" :key="x.schema + '.' + x.table"
                     :value="x.table" :label="`${x.schema}.${x.table}`" />
        </el-select>
      </el-form-item>
      <el-form-item :label="t('quick.target')" required>
        <el-select v-model="targetId" style="width: 100%"
                   @change="loadTargetTables">
          <el-option v-for="d in targetOptions" :key="d.id" :value="d.id"
                     :label="`${d.name} (${kindLabel(d.kind)})`" />
        </el-select>
      </el-form-item>
      <el-form-item :label="t('quick.targetTable')" required>
        <el-select v-model="targetTable" filterable allow-create
                   style="width: 100%">
          <el-option v-for="x in targetTables" :key="x.schema + '.' + x.table"
                     :value="x.table" :label="`${x.schema}.${x.table}`" />
        </el-select>
      </el-form-item>
      <el-form-item :label="t('quick.mode')">
        <el-select v-model="mode" style="width: 100%">
          <el-option value="upsert" label="upsert" />
          <el-option value="append" label="append" />
        </el-select>
      </el-form-item>
      <el-form-item :label="t('quick.pk')">
        <el-input v-model="pk" :placeholder="t('quick.pkPlaceholder')" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">
        {{ t("quick.cancel") }}
      </el-button>
      <el-button type="primary" :loading="saving" :disabled="!valid"
                 @click="create">
        {{ t("quick.create") }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { useRouter } from "vue-router";
import { api, errMsg } from "../api";
import { t } from "../i18n";

const props = defineProps({ modelValue: Boolean });
const emit = defineEmits(["update:modelValue", "created"]);
const router = useRouter();
const datasources = ref([]);
const sourceId = ref(null);
const targetId = ref(null);
const sourceTable = ref("");
const targetTable = ref("");
const sourceTables = ref([]);
const targetTables = ref([]);
const name = ref("");
const mode = ref("upsert");
const pk = ref("id");
const saving = ref(false);

const sourceOptions = computed(() => datasources.value.filter(
  (d) => d.capabilities && d.capabilities.metadata && d.capabilities.source));
const targetOptions = computed(() => datasources.value.filter(
  (d) => d.capabilities && d.capabilities.metadata && d.capabilities.sink));
const valid = computed(() => name.value.trim() && sourceId.value &&
  targetId.value && sourceTable.value && targetTable.value);

function kindLabel(kind) { return kind; }

async function load() {
  datasources.value = await api.get("/datasources");
  if (!sourceId.value && sourceOptions.value.length) {
    sourceId.value = sourceOptions.value[0].id;
    await loadSourceTables();
  }
  if (!targetId.value && targetOptions.value.length) {
    targetId.value = targetOptions.value[0].id;
    await loadTargetTables();
  }
}

async function loadSourceTables() {
  sourceTable.value = "";
  sourceTables.value = sourceId.value
    ? await api.get(`/datasources/${sourceId.value}/tables`) : [];
}

async function loadTargetTables() {
  targetTable.value = "";
  targetTables.value = targetId.value
    ? await api.get(`/datasources/${targetId.value}/tables`) : [];
}

function pickPk() {
  const found = sourceTables.value.find((x) => x.table === sourceTable.value);
  const first = found && (found.columns || [])[0];
  if (first) pk.value = first.name;
}

async function create() {
  if (!valid.value) return;
  saving.value = true;
  try {
    const content = {
      nodes: [
        { id: "source_1", type: "source", position: { x: 80, y: 120 },
          data: { kind: "source", name: t("quick.source"),
                  config: { datasource_id: sourceId.value,
                            table: sourceTable.value, pk: pk.value } } },
        { id: "sink_1", type: "sink", position: { x: 420, y: 120 },
          data: { kind: "sink", name: t("quick.target"),
                  config: { datasource_id: targetId.value,
                            table: targetTable.value, mode: mode.value,
                            pk: [pk.value] } } },
      ],
      edges: [{ id: "e1", source: "source_1", target: "sink_1" }],
      settings: { batch: 1000 },
    };
    const asset = await api.post("/pipelines", {
      name: name.value.trim(), content,
    });
    ElMessage.success(t("quick.created"));
    emit("update:modelValue", false);
    emit("created", asset);
    router.push(`/pipelines/${asset.id}`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

watch(() => props.modelValue, (open) => {
  if (open) load();
});
</script>

<style scoped>
.hint { margin: 0 0 14px; color: #64748b; font-size: 12px; }
</style>
