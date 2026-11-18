<template>
  <div class="page">
    <div class="toolbar">
      <div class="spacer" />
      <el-tag size="small" :type="totpEnabled ? 'success' : 'info'">
        {{ totpEnabled ? t("sec.totpEnabled") : t("sec.totpDisabled") }}
      </el-tag>
    </div>

    <el-card shadow="never" class="card">
      <template #header><span>{{ t("sec.changePassword") }}</span></template>
      <el-form label-width="100px" style="max-width: 520px">
        <el-form-item :label="t('sec.currentPassword')">
          <el-input v-model="oldPassword" type="password" show-password />
        </el-form-item>
        <el-form-item :label="t('sec.newPassword')">
          <el-input v-model="newPassword" type="password" show-password />
        </el-form-item>
        <el-form-item :label="t('sec.confirmPassword')">
          <el-input v-model="confirm" type="password" show-password />
        </el-form-item>
        <el-button type="primary" :loading="saving" @click="changePassword">
          {{ t("sec.updatePassword") }}
        </el-button>
      </el-form>
    </el-card>

    <el-card shadow="never" class="card">
      <template #header><span>{{ t("sec.totpTitle") }}</span></template>
      <div v-if="!totpEnabled">
        <p class="hint">
          {{ t("sec.totpHint") }}
        </p>
        <el-button v-if="!secret" size="small" @click="setup">
          {{ t("sec.generateSecret") }}
        </el-button>
        <div v-if="secret" class="setup">
          <el-tag effect="plain" class="mono">{{ secret }}</el-tag>
          <el-button link @click="copy(uri)">{{ t("sec.copyUri") }}</el-button>
          <el-input v-model="code" size="small"
                    :placeholder="t('sec.codePlaceholder')"
                    style="width: 220px" />
          <el-button type="primary" size="small" @click="enable">
            {{ t("sec.enable") }}
          </el-button>
        </div>
      </div>
      <div v-else class="setup">
        <el-input v-model="code" size="small"
                  :placeholder="t('sec.codePlaceholder')"
                  style="width: 220px" />
        <el-button type="danger" size="small" @click="disable">
          {{ t("sec.disableTotp") }}
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { api, errMsg, setToken } from "../api";
import { t } from "../i18n";

const oldPassword = ref("");
const newPassword = ref("");
const confirm = ref("");
const saving = ref(false);
const totpEnabled = ref(false);
const secret = ref("");
const uri = ref("");
const code = ref("");

async function load() {
  try {
    const me = await api.get("/auth/me");
    totpEnabled.value = Boolean(me.totp_enabled);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function changePassword() {
  if (!oldPassword.value || !newPassword.value) {
    ElMessage.error(t("sec.fillPassword"));
    return;
  }
  if (newPassword.value !== confirm.value) {
    ElMessage.error(t("sec.mismatch"));
    return;
  }
  saving.value = true;
  try {
    const r = await api.post("/auth/change-password", {
      old_password: oldPassword.value, new_password: newPassword.value,
    });
    if (r.token) setToken(r.token);
    oldPassword.value = newPassword.value = confirm.value = "";
    ElMessage.success(t("sec.passwordUpdated"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

async function setup() {
  try {
    const r = await api.post("/auth/totp/setup");
    secret.value = r.secret;
    uri.value = r.uri;
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function enable() {
  try {
    await api.post("/auth/totp/enable", { code: code.value });
    totpEnabled.value = true;
    code.value = "";
    ElMessage.success(t("sec.totpEnabledMsg"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function disable() {
  try {
    await api.post("/auth/totp/disable", { code: code.value });
    totpEnabled.value = false;
    secret.value = uri.value = code.value = "";
    ElMessage.success(t("sec.totpDisabledMsg"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success(t("sec.copied"));
  } catch (e) {
    ElMessage.error(t("sec.copyFailed"));
  }
}

onMounted(load);
</script>

<style scoped>
.toolbar { display: flex; align-items: center; gap: 10px;
           margin-bottom: 12px; }
.title { font-size: 16px; font-weight: 700; color: #0f172a; }
.spacer { flex: 1; }
.card { margin-bottom: 14px; }
.hint { color: #6b7280; font-size: 12px; }
.setup { display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
         margin-top: 10px; }
.mono { font-family: ui-monospace, monospace; }
</style>
