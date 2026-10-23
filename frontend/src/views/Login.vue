<template>
  <div class="login-page">
    <section class="intro">
      <div class="intro-brand">
        <span class="mark">OD</span>
        <span>OpenDataFusion</span>
      </div>
      <h1>OpenData<br>Fusion.</h1>
      <p class="statement">
        从数据源到管道、模型、接口和应用，<br>
        一个工作区完成数据流动的全过程。
      </p>
      <div class="facts">
        <div class="fact">
          <span class="fact-key"></span>
          <span>数据源 → 管道 → 模型 → 接口</span>
        </div>
        <div class="fact">
          <span class="fact-key"></span>
          <span>治理、审批与审计在同一条链路上</span>
        </div>
        <div class="fact">
          <span class="fact-key"></span>
          <span>外部 AI 通过 MCP 接入同一套能力</span>
        </div>
      </div>
      <div class="intro-foot">
        <span>API-first</span><span>Open source</span><span>v1.0</span>
      </div>
    </section>

    <section class="panel">
      <div class="panel-inner">
        <header class="panel-head">
          <h2>登录工作区</h2>
          <p>使用管理员或项目成员账号进入控制台。</p>
        </header>

        <el-form label-position="top" @submit.prevent="submit">
          <el-form-item label="用户名">
            <el-input v-model="username" size="large" placeholder="admin"
                      autocomplete="username" :prefix-icon="User" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="password" size="large" type="password"
                      show-password autocomplete="current-password"
                      placeholder="输入密码" :prefix-icon="Lock"
                      @keyup.enter="submit" />
          </el-form-item>
          <el-form-item label="动态验证码（启用 2FA 时）">
            <el-input v-model="otp" size="large" placeholder="可选"
                      autocomplete="one-time-code" :prefix-icon="Key" />
          </el-form-item>
          <el-form-item label="项目 ID">
            <el-input-number v-model="projectId" :min="1" size="large"
                             controls-position="right" />
          </el-form-item>
          <el-button type="primary" size="large" class="submit"
                     :loading="loading" @click="submit">登录</el-button>
          <el-button v-if="oidcEnabled" size="large" class="oidc"
                     @click="oidcLogin">使用企业账号登录 (OIDC)</el-button>
        </el-form>

        <el-alert v-if="error" :title="error" type="error" :closable="false"
                  show-icon class="error" />

        <div class="panel-foot">
          <span>遇到权限问题请联系工作区管理员</span>
          <span class="mono">MCP 18082</span>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { Lock, User, Key } from "@element-plus/icons-vue";
import { api, errMsg } from "../api";

const username = ref("admin");
const password = ref("");
const projectId = ref(1);
const loading = ref(false);
const error = ref("");
const otp = ref("");
const oidcEnabled = ref(false);
const router = useRouter();

async function submit() {
  if (!username.value || !password.value) {
    error.value = "请输入用户名和密码";
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    await api.login(username.value, password.value, projectId.value,
                    otp.value);
    router.push("/dashboard");
  } catch (e) {
    error.value = errMsg(e);
  } finally {
    loading.value = false;
  }
}

function oidcLogin() {
  window.location.href = "/api/v1/auth/oidc/start?project_id=" + projectId.value;
}

onMounted(async () => {
  try {
    const r = await fetch("/api/v1/auth/oidc/enabled");
    oidcEnabled.value = Boolean((await r.json()).enabled);
  } catch (e) {
    oidcEnabled.value = false;
  }
});
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(420px, 0.65fr);
  background: var(--odf-paper);
  color: var(--odf-ink);
}

.intro {
  position: relative;
  display: flex;
  flex-direction: column;
  padding: clamp(34px, 6vw, 76px) clamp(34px, 6vw, 88px) 30px;
  border-right: 1px solid var(--odf-rule);
  overflow: hidden;
}

.intro::before {
  content: "";
  position: absolute;
  left: clamp(14px, 2.6vw, 40px);
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--odf-accent);
  opacity: 0.9;
}

.intro-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: -0.01em;
  margin-bottom: clamp(56px, 10vh, 108px);
}

.mark {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  background: var(--odf-ink);
  color: #fff;
  font-size: 11px;
  font-weight: 650;
  border-bottom: 2px solid var(--odf-accent);
}

h1 {
  margin: 0;
  font-size: clamp(64px, 9vw, 132px);
  line-height: 0.84;
  letter-spacing: -0.07em;
  font-weight: 700;
  max-width: 8ch;
}

.statement {
  margin: 30px 0 0;
  font-size: 14px;
  line-height: 1.75;
  color: #4b5563;
  max-width: 36ch;
}

.facts {
  margin-top: auto;
  border-top: 1px solid var(--odf-ink);
  max-width: 520px;
}

.fact {
  display: grid;
  grid-template-columns: 34px 1fr;
  gap: 14px;
  padding: 11px 0;
  border-bottom: 1px solid var(--odf-rule);
  font-size: 12px;
  color: #374151;
}

.fact-key {
  width: 6px;
  height: 6px;
  margin-top: 6px;
  background: var(--odf-accent);
}

.intro-foot {
  display: flex;
  gap: 18px;
  margin-top: 18px;
  color: var(--odf-muted);
  font-family: var(--odf-mono);
  font-size: 9px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.panel {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px clamp(26px, 5vw, 64px);
  background: #fff;
}

.panel-inner {
  width: 100%;
  max-width: 352px;
}

.panel-head {
  border-bottom: 1px solid var(--odf-ink);
  padding-bottom: 14px;
  margin-bottom: 22px;
}

.panel-head h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 650;
  letter-spacing: -0.035em;
}

.panel-head p {
  margin: 7px 0 0;
  color: var(--odf-muted);
  font-size: 11px;
  line-height: 1.5;
}

.submit {
  width: 100%;
  margin-top: 4px;
}

.oidc {
  width: 100%;
  margin: 8px 0 0 !important;
}

.error {
  margin-top: 14px;
}

.panel-foot {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  border-top: 1px solid var(--odf-rule);
  margin-top: 24px;
  padding-top: 12px;
  color: var(--odf-muted);
  font-size: 9px;
}

.panel-foot .mono {
  font-size: 9px;
}

@media (max-width: 900px) {
  .login-page {
    grid-template-columns: 1fr;
  }

  .intro {
    border-right: 0;
    border-bottom: 1px solid var(--odf-rule);
    padding: 28px 24px 24px;
  }

  .intro::before {
    left: 12px;
    width: 2px;
  }

  .intro-brand {
    margin-bottom: 34px;
  }

  h1 {
    font-size: clamp(52px, 16vw, 86px);
  }

  .statement {
    margin-top: 18px;
    font-size: 12px;
  }

  .facts {
    margin-top: 28px;
  }

  .intro-foot {
    margin-top: 14px;
  }

  .panel {
    padding: 28px 24px 40px;
    align-items: flex-start;
  }
}
</style>
