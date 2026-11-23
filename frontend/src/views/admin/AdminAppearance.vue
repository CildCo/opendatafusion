<template>
  <div class="admin-page">
    <el-form label-width="140px" class="form">
      <el-card shadow="never">
        <template #header><b>{{ t("adm.brand") }}</b></template>
        <el-form-item :label="t('adm.brandName')">
          <el-input v-model="brand.name" maxlength="64" />
        </el-form-item>
        <el-form-item :label="t('adm.brandColor')">
          <el-color-picker v-model="brand.color" />
          <span class="hint">{{ brand.color }}</span>
        </el-form-item>
        <el-form-item :label="t('adm.welcomeTitle')">
          <el-input v-model="brand.welcome_title" maxlength="128" />
        </el-form-item>
        <el-form-item :label="t('adm.welcomeText')">
          <el-input v-model="brand.welcome_text" type="textarea" :rows="3"
                    maxlength="1000" show-word-limit />
        </el-form-item>
        <el-form-item :label="t('adm.defaultLocale')">
          <el-select v-model="brand.default_locale" style="width: 180px">
            <el-option value="zh" label="简体中文" />
            <el-option value="en" label="English" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('adm.announcement')">
          <el-input v-model="brand.announcement" type="textarea" :rows="2"
                    maxlength="500" show-word-limit />
        </el-form-item>
      </el-card>

      <el-card shadow="never">
        <template #header><b>{{ t("adm.features") }}</b></template>
        <el-form-item v-for="flag in flags" :key="flag.key"
                      :label="t(flag.label)">
          <el-switch v-model="features[flag.key]" />
        </el-form-item>
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

const brand = reactive({
  name: "OpenDataFusion", color: "#1d4ed8", welcome_title: "",
  welcome_text: "", default_locale: "zh", announcement: "",
});
const features = reactive({
  workbench: true, cdc: true, tools: true, apps: true, dashboards: true,
});
const flags = [
  { key: "workbench", label: "adm.flagWorkbench" },
  { key: "cdc", label: "adm.flagCdc" },
  { key: "tools", label: "adm.flagTools" },
  { key: "apps", label: "adm.flagApps" },
  { key: "dashboards", label: "adm.flagDashboards" },
];
const saving = ref(false);

onMounted(async () => {
  try {
    const doc = await api.get("/platform/settings");
    Object.assign(brand, doc.brand || {});
    Object.assign(features, doc.features || {});
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
});

async function save() {
  saving.value = true;
  try {
    await api.put("/platform/settings", { brand, features });
    ElMessage.success(t("adm.saved"));
  } catch (e) {
    ElMessage.error(e && e.message ? errMsg(e) : t("adm.saveFailed"));
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.form :deep(.el-card) { margin-bottom: 14px; border-radius: 10px; }
.hint { margin-left: 10px; color: #94a3b8; font-size: 12px; }
.actions { display: flex; justify-content: flex-end; }
</style>
