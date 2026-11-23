<template>
  <div class="admin-page">
    <el-form label-width="160px" class="form">
      <el-card shadow="never">
        <template #header><b>{{ t("adm.engines") }}</b></template>
        <el-form-item :label="t('adm.sparkImage')">
          <el-input v-model="engines.spark_image"
                    placeholder="odf/spark-iceberg:3.5.1" />
        </el-form-item>
        <el-form-item :label="t('adm.flinkGateway')">
          <el-input v-model="engines.flink_sql_gateway_url"
                    placeholder="http://flink-sql-gateway:8083" />
        </el-form-item>
        <el-form-item :label="t('adm.sqlWrite')">
          <el-select v-model="engines.sql_write_enabled" clearable
                     style="width: 220px">
            <el-option :value="true" :label="t('adm.enabled')" />
            <el-option :value="false" :label="t('adm.disabled')" />
          </el-select>
          <span class="hint">{{ t("adm.sqlWriteHint") }}</span>
        </el-form-item>
      </el-card>

      <el-card shadow="never">
        <template #header><b>{{ t("adm.cdcDefaults") }}</b></template>
        <el-form-item :label="t('adm.topicPrefix')">
          <el-input v-model="cdc.topic_prefix" placeholder="odf" />
        </el-form-item>
        <el-form-item :label="t('adm.kafkaBootstrap')">
          <el-input v-model="cdc.kafka_bootstrap" placeholder="kafka:9092" />
        </el-form-item>
        <p class="hint block">{{ t("adm.cdcHint") }}</p>
      </el-card>

      <el-card shadow="never">
        <template #header><b>{{ t("adm.currentProfile") }}</b></template>
        <el-descriptions :column="2" border>
          <el-descriptions-item :label="t('adm.lakehouse')">
            {{ profile.lakehouse_enabled ? t("adm.enabled") : t("adm.disabled") }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('adm.catalog')">
            {{ profile.lakehouse_catalog || "—" }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('adm.sparkImage')">
            {{ profile.spark?.image || "—" }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('adm.flinkGateway')">
            {{ profile.flink?.sql_gateway ? t("adm.enabled") : t("adm.disabled") }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <div class="actions">
        <el-button type="primary" :loading="saving" @click="save">
          {{ t("adm.save") }}
        </el-button>
      </div>
    </el-form>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { api, errMsg } from "../../api";
import { t } from "../../i18n";

const engines = reactive({ spark_image: "", flink_sql_gateway_url: "",
                           sql_write_enabled: null });
const cdc = reactive({ topic_prefix: "", kafka_bootstrap: "" });
const profile = ref({});
const saving = ref(false);

onMounted(async () => {
  try {
    const doc = await api.get("/platform/settings");
    Object.assign(engines, doc.engines || {});
    Object.assign(cdc, doc.cdc || {});
    profile.value = await api.get("/engine/profiles");
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
});

async function save() {
  saving.value = true;
  try {
    await api.put("/platform/settings", { engines, cdc });
    ElMessage.success(t("adm.saved"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.form :deep(.el-card) { margin-bottom: 14px; border-radius: 10px; }
.hint { margin-left: 10px; color: #94a3b8; font-size: 12px; }
.block { display: block; margin: 0 0 4px 160px; }
.actions { display: flex; justify-content: flex-end; }
</style>
