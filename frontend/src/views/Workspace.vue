<template>
  <div class="page">
    <page-header icon="workspace" :title="t('menu.workspace')"
                 :intro="t('settings.intro')" />
    <div class="toolbar">
      <el-tag size="small" type="info">{{ t("settings.scope") }}</el-tag>
      <div class="spacer" />
      <el-button size="small" @click="load" :loading="loading">{{ t("common.refresh") }}</el-button>
      <el-button type="primary" size="small" :loading="saving"
                 @click="save">{{ t("common.save") }}</el-button>
    </div>

    <el-card shadow="never">
      <el-form label-width="110px" style="max-width: 680px">
        <el-form-item :label="t('common.language')">
          <el-select :model-value="locale" style="width: 200px"
                     @change="changeLocale">
            <el-option value="zh" label="简体中文" />
            <el-option value="en" label="English" />
          </el-select>
        </el-form-item>
        <el-form-item :label="locale === 'en' ? 'Brand name' : '品牌名称'">
          <el-input v-model="form.brand_name" maxlength="64" />
        </el-form-item>
        <el-form-item :label="t('settings.themeColor')">
          <el-color-picker v-model="form.primary_color" />
          <span class="hint" style="margin-left: 10px">
            {{ form.primary_color }}
          </span>
        </el-form-item>
        <el-form-item :label="t('settings.welcomeTitle')">
          <el-input v-model="form.welcome_title" maxlength="128"
                    :placeholder="t('settings.welcomePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('settings.welcomeText')">
          <el-input v-model="form.welcome_text" type="textarea" :rows="3"
                    maxlength="1000" show-word-limit />
        </el-form-item>
        <el-form-item :label="t('settings.hiddenMenus')">
          <el-checkbox-group v-model="form.hidden_menus" class="menus">
            <el-checkbox v-for="m in menus" :key="m.path" :value="m.path">
              {{ t(m.key) }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item :label="t('settings.menuPermissions')">
          <el-checkbox-group v-model="allowedMenus" class="menus">
            <el-checkbox v-for="m in menus" :key="m.path" :value="m.path">
              {{ t(m.key) }}
            </el-checkbox>
          </el-checkbox-group>
          <p class="hint">
            {{ t("settings.menuHint") }}
          </p>
        </el-form-item>
      </el-form>
      <p class="hint">
        {{ t("settings.applyHint") }}
      </p>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { api, errMsg } from "../api";
import { locale, setLocale, t } from "../i18n";
import PageHeader from "../components/PageHeader.vue";
import { MENU_ITEMS } from "../menu";

function changeLocale(value) {
  setLocale(value);
}

const menus = MENU_ITEMS.map((m) => ({ path: m.path, key: m.key }));
const form = reactive({ brand_name: "Weft",
                        primary_color: "#1d4ed8", welcome_title: "",
                        welcome_text: "", hidden_menus: [] });
const loading = ref(false);
const saving = ref(false);
const allowedMenus = ref([]);

async function load() {
  loading.value = true;
  try {
    const data = await api.get("/portal");
    Object.assign(form, data);
    allowedMenus.value = data.allowed_menus || [];
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

async function save() {
  saving.value = true;
  try {
    const payload = { ...form,
                      allowed_menus: allowedMenus.value.length
                        ? allowedMenus.value : null };
    Object.assign(form, await api.put("/portal", payload));
    ElMessage.success(t("settings.saved"));
    setTimeout(() => window.location.reload(), 500);
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.toolbar { display: flex; gap: 10px; align-items: center;
           margin-bottom: 12px; }
.title { font-size: 16px; font-weight: 700; color: #0f172a; }
.spacer { flex: 1; }
.hint { color: #6b7280; font-size: 12px; }
.menus { display: grid; grid-template-columns: repeat(3, 1fr); gap: 2px; }
</style>
