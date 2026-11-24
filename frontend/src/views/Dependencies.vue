<template>
  <div class="page">
    <page-header icon="dependency" :title="t('menu.dependencies')"
                 :intro="t('dep.intro')" />
    <div class="toolbar">
      <el-radio-group v-model="view" size="small">
        <el-radio-button value="table">{{ t("dep.viewTable") }}</el-radio-button>
        <el-radio-button value="graph">{{ t("dep.viewGraph") }}</el-radio-button>
      </el-radio-group>
      <div class="spacer" />
      <el-button @click="load" :loading="loading">
        {{ t("dep.refresh") }}
      </el-button>
      <el-button v-if="canEdit" type="primary" @click="openCreate">
        {{ t("dep.new") }}
      </el-button>
    </div>

    <el-card class="card" shadow="never">
      <el-table v-if="view === 'table'" :data="rows" size="small"
                v-loading="loading">
        <el-table-column :label="t('dep.downstream')" min-width="220">
          <template #default="{ row }">
            <span class="entity-cell">
              <entity-icon :type="row.downstream_type" :size="20" />
              <b>{{ row.downstream_name }}</b>
            </span>
          </template>
        </el-table-column>
        <el-table-column :label="t('dep.upstream')" min-width="220">
          <template #default="{ row }">
            <span class="entity-cell">
              <entity-icon :type="row.upstream_type" :size="20" />
              <span>{{ row.upstream_name }}</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column :label="t('dep.actions')" width="100">
          <template #default="{ row }">
            <el-button v-if="canEdit" link type="danger" @click="remove(row)">
              {{ t("dep.delete") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <empty-state v-if="view === 'table' && !loading && !rows.length"
                   :title="t('dep.empty')" :description="t('dep.intro')"
                   :action-text="canEdit ? t('dep.new') : ''" @action="openCreate" />
      <graph-canvas v-if="view === 'graph'" :nodes="depGraph.nodes"
                    :edges="depGraph.edges" :height="480"
                    :empty-text="t('dep.empty')" />
    </el-card>

    <el-dialog v-model="dialog" :title="t('dep.new')" width="600px">
      <el-form label-width="110px">
        <el-form-item :label="t('dep.downstream')" required>
          <el-select v-model="form.downstream_id" filterable
                     style="width: 250px; margin-left: 8px"
                     :placeholder="t('dep.selectObject')">
            <el-option v-for="o in pipelines"
                       :key="o.id" :value="o.id"
                       :label="optionLabel(o)" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('dep.upstream')" required>
          <el-select v-model="form.upstream_id" filterable
                     style="width: 250px; margin-left: 8px"
                     :placeholder="t('dep.selectObject')">
            <el-option v-for="o in pipelines"
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
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, canWrite, errMsg } from "../api";
import GraphCanvas from "../components/GraphCanvas.vue";
import EmptyState from "../components/EmptyState.vue";
import EntityIcon from "../components/EntityIcon.vue";
import PageHeader from "../components/PageHeader.vue";
import { t } from "../i18n";

const rows = ref([]);
const view = ref("table");
const canEdit = canWrite();

const depGraph = computed(() => {
  const nodes = new Map();
  const edges = [];
  const add = (type, id, name) => {
    const key = `${type}:${id}`;
    if (!nodes.has(key)) nodes.set(key, { id: key, name, type });
    return key;
  };
  for (const row of rows.value) {
    const upstream = add(row.upstream_type, row.upstream_id,
                         row.upstream_name);
    const downstream = add(row.downstream_type, row.downstream_id,
                           row.downstream_name);
    edges.push({ from: upstream, to: downstream });
  }
  return { nodes: [...nodes.values()], edges };
});
const pipelines = ref([]);
const loading = ref(false);
const saving = ref(false);
const dialog = ref(false);
const form = reactive({ downstream_id: null, upstream_id: null });

function optionLabel(row) {
  return `${row.name} (#${row.id})`;
}

async function load() {
  loading.value = true;
  try {
    const [deps, pipeRows] = await Promise.all([
      api.get("/dependencies"),
      api.get("/pipelines"),
    ]);
    rows.value = deps;
    pipelines.value = pipeRows.items || [];
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  form.downstream_id = null;
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
    await api.post("/dependencies", {
      downstream_type: "pipeline", downstream_id: form.downstream_id,
      upstream_type: "pipeline", upstream_id: form.upstream_id,
    });
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
.entity-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.card { border-radius: 12px; border: 1px solid #e5e7eb; }
.muted { color: #64748b; font-size: 12px; margin: 0; }
</style>
