<template>
  <div class="oidc">
    <el-result icon="info" title="正在完成登录"
               sub-title="处理完成后将自动进入工作区" />
  </div>
</template>

<script setup>
import { onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, setProject, setToken } from "../api";

const route = useRoute();
const router = useRouter();

onMounted(async () => {
  const token = String(route.query.token || "");
  if (!token) {
    router.replace("/login");
    return;
  }
  setToken(token);
  try {
    const me = await api.get("/auth/me");
    localStorage.setItem("odf_role", me.role || "viewer");
    setProject(me.project_id);
    router.replace("/dashboard");
  } catch (e) {
    router.replace("/login");
  }
});
</script>

<style scoped>
.oidc { min-height: 100vh; display: grid; place-items: center;
        background: var(--odf-paper); }
</style>
