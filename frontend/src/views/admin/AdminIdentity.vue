<template>
  <div class="admin-page">
    <el-form label-width="140px" class="form">
      <el-card shadow="never">
        <template #header><b>{{ t("adm.loginPolicy") }}</b></template>
        <el-form-item :label="t('adm.sessionHours')">
          <el-input-number v-model="login.session_hours" :min="0" :max="720" />
          <span class="hint">{{ t("adm.sessionHint") }}</span>
        </el-form-item>
        <el-form-item :label="t('adm.mfaRoles')">
          <el-checkbox-group v-model="login.mfa_required_roles">
            <el-checkbox v-for="role in roles" :key="role" :value="role">
              {{ role }}
            </el-checkbox>
          </el-checkbox-group>
          <p class="warn">{{ t("adm.mfaHint") }}</p>
        </el-form-item>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-head">
            <b>OIDC</b>
            <el-switch v-model="identity.oidc.enabled" />
          </div>
        </template>
        <el-form-item label="Issuer">
          <el-input v-model="identity.oidc.issuer"
                    placeholder="https://idp.example" />
        </el-form-item>
        <el-form-item label="Client ID">
          <el-input v-model="identity.oidc.client_id" />
        </el-form-item>
        <el-form-item label="Client secret">
          <el-input v-model="identity.oidc.client_secret"
                    :placeholder="t('adm.secretPlaceholder')" show-password />
        </el-form-item>
        <el-form-item label="Redirect URI">
          <el-input v-model="identity.oidc.redirect_uri" />
        </el-form-item>
        <el-form-item label="Scopes">
          <el-input v-model="identity.oidc.scopes" />
        </el-form-item>
        <el-form-item :label="t('adm.autoProvision')">
          <el-switch v-model="identity.oidc.auto_provision" />
        </el-form-item>
        <el-form-item>
          <el-button :loading="testing" @click="testOidc">
            {{ t("adm.testOidc") }}
          </el-button>
        </el-form-item>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-head">
            <b>LDAP</b>
            <el-switch v-model="identity.ldap.enabled" />
          </div>
        </template>
        <el-form-item label="URL">
          <el-input v-model="identity.ldap.url"
                    placeholder="ldap://ldap.example:389" />
        </el-form-item>
        <el-form-item label="User DN template">
          <el-input v-model="identity.ldap.user_dn_template"
                    placeholder="uid={username},ou=people,dc=example" />
        </el-form-item>
        <el-form-item label="Bind DN">
          <el-input v-model="identity.ldap.bind_dn" />
        </el-form-item>
        <el-form-item label="Bind password">
          <el-input v-model="identity.ldap.bind_password"
                    :placeholder="t('adm.secretPlaceholder')" show-password />
        </el-form-item>
        <el-form-item :label="t('adm.autoProvision')">
          <el-switch v-model="identity.ldap.auto_provision" />
        </el-form-item>
        <el-form-item>
          <el-button :loading="testing" @click="testLdap">
            {{ t("adm.testLdap") }}
          </el-button>
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

const roles = ["viewer", "editor", "approver", "admin"];
const login = reactive({ session_hours: 0, mfa_required_roles: [] });
const identity = reactive({
  oidc: { enabled: false, issuer: "", client_id: "", client_secret: "",
          redirect_uri: "", scopes: "openid profile email",
          auto_provision: true },
  ldap: { enabled: false, url: "", user_dn_template: "", bind_dn: "",
          bind_password: "", auto_provision: true },
});
const saving = ref(false);
const testing = ref(false);

function assign(target, source) {
  for (const [key, value] of Object.entries(source || {})) {
    if (value && typeof value === "object" && !Array.isArray(value)) {
      target[key] = target[key] || {};
      assign(target[key], value);
    } else if (value !== undefined && value !== null) {
      target[key] = value;
    }
  }
}

onMounted(async () => {
  try {
    const doc = await api.get("/platform/settings");
    assign(login, doc.login);
    assign(identity, doc.identity);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
});

async function save() {
  saving.value = true;
  try {
    const doc = await api.put("/platform/settings", {
      login: { session_hours: login.session_hours,
               mfa_required_roles: login.mfa_required_roles },
      identity,
    });
    assign(identity, doc.identity);
    ElMessage.success(t("adm.saved"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

async function testOidc() {
  testing.value = true;
  try {
    const out = await api.post("/platform/identity/test-oidc",
                               { issuer: identity.oidc.issuer });
    ElMessage.success(out.authorization_endpoint || t("adm.testOk"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    testing.value = false;
  }
}

async function testLdap() {
  testing.value = true;
  try {
    await api.post("/platform/identity/test-ldap", {
      url: identity.ldap.url,
      bind_dn: identity.ldap.bind_dn,
      bind_password: identity.ldap.bind_password,
    });
    ElMessage.success(t("adm.testOk"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    testing.value = false;
  }
}
</script>

<style scoped>
.form :deep(.el-card) { margin-bottom: 14px; border-radius: 10px; }
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.hint { margin-left: 10px; color: #94a3b8; font-size: 12px; }
.warn { color: #b45309; font-size: 12px; margin: 6px 0 0; }
.actions { display: flex; justify-content: flex-end; }
</style>
