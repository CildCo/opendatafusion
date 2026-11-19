<template>
  <div class="page">
    <div class="toolbar">
      <el-select v-model="status" clearable
                 :placeholder="t('alerts.allStatus')" style="width: 140px"
                 @change="load">
        <el-option value="open" :label="t('alerts.statusOpen')" />
        <el-option value="acked" :label="t('alerts.statusAcked')" />
        <el-option value="closed" :label="t('alerts.statusClosed')" />
      </el-select>
      <el-select v-model="severity" clearable
                 :placeholder="t('alerts.allSeverity')" style="width: 140px">
        <el-option value="critical" :label="t('alerts.severityCritical')" />
        <el-option value="warning" :label="t('alerts.severityWarning')" />
      </el-select>
      <div class="spacer" />
      <el-button @click="$router.push('/webhooks')">
        {{ t("alerts.subscriptions") }}
      </el-button>
      <el-button @click="load" :loading="loading">
        {{ t("alerts.refresh") }}
      </el-button>
    </div>

    <el-card class="card" shadow="never">
      <el-table :data="filtered" size="small" v-loading="loading"
                @row-click="showDetail" row-class-name="clickable">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="severity" :label="t('alerts.colSeverity')"
                         width="90">
          <template #default="{ row }">
            <el-tag :type="row.severity === 'critical' ? 'danger' : 'warning'"
                    size="small">{{ row.severity }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" :label="t('alerts.colTitle')"
                         min-width="220" />
        <el-table-column prop="status" :label="t('alerts.colStatus')"
                         width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'open' ? 'danger' : row.status === 'acked' ? 'warning' : 'info'"
                    size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" :label="t('alerts.colTime')"
                         width="200" />
        <el-table-column :label="t('alerts.colActions')" width="180"
                         fixed="right">
          <template #default="{ row }">
            <el-button link :disabled="row.status !== 'open'"
                       @click.stop="ack(row)">
              {{ t("alerts.ack") }}
            </el-button>
            <el-button link :disabled="row.status === 'closed'"
                       @click.stop="close(row)">
              {{ t("alerts.close") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !filtered.length"
                :description="t('alerts.empty')" />
    </el-card>

    <el-card class="card" shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <b>{{ t("alerts.rules") }}</b>
          <el-button size="small" type="primary" @click="openRule">
            {{ t("alerts.newRule") }}
          </el-button>
        </div>
      </template>
      <el-table :data="rules" size="small">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" :label="t('alerts.ruleName')"
                         min-width="180" />
        <el-table-column prop="kind" :label="t('alerts.ruleKind')"
                         width="150" />
        <el-table-column :label="t('alerts.colActions')" width="100">
          <template #default="{ row }">
            <el-button link type="danger" @click="removeRule(row)">
              {{ t("alerts.deleteRule") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!rules.length" :description="t('alerts.noRules')"
                :image-size="60" />
    </el-card>

    <el-drawer v-model="drawer"
               :title="current.title || t('alerts.drawerTitle')"
               size="520px">
      <el-descriptions :column="1" border>
        <el-descriptions-item :label="t('alerts.colSeverity')">
          {{ current.severity }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('alerts.colStatus')">
          {{ statusLabel(current.status) }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('alerts.colTime')">
          {{ current.created_at }}
        </el-descriptions-item>
      </el-descriptions>
      <h4>{{ t("alerts.detail") }}</h4>
      <pre class="detail">{{ JSON.stringify(current.detail, null, 2) }}</pre>
    </el-drawer>

    <el-dialog v-model="ruleDialog" :title="t('alerts.newRule')"
               width="520px">
      <el-form label-width="110px">
        <el-form-item :label="t('alerts.ruleName')" required>
          <el-input v-model="ruleForm.name" />
        </el-form-item>
        <el-form-item :label="t('alerts.ruleKind')" required>
          <el-input v-model="ruleForm.kind" placeholder="flow_health" />
        </el-form-item>
        <el-form-item :label="t('alerts.ruleConfig')">
          <el-input v-model="ruleForm.config" type="textarea" :rows="4"
                    placeholder="{}" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ruleDialog = false">{{ t("alerts.cancel") }}</el-button>
        <el-button type="primary" @click="createRule">
          {{ t("alerts.save") }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../api";
import { t } from "../i18n";

const rows = ref([]);
const rules = ref([]);
const loading = ref(false);
const status = ref("");
const severity = ref("");
const drawer = ref(false);
const current = ref({});
const ruleDialog = ref(false);
const ruleForm = reactive({ name: "", kind: "flow_health", config: "{}" });

const filtered = computed(() =>
  rows.value.filter((r) => !severity.value || r.severity === severity.value)
);

function statusLabel(s) {
  return {
    open: t("alerts.statusOpen"),
    acked: t("alerts.statusAcked"),
    closed: t("alerts.statusClosed"),
  }[s] || s;
}

async function load() {
  loading.value = true;
  try {
    const q = status.value ? `?status=${status.value}` : "";
    rows.value = await api.get("/alerts" + q);
    rules.value = await api.get("/alerts/rules");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}
function showDetail(row) {
  current.value = row;
  drawer.value = true;
}
async function ack(row) {
  try {
    await api.post(`/alerts/${row.id}/ack`);
    await load();
    ElMessage.success(t("alerts.ackedMsg"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}
async function close(row) {
  try {
    await ElMessageBox.confirm(t("alerts.closeConfirm"),
                               t("alerts.closeTitle"),
                               { type: "warning" });
    await api.post(`/alerts/${row.id}/close`);
    await load();
    ElMessage.success(t("alerts.closedMsg"));
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}
onMounted(load);

function openRule() {
  ruleForm.name = "";
  ruleForm.kind = "flow_health";
  ruleForm.config = "{}";
  ruleDialog.value = true;
}

async function createRule() {
  if (!ruleForm.name.trim() || !ruleForm.kind.trim()) {
    ElMessage.warning(t("alerts.nameRequired"));
    return;
  }
  let config = {};
  try {
    config = ruleForm.config.trim() ? JSON.parse(ruleForm.config) : {};
  } catch (e) {
    ElMessage.error(t("alerts.ruleConfig") + ": " + errMsg(e));
    return;
  }
  try {
    await api.post("/alerts/rules", {
      name: ruleForm.name.trim(), kind: ruleForm.kind.trim(), config,
    });
    ruleDialog.value = false;
    await load();
    ElMessage.success(t("alerts.created"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function removeRule(row) {
  try {
    await ElMessageBox.confirm(
      t("alerts.deleteRuleConfirm").replace("{name}", row.name),
      t("alerts.deleteRule"), { type: "warning" });
  } catch (e) {
    return;
  }
  try {
    await api.del(`/alerts/rules/${row.id}`);
    await load();
    ElMessage.success(t("alerts.deleted"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}
</script>

<style scoped>
.card {
  border-radius: 0;
  border: 1px solid #e5e7eb;
}
.detail {
  background: #0f172a;
  color: #e2e8f0;
  padding: 14px;
  border-radius: 0;
  font-size: 12px;
  overflow: auto;
}
:deep(.clickable) {
  cursor: pointer;
}
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
