<template>
  <div class="page">
    <page-header icon="collection" :title="t('menu.dataProducts')"
                 :intro="t('product.intro')" />
    <div class="toolbar">
      <el-input v-model="q" :placeholder="t('product.search')" clearable
                style="width: 260px" @keyup.enter="search" @clear="search" />
      <div class="spacer" />
      <el-button @click="load" :loading="loading">{{ t("common.refresh") }}</el-button>
      <el-button v-if="canEdit" type="primary" @click="create">
        {{ t("product.new") }}
      </el-button>
    </div>
    <el-card shadow="never">
      <el-table :data="rows" size="small" v-loading="loading">
        <el-table-column prop="name" :label="t('product.name')" min-width="180" />
        <el-table-column prop="key" :label="t('product.key')" min-width="220">
          <template #default="{ row }"><span class="mono">{{ row.key }}</span></template>
        </el-table-column>
        <el-table-column :label="t('product.status')" width="110">
          <template #default="{ row }">
            <el-tag :type="row.published ? 'success' : 'info'" size="small">
              {{ row.published ? t("product.published") : t("product.draft") }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('product.actions')" width="260">
          <template #default="{ row }">
            <el-button link @click="$router.push(`/data-products/${row.id}`)">
              {{ t("product.edit") }}
            </el-button>
            <el-button v-if="canEdit" link type="danger" @click="remove(row)">
              {{ t("product.delete") }}
            </el-button>
            <el-button link @click="downloadBundle(row)">
              {{ t("product.package") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-if="total > pageSize" class="pager"
                     layout="total, prev, pager, next" :total="total"
                     :page-size="pageSize" :current-page="page"
                     @current-change="changePage" />
      <el-empty v-if="!loading && !rows.length"
                :description="t('product.empty')" />
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, canWrite, errMsg } from "../api";
import { t } from "../i18n";

const router = useRouter();
const route = useRoute();
const rows = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = 50;
const q = ref("");
const loading = ref(false);
const canEdit = canWrite();

async function load() {
  loading.value = true;
  try {
    const params = new URLSearchParams({
      page: String(page.value), page_size: String(pageSize),
    });
    if (q.value.trim()) params.set("q", q.value.trim());
    const out = await api.get(`/data-products?${params.toString()}`);
    rows.value = out.items || [];
    total.value = out.total || 0;
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

function search() {
  page.value = 1;
  load();
}

function changePage(next) {
  page.value = next;
  load();
}

async function create() {
  try {
    const { value } = await ElMessageBox.prompt(
      t("product.namePrompt"), t("product.new"), {
        inputPattern: /\S+/, inputErrorMessage: t("product.nameRequired"),
      });
    const r = await api.post("/data-products", { name: value });
    router.push(`/data-products/${r.id}`);
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(
      t("product.deleteConfirm").replace("{name}", row.name),
      t("product.delete"), { type: "warning" });
    await api.del(`/data-products/${row.id}`);
    ElMessage.success(t("product.deleted"));
    await load();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

async function downloadBundle(row) {
  try {
    await api.download(`/data-products/${row.id}/bundle`,
                       `odf-product-${row.id}.json`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

onMounted(load);
onMounted(() => { if (route.query.new && canEdit) create(); });
</script>

<style scoped>
.toolbar { display: flex; gap: 10px; align-items: center; margin-bottom: 12px; }
.spacer { flex: 1; }
.mono { font-family: ui-monospace, monospace; font-size: 11px; }
.pager { margin-top: 12px; justify-content: flex-end; }
</style>
