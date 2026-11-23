<template>
  <el-drawer :model-value="modelValue" :title="t('gov.assetTitle')"
             size="560px"
             @update:model-value="$emit('update:modelValue', $event)"
             @open="load">
    <div v-loading="loading">
      <el-form label-width="130px" size="small">
        <el-form-item :label="t('gov.domain')">
          <el-select v-model="form.domain_id" clearable
                     style="width: 100%">
            <el-option v-for="d in domains" :key="d.id" :value="d.id"
                       :label="d.name" />
          </el-select>
        </el-form-item>
        <template v-if="mode === 'asset'">
          <el-form-item :label="t('gov.contractOwner')">
            <el-input v-model="form.owner" />
          </el-form-item>
          <el-form-item :label="t('gov.sla')">
            <el-input v-model="form.sla" placeholder="每日 08:00 前" />
          </el-form-item>
          <el-form-item :label="t('gov.schema')">
            <el-input v-model="form.schemaText"
                      placeholder="id, order_no, amount" />
          </el-form-item>
          <el-form-item :label="t('gov.quality')">
            <el-input v-model="form.qualityText" type="textarea" :rows="4"
                      placeholder='[{"kind":"not_null","column":"id"}]' />
          </el-form-item>
          <el-form-item :label="t('gov.notes')">
            <el-input v-model="form.notes" type="textarea" :rows="3" />
          </el-form-item>
        </template>
        <el-button type="primary" :loading="saving" @click="save">
          {{ t("gov.saveGovernance") }}
        </el-button>
      </el-form>

      <template v-if="mode === 'asset' && usage">
        <el-divider content-position="left">{{ t("gov.usage") }}</el-divider>
        <div class="usage-tiles">
          <stat-tile :label="t('gov.references')" :value="usage.reference_count" />
          <stat-tile :label="t('gov.runs')" :value="usage.runs" />
          <stat-tile :label="t('gov.downstream')" :value="usage.downstream" />
          <stat-tile v-if="usage.api_calls_30d !== undefined"
                     :label="t('gov.apiCalls')" :value="usage.api_calls_30d" />
        </div>
        <el-table v-if="usage.references.length" :data="usage.references"
                  size="small" style="margin-top: 12px">
          <el-table-column prop="type" :label="t('model.type')" width="110" />
          <el-table-column prop="name" :label="t('gov.name')" />
        </el-table>
      </template>
    </div>
  </el-drawer>
</template>

<script setup>
import { reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { api, errMsg } from "../api";
import { t } from "../i18n";
import StatTile from "./StatTile.vue";

const props = defineProps({
  modelValue: Boolean,
  assetId: { type: Number, default: 0 },
  mode: { type: String, default: "asset" },
});
defineEmits(["update:modelValue"]);

const loading = ref(false);
const saving = ref(false);
const domains = ref([]);
const usage = ref(null);
const form = reactive({
  domain_id: null, owner: "", sla: "", notes: "",
  schemaText: "", qualityText: "[]",
});

async function load() {
  if (!props.assetId) return;
  loading.value = true;
  usage.value = null;
  try {
    domains.value = (await api.get("/governance/domains")).items || [];
    if (props.mode === "table") {
      const out = await api.get(`/governance/tables/${props.assetId}`);
      form.domain_id = out.domain_id;
    } else {
      const out = await api.get(`/assets/${props.assetId}/governance`);
      const contract = out.contract || {};
      form.domain_id = out.domain_id;
      form.owner = contract.owner || "";
      form.sla = contract.sla || "";
      form.notes = contract.notes || "";
      form.schemaText = (contract.schema || []).join(", ");
      form.qualityText = JSON.stringify(contract.quality || [], null, 2);
      try {
        usage.value = await api.get(`/assets/${props.assetId}/usage`);
      } catch {
        usage.value = null;
      }
    }
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

async function save() {
  let quality = [];
  if (props.mode === "asset" && form.qualityText.trim()) {
    try {
      quality = JSON.parse(form.qualityText);
    } catch {
      ElMessage.error(t("gov.qualityInvalid"));
      return;
    }
    if (!Array.isArray(quality)) {
      ElMessage.error(t("gov.qualityInvalid"));
      return;
    }
  }
  saving.value = true;
  try {
    if (props.mode === "table") {
      await api.put(`/governance/tables/${props.assetId}`,
                    { domain_id: form.domain_id });
    } else {
      await api.put(`/assets/${props.assetId}/governance`, {
        domain_id: form.domain_id,
        contract: {
          owner: form.owner,
          sla: form.sla,
          notes: form.notes,
          schema: form.schemaText.split(",").map((x) => x.trim())
            .filter(Boolean),
          quality,
        },
      });
      usage.value = await api.get(`/assets/${props.assetId}/usage`);
    }
    ElMessage.success(t("gov.saved"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

watch(() => props.assetId, () => {
  if (props.modelValue) load();
});
</script>

<style scoped>
.usage-tiles {
  display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
</style>
