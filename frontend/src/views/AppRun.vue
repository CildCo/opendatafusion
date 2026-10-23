<template>
  <div class="run-page">
    <div class="head">
      <el-button link @click="$router.push('/apps')">←</el-button>
      <span class="app-name">{{ name }}</span>
      <el-tag v-if="published" size="small" type="success">已发布</el-tag>
      <div class="spacer" />
      <el-button v-if="content" size="small" @click="refresh">
        刷新数据
      </el-button>
      <el-button size="small" @click="$router.push(`/apps/${id}`)">
        编辑
      </el-button>
    </div>
    <div v-if="!published" class="empty">
      <el-empty description="应用还没有发布版本">
        <el-button type="primary" @click="$router.push(`/apps/${id}`)">
          去编辑
        </el-button>
      </el-empty>
    </div>
    <template v-else>
      <div v-if="content.pages.length > 1" class="tabs">
        <el-radio-group v-model="currentId" size="small">
          <el-radio-button v-for="p in content.pages" :key="p.id"
                           :value="p.id">
            {{ p.title || p.id }}
          </el-radio-button>
        </el-radio-group>
      </div>
      <main class="canvas" v-loading="loading">
        <AppRuntime v-if="currentPage" :key="currentPage.id"
                    :page="currentPage" :data="data" :params="paramValues"
                    :on-submit="submitForm"
                    @update:params="setParams" @refresh="refresh" />
      </main>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { ElMessage } from "element-plus";
import { api, errMsg } from "../api";
import AppRuntime from "../studio/app/AppRuntime.vue";

const route = useRoute();
const id = Number(route.params.id);
const name = ref("");
const published = ref(false);
const content = ref(null);
const currentId = ref("");
const paramValues = ref({});
const data = ref({});
const loading = ref(false);

const currentPage = computed(() =>
  content.value?.pages?.find((p) => p.id === currentId.value) || null);

function resetParams() {
  const values = {};
  for (const p of currentPage.value?.params || []) {
    if (p.name) values[p.name] = p.default ?? "";
  }
  paramValues.value = values;
}

async function load() {
  try {
    const a = await api.get(`/apps/${id}`);
    name.value = a.name;
    published.value = Boolean(a.published_version);
    content.value = a.published || null;
    if (content.value) {
      currentId.value = content.value.start_page
        || content.value.pages[0]?.id || "";
      resetParams();
      await refresh();
    }
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

function setParams(p) {
  paramValues.value = { ...p };
  refresh();
}

async function submitForm(componentId, values) {
  await api.post(`/apps/${id}/submit`, {
    component_id: componentId,
    values,
    published: true,
  });
  await refresh();
}

async function refresh() {
  if (!currentPage.value) return;
  loading.value = true;
  try {
    const r = await api.post(`/apps/${id}/data`, {
      page_id: currentPage.value.id,
      params: paramValues.value,
      limit: 100,
      published: true,
    });
    data.value = r.components || {};
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

watch(currentId, () => {
  resetParams();
  data.value = {};
  refresh();
});

onMounted(load);
</script>

<style scoped>
.run-page { min-height: calc(100vh - 104px); background: #f8fafc;
            border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden;
            display: flex; flex-direction: column; }
.head { height: 52px; display: flex; align-items: center; gap: 10px;
        padding: 0 14px; background: #fff; border-bottom: 1px solid #e5e7eb; }
.app-name { font-size: 14px; font-weight: 600; color: #0f172a; }
.spacer { flex: 1; }
.tabs { padding: 10px 16px 0; }
.canvas { flex: 1; overflow: auto; padding: 16px; max-width: 1200px;
          width: 100%; margin: 0 auto; }
.empty { flex: 1; display: flex; align-items: center; justify-content: center; }
</style>
