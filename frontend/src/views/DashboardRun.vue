<template>
  <div class="run-page">
    <div class="head">
      <el-button link @click="$router.push('/dashboards')":aria-label="t('common.back')">←</el-button>
      <span class="name">{{ name }}</span>
      <el-tag v-if="published" size="small" type="success">{{ t("dedit.published") }}</el-tag>
      <div class="spacer" />
      <el-button size="small" :loading="loading" @click="refresh">
        {{ t("dedit.refreshData") }}
      </el-button>
      <el-button size="small" :disabled="!published" @click="exportCsv">
        {{ t("dedit.exportCsv") }}
      </el-button>
      <el-button size="small" @click="$router.push(`/dashboards/${id}`)">
        {{ t("dedit.edit") }}
      </el-button>
    </div>
    <div v-if="!published" class="empty">
      <el-empty :description="t('dedit.notPublished')">
        <el-button type="primary" @click="$router.push(`/dashboards/${id}`)">
          {{ t("dedit.goEdit") }}
        </el-button>
      </el-empty>
    </div>
    <main v-else class="canvas" v-loading="loading">
      <DashboardRuntime v-if="content" :content="content" :data="widgets"
                        :params="paramValues" :asset-id="id" drillable
                        @update:params="setParams" @refresh="refresh"
                        @navigate="navigate" />
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { api, errMsg } from "../api";
import { t } from "../i18n";
import DashboardRuntime from "../studio/dashboard/DashboardRuntime.vue";

const route = useRoute();
const router = useRouter();
const id = Number(route.params.id);
const name = ref("");
const published = ref(false);
const content = ref(null);
const widgets = ref({});
const paramValues = ref({});
const loading = ref(false);

function resetParams() {
  const values = {};
  for (const p of content.value?.params || []) {
    if (p.name) values[p.name] = route.query[p.name] ?? p.default ?? "";
  }
  paramValues.value = values;
}

function syncUrl() {
  const query = { ...route.query };
  for (const p of content.value?.params || []) {
    const value = paramValues.value[p.name];
    if (value === "" || value === null || value === undefined) {
      delete query[p.name];
    } else {
      query[p.name] = String(value);
    }
  }
  router.replace({ query });
}

async function load() {
  try {
    const a = await api.get(`/dashboards/${id}`);
    name.value = a.name;
    published.value = Boolean(a.published_version);
    content.value = a.published || null;
    if (content.value) {
      resetParams();
      await refresh();
    }
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

function navigate(path) {
  if (path) router.push(path);
}

function setParams(p) {
  paramValues.value = { ...p };
  syncUrl();
}

async function exportCsv() {
  try {
    await api.download(`/dashboards/${id}/export.csv`,
                       `dashboard-${id}.csv`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function refresh() {
  if (!content.value) return;
  loading.value = true;
  try {
    const r = await api.post(`/dashboards/${id}/data`, {
      params: paramValues.value,
      limit: 100,
      published: true,
    });
    widgets.value = r.widgets || {};
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.run-page { min-height: calc(100vh - 104px); background: #f8fafc;
            border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden;
            display: flex; flex-direction: column; }
.head { height: 52px; display: flex; align-items: center; gap: 10px;
        padding: 0 14px; background: #fff; border-bottom: 1px solid #e5e7eb; }
.name { font-size: 14px; font-weight: 600; color: #0f172a; }
.spacer { flex: 1; }
.canvas { flex: 1; overflow: auto; padding: 14px; }
.empty { flex: 1; display: flex; align-items: center; justify-content: center; }
</style>
