<template>
  <div class="page">
    <div class="head">
      <el-button link @click="$router.push('/data-products')"
                 :aria-label="t('common.back')">←</el-button>
      <el-input v-model="name" size="small" style="width: 240px"
                @change="rename" />
      <el-tag size="small" :type="published ? 'success' : 'info'">
        {{ published ? t("product.published") : t("product.draft") }}
      </el-tag>
      <div class="spacer" />
      <el-button v-if="canEdit" size="small" @click="save">
        {{ t("aedit.save") }}
      </el-button>
      <el-button v-if="canEdit" size="small" @click="validate">
        {{ t("aedit.validate") }}
      </el-button>
      <el-button v-if="canEdit" size="small" type="primary" @click="publish">
        {{ t("aedit.publish") }}
      </el-button>
      <el-button size="small" @click="versionsOpen = true">
        {{ t("aedit.versions") }}
      </el-button>
      <el-button size="small" @click="downloadBundle">
        {{ t("product.package") }}
      </el-button>
    </div>

    <div class="body">
      <el-card shadow="never" class="meta-card">
        <el-form label-width="90px" size="small">
          <el-form-item :label="t('product.summary')">
            <el-input v-model="content.summary" type="textarea" :rows="4" />
          </el-form-item>
          <el-form-item :label="t('product.owner')">
            <el-input v-model="content.owner" />
          </el-form-item>
          <el-form-item :label="t('product.sla')">
            <el-input v-model="content.sla" />
          </el-form-item>
          <el-form-item :label="t('product.terms')">
            <el-input v-model="termsText" :placeholder="t('product.termsHint')" />
          </el-form-item>
        </el-form>
      </el-card>

      <el-card shadow="never" class="assets-card" v-loading="loading">
        <template #header>
          <div class="assets-head">
            <b>{{ t("product.members") }}</b>
            <span class="muted">
              {{ t("product.selected").replace("{n}", content.asset_ids.length) }}
            </span>
          </div>
        </template>
        <el-table ref="assetTable" :data="assets" size="small"
                  row-key="id" height="560"
                  @selection-change="onSelection">
          <el-table-column type="selection" width="42" reserve-selection />
          <el-table-column prop="name" :label="t('product.asset')" min-width="180">
            <template #default="{ row }">
              <b>{{ row.name }}</b>
              <div class="muted">{{ row.key }}</div>
            </template>
          </el-table-column>
          <el-table-column :label="t('product.assetType')" width="110">
            <template #default="{ row }">{{ typeLabel(row.type) }}</template>
          </el-table-column>
          <el-table-column prop="owner" :label="t('product.owner')" width="110" />
          <el-table-column :label="t('acat.trust')" width="90">
            <template #default="{ row }">{{ row.trust?.score ?? "-" }}</template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <el-drawer v-model="versionsOpen" :title="t('aedit.versions')"
               size="480px" @open="loadVersions">
      <el-table :data="versions" size="small">
        <el-table-column prop="version" :label="t('aedit.version')" width="70" />
        <el-table-column prop="status" :label="t('aedit.status')" width="100" />
        <el-table-column prop="created_by" :label="t('aedit.createdBy')" />
      </el-table>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref } from "vue";
import { useRoute } from "vue-router";
import { ElMessage } from "element-plus";
import { api, canWrite, errMsg } from "../api";
import { t } from "../i18n";

const route = useRoute();
const id = Number(route.params.id);
const name = ref("");
const published = ref(false);
const draftVersion = ref(null);
const content = reactive({
  summary: "", owner: "", sla: "", asset_ids: [], terms: [],
});
const assets = ref([]);
const assetTable = ref(null);
const loading = ref(false);
const versions = ref([]);
const versionsOpen = ref(false);
const canEdit = canWrite();
const termsText = computed({
  get: () => (content.terms || []).join(","),
  set: (value) => {
    content.terms = String(value || "").split(",")
      .map((item) => item.trim()).filter(Boolean).slice(0, 20);
  },
});
const typeLabels = {
  dataset: "acat.typeDataset", metric: "acat.typeMetric",
  dashboard: "acat.typeDashboard", app: "acat.typeApp",
  pipeline: "acat.typePipeline", api: "acat.typeApi",
  model: "acat.typeModel", data_product: "acat.typeDataProduct",
};

function typeLabel(value) {
  return typeLabels[value] ? t(typeLabels[value]) : value;
}

async function load() {
  loading.value = true;
  try {
    const [product, catalog] = await Promise.all([
      api.get(`/data-products/${id}`),
      api.get("/catalog/assets?limit=200&lifecycle=active"),
    ]);
    name.value = product.name;
    published.value = Boolean(product.published_version);
    draftVersion.value = product.draft_version;
    Object.assign(content, {
      summary: "", owner: "", sla: "", asset_ids: [], terms: [],
      ...(product.draft || product.published || {}),
    });
    assets.value = (catalog.items || []).filter(
      (item) => item.type !== "data_product");
    await nextTick();
    const selected = new Set(content.asset_ids || []);
    for (const row of assets.value) {
      if (selected.has(row.id)) {
        assetTable.value?.toggleRowSelection(row, true);
      }
    }
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

function onSelection(rows) {
  content.asset_ids = rows.map((row) => row.id);
}

async function rename() {
  if (!name.value.trim()) return;
  try {
    await api.put(`/data-products/${id}`, { name: name.value });
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function save() {
  try {
    const result = await api.put(`/data-products/${id}/draft`, {
      content: { ...content },
      base_version: draftVersion.value,
    });
    draftVersion.value = result.version;
    ElMessage.success(t("aedit.savedDraft"));
    return true;
  } catch (e) {
    ElMessage.error(errMsg(e));
    return false;
  }
}

async function validate() {
  try {
    const result = await api.post(`/data-products/${id}/validate`, {
      content: { ...content },
    });
    if (result.valid) ElMessage.success(t("aedit.validatePassed"));
    else ElMessage.error(result.errors.map((e) => e.message).join("; "));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function publish() {
  try {
    if (!(await save())) return;
    const result = await api.post(`/data-products/${id}/publish`);
    published.value = true;
    ElMessage.success(t("product.publishedVersion")
      .replace("{version}", result.version));
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function loadVersions() {
  try {
    versions.value = await api.get(`/data-products/${id}/versions`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function downloadBundle() {
  try {
    await api.download(`/data-products/${id}/bundle`,
                       `odf-product-${id}.json`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

onMounted(load);
</script>

<style scoped>
.head { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.spacer { flex: 1; }
.body { display: grid; grid-template-columns: 340px 1fr; gap: 14px; }
.meta-card, .assets-card { border-radius: 10px; }
.assets-head { display: flex; align-items: center; justify-content: space-between; }
.muted { color: #64748b; font-size: 11px; }
@media (max-width: 1100px) {
  .body { grid-template-columns: 1fr; }
}
</style>
