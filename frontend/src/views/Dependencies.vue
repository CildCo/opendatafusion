<template>
  <div class="page">
    <div class="toolbar">
      <div class="spacer" />
      <el-button @click="load" :loading="loading">
        {{ t("dep.refresh") }}
      </el-button>
      <el-button type="primary" @click="openCreate">
        {{ t("dep.new") }}
      </el-button>
    </div>

    <p class="page-intro">{{ t("dep.intro") }}</p>

    <el-card class="card" shadow="never">
      <el-table :data="rows" size="small" v-loading="loading">
        <el-table-column :label="t('dep.downstream')" min-width="200">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.downstream_type }}</el-tag>
            <span style="margin-left: 8px">{{ row.downstream_name }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('dep.upstream')" min-width="200">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" type="info">
              {{ row.upstream_type }}
            </el-tag>
            <span style="margin-left: 8px">{{ row.upstream_name }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('dep.actions')" width="100">
          <template #default="{ row }">
            <el-button link type="danger" @click="remove(row)">
              {{ t("dep.delete") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !rows.length" :description="t('dep.empty')">
        <el-button type="primary" @click="openCreate">
          {{ t("dep.new") }}
        </el-button>
      </el-empty>
    </el-card>

    <el-dialog v-model="dialog" :title="t('dep.new')" width="600px">
      <el-form label-width="110px">
        <el-form-item :label="t('dep.downstream')" required>
          <el-select v-model="form.downstream_type" style="width: 130px"
                     @change="form.downstream_id = null">
            <el-option value="flow" :label="t('dep.flow')" />
            <el-option value="pipeline" :label="t('dep.pipeline')" />
          </el-select>
          <el-select v-model="form.downstream_id" filterable
                     style="width: 250px; margin-left: 8px"
                     :placeholder="t('dep.selectObject')">
            <el-option v-for="o in options(form.downstream_type)"
                       :key="o.id" :value="o.id"
                       :label="optionLabel(o)" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('dep.upstream')" required>
          <el-select v-model="form.upstream_type" style="width: 130px"
                     @change="form.upstream_id = null">
            <el-option value="flow" :label="t('dep.flow')" />
            <el-option value="pipeline" :label="t('dep.pipeline')" />
          </el-select>
          <el-select v-model="form.upstream_id" filterable
                     style="width: 250px; margin-left: 8px"
                     :placeholder="t('dep.selectObject')">
            <el-option v-for="o in options(form.upstream_type)"
                       :key="o.id" :value="o.id"
                       :label="optionLabel(o)" />
          </el-select>
        </el-form-item>
      </el-form>
      <p class="muted">{{ t("dep.hint") }}</p>
      <template #footer>
        <el-button @click="dialog = false">{{ t("dep.cancel") }}</el-button>
        <el-button type="primary" :loading="saving" @click="create">
          {{ t("dep.save") }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../api";
import { t } from "../i18n";

const rows = ref([]);
const flows = ref([]);
const pipelines = ref([]);
const loading = ref(false);
const saving = ref(false);
const dialog = ref(false);
const form = reactive({ downstream_type: "flow", downstream_id: null,
                        upstream_type: "flow", upstream_id: null });

function options(kind) {
  return kind === "flow" ? flows.value : pipelines.value;
}

function optionLabel(row) {
  return `${row.name} (#${row.id})`;
}

async function load() {
  loading.value = true;
  try {
    const [deps, flowRows, pipeRows] = await Promise.all([
      api.get("/dependencies"),
      api.get("/flows"),
      api.get("/pipelines"),
    ]);
    rows.value = deps;
    flows.value = flowRows;
    pipelines.value = pipeRows;
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  form.downstream_type = "flow";
  form.downstream_id = null;
  form.upstream_type = "flow";
  form.upstream_id = null;
  dialog.value = true;
}

async function create() {
  if (!form.downstream_id || !form.upstream_id) {
    ElMessage.warning(t("dep.required"));
    return;
  }
  saving.value = true;
  try {
    await api.post("/dependencies", form);
    dialog.value = false;
    await load();
    ElMessage.success(t("dep.created"));
  } catch (e) {
    const text = errMsg(e);
    if (/cycle/i.test(text)) ElMessage.error(t("dep.cycle"));
    else if (/itself/i.test(text)) ElMessage.error(t("dep.self"));
    else ElMessage.error(text);
  } finally {
    saving.value = false;
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(
      t("dep.deleteConfirm")
        .replace("{downstream}", row.downstream_name)
        .replace("{upstream}", row.upstream_name),
      t("dep.deleteTitle"), { type: "warning" });
    await api.del(`/dependencies/${row.id}`);
    await load();
    ElMessage.success(t("dep.deleted"));
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

onMounted(load);
</script>

<style scoped>
.card { border-radius: 12px; border: 1px solid #e5e7eb; }
.muted { color: #64748b; font-size: 12px; margin: 0; }
</style>
