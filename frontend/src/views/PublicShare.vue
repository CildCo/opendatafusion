<template>
  <div class="public">
    <header class="head">
      <div class="brand">OD</div>
      <div class="name">{{ view?.name || "分享内容" }}</div>
      <el-tag size="small" type="info">只读分享</el-tag>
      <div class="spacer" />
      <el-button v-if="view" size="small" :loading="loading"
                 @click="refresh">刷新</el-button>
    </header>

    <div v-if="error" class="error">
      <el-result icon="warning" title="链接不可用"
                 :sub-title="error" />
    </div>

    <main v-else-if="view" class="body" v-loading="loading">
      <el-alert v-if="dataError" :title="dataError" type="warning"
                :closable="false" style="margin-bottom: 10px" />
      <template v-if="view.kind === 'app'">
        <div v-if="pages.length > 1" class="tabs">
          <el-radio-group v-model="currentId" size="small">
            <el-radio-button v-for="p in pages" :key="p.id" :value="p.id">
              {{ p.title || p.id }}
            </el-radio-button>
          </el-radio-group>
        </div>
        <AppRuntime v-if="currentPage" :key="currentPage.id"
                    :page="currentPage" :data="data" :params="paramValues"
                    @update:params="setParams" @refresh="refresh" />
      </template>
      <DashboardRuntime v-else-if="view.kind === 'dashboard'"
                        :content="view.content" :data="data"
                        :params="paramValues"
                        @update:params="setParams" @refresh="refresh" />
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import AppRuntime from "../studio/app/AppRuntime.vue";
import DashboardRuntime from "../studio/dashboard/DashboardRuntime.vue";

const route = useRoute();
const token = computed(() => String(route.params.token || ""));
const view = ref(null);
const error = ref("");
const dataError = ref("");
const loading = ref(false);
const data = ref({});
const currentId = ref("");
const paramValues = ref({});

const pages = computed(() => view.value?.kind === "app"
  ? view.value.content?.pages || [] : []);
const currentPage = computed(() =>
  pages.value.find((p) => p.id === currentId.value) || pages.value[0]);

async function call(path, method = "GET", body = null) {
  const r = await fetch("/api/v1" + path, {
    method,
    headers: { "Content-Type": "application/json",
               "X-Share-Token": token.value },
    body: body === null ? undefined : JSON.stringify(body),
  });
  let payload = null;
  try {
    payload = await r.json();
  } catch (e) {
    payload = null;
  }
  if (!r.ok) {
    throw new Error(payload?.detail || `HTTP ${r.status}`);
  }
  return payload;
}

function resetParams() {
  const values = {};
  if (view.value?.kind === "app") {
    for (const p of currentPage.value?.params || []) {
      if (p.name) values[p.name] = p.default ?? "";
    }
  } else {
    for (const p of view.value?.content?.params || []) {
      if (p.name) values[p.name] = p.default ?? "";
    }
  }
  paramValues.value = values;
}

function setParams(p) {
  paramValues.value = { ...p };
}

async function load() {
  if (!token.value) {
    error.value = "链接缺少令牌";
    return;
  }
  loading.value = true;
  dataError.value = "";
  try {
    view.value = await call("/public/share");
    if (view.value.kind === "app") {
      const content = view.value.content || {};
      currentId.value = content.start_page || pages.value[0]?.id || "";
    }
    resetParams();
    if (requiredMissing()) {
      dataError.value = "请填写必填参数后查询";
      loading.value = false;
      return;
    }
    await refresh();
  } catch (e) {
    error.value = e.message || "链接无效或已过期";
  } finally {
    loading.value = false;
  }
}

function defs() {
  return view.value?.kind === "app"
    ? currentPage.value?.params || []
    : view.value?.content?.params || [];
}

function requiredMissing() {
  return defs().some((p) => p.required &&
    (paramValues.value[p.name] === "" ||
     paramValues.value[p.name] === null ||
     paramValues.value[p.name] === undefined));
}

async function refresh() {
  if (!view.value) return;
  if (requiredMissing()) {
    dataError.value = "请填写必填参数后查询";
    return;
  }
  loading.value = true;
  dataError.value = "";
  try {
    if (view.value.kind === "app") {
      const r = await call("/public/share/data", "POST", {
        page_id: currentPage.value?.id,
        params: paramValues.value,
        limit: 100,
      });
      data.value = r.components || {};
    } else {
      const r = await call("/public/share/data", "POST", {
        params: paramValues.value,
        limit: 100,
      });
      data.value = r.widgets || {};
    }
  } catch (e) {
    dataError.value = e.message || "数据加载失败";
  } finally {
    loading.value = false;
  }
}

watch(currentId, () => {
  resetParams();
  data.value = {};
  refresh();
});
watch(() => route.params.token, () => {
  view.value = null;
  error.value = "";
  dataError.value = "";
  data.value = {};
  load();
});

onMounted(load);
</script>

<style scoped>
.public { min-height: 100vh; background: var(--odf-paper); color: var(--odf-ink); }
.head { height: 56px; display: flex; align-items: center; gap: 10px;
        padding: 0 20px; background: #fff; border-bottom: 1px solid var(--odf-rule); }
.brand { width: 30px; height: 30px; background: var(--odf-ink);
         color: #fff; display: grid; place-items: center; font-size: 11px;
         font-weight: 650; border-bottom: 2px solid var(--odf-accent); }
.name { font-size: 15px; font-weight: 600; color: var(--odf-ink); }
.spacer { flex: 1; }
.body { max-width: 1200px; margin: 0 auto; padding: 16px; }
.tabs { margin-bottom: 10px; }
.error { display: grid; place-items: center; min-height: 60vh; }
</style>
