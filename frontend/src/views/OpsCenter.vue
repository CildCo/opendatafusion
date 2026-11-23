<template>
  <div class="ops-page">
    <div class="toolbar">
      <el-tag size="small" effect="plain">{{ projectLabel }}</el-tag>
      <div class="spacer" />
      <span class="updated">{{ t("ops.updatedAt") }} {{ updated || "-" }}</span>
      <el-switch v-model="auto" :active-text="t('ops.autoRefresh')" size="small" />
      <el-button size="small" :loading="loading" @click="load">{{ t("ops.refresh") }}</el-button>
    </div>

    <div class="cards">
      <div v-for="c in cards" :key="c.label" class="card"
           :class="c.tone">
        <div class="card-value">{{ c.value }}</div>
        <sparkline v-if="c.values && c.values.length" :values="c.values"
                   :tone="c.tone === 'red' ? 'danger'
                     : c.tone === 'amber' ? 'warning' : 'primary'"
                   :width="110" :height="22" />
        <div class="card-label">{{ c.label }}</div>
      </div>
    </div>

    <el-card shadow="never" class="panel">
      <el-tabs v-model="tab">
        <el-tab-pane :label="t('ops.tabOverview')" name="overview">
          <div class="section-title">{{ t("ops.recentFailures") }}</div>
          <el-table :data="summary.recent_failures || []" size="small"
                    :empty-text="t('ops.emptyFailures')">
            <el-table-column prop="id" :label="t('ops.job')" width="80" />
            <el-table-column prop="target_name" :label="t('ops.target')" min-width="140" />
            <el-table-column prop="target_type" :label="t('ops.type')" width="90" />
            <el-table-column prop="attempts" :label="t('ops.attempts')" width="70" />
            <el-table-column prop="last_error" :label="t('ops.error')" min-width="260"
                             show-overflow-tooltip />
            <el-table-column prop="finished_at" :label="t('ops.finishedAt')" width="180">
              <template #default="{ row }">{{ fmt(row.finished_at) }}</template>
            </el-table-column>
            <el-table-column :label="t('ops.actions')" width="130">
              <template #default="{ row }">
                <el-button v-if="canOperate" link type="primary"
                           @click="retry(row)">
                  {{ t("ops.retry") }}
                </el-button>
                <el-button v-if="targetPath(row)" link @click="openTarget(row)">
                  {{ t("ops.view") }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="t('ops.tabJobs')" name="jobs">
          <div class="filters">
            <el-select v-model="jobStatus" clearable
                       :placeholder="t('ops.allStatuses')"
                       size="small" style="width: 140px" @change="loadJobs">
              <el-option v-for="s in statuses" :key="s" :value="s"
                         :label="s" />
            </el-select>
            <el-button size="small" @click="loadJobs">{{ t("ops.query") }}</el-button>
          </div>
          <template v-if="dependencyBlocked.length">
            <div class="section-title">{{ t("ops.dependencySkips") }}</div>
            <el-table :data="dependencyBlocked" size="small"
                      style="margin-bottom: 14px">
              <el-table-column prop="name" :label="t('ops.dependencyObject')"
                               min-width="180" />
              <el-table-column prop="reason"
                               :label="t('ops.dependencyReason')"
                               min-width="260" />
              <el-table-column :label="t('ops.createdAt')" width="180">
                <template #default="{ row }">{{ fmt(row.at) }}</template>
              </el-table-column>
            </el-table>
          </template>
          <el-table :data="jobs" size="small" :empty-text="t('ops.emptyJobs')">
            <el-table-column prop="id" :label="t('ops.job')" width="80" />
            <el-table-column prop="target_name" :label="t('ops.target')" min-width="160" />
            <el-table-column prop="asset_type" :label="t('ops.assetType')" width="100" />
            <el-table-column :label="t('ops.status')" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="jobTone(row.status)">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="t('ops.attempts')" width="90">
              <template #default="{ row }">
                {{ row.attempts }}/{{ row.max_attempts }}
              </template>
            </el-table-column>
            <el-table-column prop="last_error" :label="t('ops.error')" min-width="220"
                             show-overflow-tooltip />
            <el-table-column prop="run_at" :label="t('ops.scheduledAt')" width="180">
              <template #default="{ row }">{{ fmt(row.run_at) }}</template>
            </el-table-column>
            <el-table-column :label="t('ops.actions')" width="130">
              <template #default="{ row }">
                <el-button v-if="canOperate && row.status === 'failed'"
                           link type="primary" @click="retry(row)">
                  {{ t("ops.retry") }}
                </el-button>
                <el-button v-if="targetPath(row)" link @click="openTarget(row)">
                  {{ t("ops.view") }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="t('ops.tabAlerts')" name="alerts">
          <div class="filters">
            <el-select v-model="alertStatus" clearable
                       :placeholder="t('ops.allStatuses')"
                       size="small" style="width: 130px"
                       @change="loadAlerts">
              <el-option value="open" label="open" />
              <el-option value="acked" label="acked" />
              <el-option value="closed" label="closed" />
            </el-select>
            <el-select v-model="alertSeverity" clearable
                       :placeholder="t('ops.allSeverities')"
                       size="small" style="width: 130px"
                       @change="loadAlerts">
              <el-option value="critical" label="critical" />
              <el-option value="warning" label="warning" />
              <el-option value="error" label="error" />
              <el-option value="info" label="info" />
            </el-select>
            <el-button size="small" @click="router.push('/alerts')">
              {{ t("ops.openAlerts") }}
            </el-button>
          </div>
          <el-table :data="alerts" size="small" :empty-text="t('ops.emptyAlerts')">
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column :label="t('ops.severity')" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="severityTone(row.severity)">
                  {{ row.severity }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="title" :label="t('ops.title')" min-width="240" />
            <el-table-column prop="status" :label="t('ops.status')" width="90" />
            <el-table-column prop="created_at" :label="t('ops.createdAt')" width="180">
              <template #default="{ row }">{{ fmt(row.created_at) }}</template>
            </el-table-column>
            <el-table-column :label="t('ops.actions')" width="130">
              <template #default="{ row }">
                <el-button v-if="canOperate && row.status === 'open'" link
                           @click="ack(row)">{{ t("ops.ack") }}</el-button>
                <el-button v-if="canOperate && row.status !== 'closed'" link
                           type="danger" @click="close(row)">{{ t("ops.close") }}</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="t('ops.tabHealth')" name="health">
          <div class="filters">
            <el-tag v-for="(v, k) in health.counts" :key="k" size="small"
                    :type="healthTone(k)">
              {{ k }} {{ v }}
            </el-tag>
            <el-button size="small" @click="loadHealth">{{ t("ops.refresh") }}</el-button>
          </div>
          <div class="section-title">{{ t("ops.flowHealth") }}</div>
          <el-table :data="health.flows || []" size="small"
                    :empty-text="t('ops.emptyFlows')">
            <el-table-column prop="name" :label="t('ops.flow')" min-width="180" />
            <el-table-column :label="t('ops.status')" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="healthTone(row.status)">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="t('ops.lag')" width="110">
              <template #default="{ row }">
                {{ row.lag_s == null ? "-" : row.lag_s + "s" }}
              </template>
            </el-table-column>
            <el-table-column prop="empty_rounds" :label="t('ops.emptyRounds')" width="90" />
            <el-table-column :label="t('ops.cursorAge')" width="120">
              <template #default="{ row }">
                {{ row.cursor_age_s == null ? "-" : row.cursor_age_s + "s" }}
              </template>
            </el-table-column>
          </el-table>
          <div class="section-title" style="margin-top: 16px">{{ t("ops.recentHealthEvents") }}</div>
          <el-table :data="health.events || []" size="small"
                    :empty-text="t('ops.emptyHealthEvents')">
            <el-table-column prop="flow_id" :label="t('ops.flow')" width="90" />
            <el-table-column prop="kind" :label="t('ops.type')" width="130" />
            <el-table-column :label="t('ops.severity')" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="severityTone(row.severity)">
                  {{ row.severity }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="at" :label="t('ops.time')" width="180">
              <template #default="{ row }">{{ fmt(row.at) }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="t('ops.tabApi')" name="api">
          <el-table :data="apiStats" size="small" :empty-text="t('ops.emptyApi')">
            <el-table-column prop="api_name" :label="t('ops.api')" min-width="180" />
            <el-table-column prop="key" label="Key" min-width="200" />
            <el-table-column prop="ak" label="AK" min-width="160" />
            <el-table-column prop="count" :label="t('ops.calls')" width="80" />
            <el-table-column prop="errors" :label="t('ops.error')" width="80" />
            <el-table-column prop="avg_ms" :label="t('ops.avgLatency')" width="100" />
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="t('ops.tabTimeline')" name="timeline">
          <el-timeline v-if="timeline.length">
            <el-timeline-item v-for="(x, i) in timeline" :key="i"
                              :timestamp="fmt(x.at)"
                              :type="severityTone(x.severity)">
              <span class="kind">{{ x.kind }}</span>
              {{ x.title }}
              <span class="target">{{ x.target }}</span>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else :description="t('ops.emptyTimeline')" />
        </el-tab-pane>

        <el-tab-pane v-if="isAdmin" :label="t('ops.tabAudit')" name="audit">
          <div class="filters">
            <el-input v-model="auditActor" size="small"
                      :placeholder="t('ops.actor')"
                      clearable style="width: 140px" />
            <el-input v-model="auditAction" size="small"
                      :placeholder="t('ops.action')"
                      clearable style="width: 160px" />
            <el-input v-model="auditQ" size="small"
                      :placeholder="t('ops.keyword')"
                      clearable style="width: 180px" />
            <el-button size="small" @click="loadAudit">{{ t("ops.query") }}</el-button>
          </div>
          <el-table :data="audit" size="small" :empty-text="t('ops.emptyAudit')">
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="actor" :label="t('ops.actor')" width="120" />
            <el-table-column prop="action" :label="t('ops.action')" width="170" />
            <el-table-column prop="target" :label="t('ops.target')" width="120" />
            <el-table-column prop="detail" :label="t('ops.detail')" min-width="260"
                             show-overflow-tooltip>
              <template #default="{ row }">
                <el-popover v-if="row.detail && Object.keys(row.detail).length"
                            placement="left" :width="360" trigger="click">
                  <template #reference>
                    <el-button link>{{ t("ops.view") }}</el-button>
                  </template>
                  <json-view :value="row.detail" />
                </el-popover>
                <span v-else class="muted">-</span>
              </template>
            </el-table-column>
            <el-table-column prop="at" :label="t('ops.time')" width="180">
              <template #default="{ row }">{{ fmt(row.at) }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useRouter } from "vue-router";
import { api, errMsg, getRole } from "../api";
import { fmtDate, t } from "../i18n";
import JsonView from "../components/JsonView.vue";
import Sparkline from "../components/Sparkline.vue";

const router = useRouter();

const role = getRole() || "viewer";
const isAdmin = role === "admin";
const canOperate = ["editor", "approver", "admin"].includes(role);
const projectLabel = computed(() => t("ops.projectLabel"));
const tab = ref("overview");
const summary = ref({});
const trendJobs = ref([]);

function hourly(status) {
  const buckets = new Array(24).fill(0);
  const now = Date.now();
  for (const job of trendJobs.value) {
    if (status && job.status !== status) continue;
    const stamp = Date.parse(job.run_at || job.created_at || "");
    if (Number.isNaN(stamp)) continue;
    const hoursAgo = Math.floor((now - stamp) / 3600000);
    if (hoursAgo >= 0 && hoursAgo < 24) buckets[23 - hoursAgo] += 1;
  }
  return buckets.some((n) => n > 0) ? buckets : [];
}
const jobs = ref([]);
const alerts = ref([]);
const health = ref({ flows: [], counts: {}, events: [] });
const timeline = ref([]);
const apiStats = ref([]);
const audit = ref([]);
const dependencyBlocked = ref([]);
const jobStatus = ref("");
const alertStatus = ref("");
const alertSeverity = ref("");
const auditActor = ref("");
const auditAction = ref("");
const auditQ = ref("");
const loading = ref(false);
const auto = ref(false);
const updated = ref("");
const statuses = ["queued", "running", "failed", "success"];
let timer = null;

const cards = computed(() => {
  const j = summary.value.jobs || {};
  const a = summary.value.alerts || {};
  const h = summary.value.health || {};
  const assets = summary.value.assets || {};
  const unhealthy = (h.critical || 0) + (h.warning || 0);
  return [
    { label: t("ops.cardQueued"), value: j.queued || 0, tone: "blue",
      values: hourly() },
    { label: t("ops.cardRunning"), value: j.running || 0, tone: "blue" },
    { label: t("ops.cardFailed"), value: j.failed || 0, tone: "red",
      values: hourly("failed") },
    { label: t("ops.cardOpenAlerts"), value: a.open || 0, tone: "amber" },
    { label: t("ops.cardUnhealthy"), value: unhealthy, tone: "amber" },
    { label: t("ops.cardAssets"),
      value: Object.values(assets).reduce((x, y) => x + y, 0), tone: "" },
  ];
});

function fmt(v) {
  if (!v) return "-";
  return fmtDate(v);
}

function jobTone(s) {
  return { failed: "danger", running: "warning", queued: "info",
           success: "success" }[s] || "info";
}

function targetPath(row) {
  const type = row.asset_type || row.target_type || "";
  return { flow: "/flows", pipeline: "/pipelines", api: "/apis",
           dashboard: "/dashboards", app: "/apps", dataset: "/datasets",
           metric: "/metrics" }[type] || "";
}

function openTarget(row) {
  const base = targetPath(row);
  const assetId = row.asset_id || row.target_id;
  router.push(assetId ? `${base}/${assetId}` : base);
}
function severityTone(s) {
  return { critical: "danger", warning: "warning", info: "info",
           ok: "success" }[s] || "info";
}
function healthTone(s) {
  return { critical: "danger", warning: "warning", ok: "success" }[s]
    || "info";
}

async function loadSummary() {
  summary.value = await api.get("/ops/summary");
  try {
    trendJobs.value = await api.get("/ops/jobs?limit=200");
  } catch {
    trendJobs.value = [];
  }
}
async function loadJobs() {
  const q = jobStatus.value
    ? `?status=${encodeURIComponent(jobStatus.value)}` : "";
  jobs.value = await api.get("/ops/jobs" + q);
}
async function loadAlerts() {
  const p = new URLSearchParams();
  if (alertStatus.value) p.set("status", alertStatus.value);
  if (alertSeverity.value) p.set("severity", alertSeverity.value);
  const q = p.toString() ? "?" + p.toString() : "";
  alerts.value = await api.get("/ops/alerts" + q);
}
async function loadHealth() {
  health.value = await api.get("/ops/health");
}
async function loadTimeline() {
  timeline.value = await api.get("/ops/timeline");
}
async function loadApiStats() {
  apiStats.value = await api.get("/api-stats");
}
async function loadDependencyStatus() {
  try {
    dependencyBlocked.value = await api.get("/ops/dependency-status");
  } catch {
    dependencyBlocked.value = [];
  }
}

async function loadAudit() {
  if (!isAdmin) return;
  const p = new URLSearchParams();
  if (auditActor.value) p.set("actor", auditActor.value);
  if (auditAction.value) p.set("action", auditAction.value);
  if (auditQ.value) p.set("q", auditQ.value);
  const q = p.toString() ? "?" + p.toString() : "";
  audit.value = await api.get("/ops/audit" + q);
}

async function load() {
  loading.value = true;
  try {
    await Promise.all([
      loadSummary(), loadJobs(), loadAlerts(), loadHealth(),
      loadTimeline(), loadApiStats(), loadAudit(),
      loadDependencyStatus(),
    ]);
    updated.value = new Date().toLocaleTimeString("zh-CN");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

async function retry(row) {
  try {
    await ElMessageBox.confirm(
      t("ops.retryConfirm")
        .replace("{id}", row.id)
        .replace("{name}", row.target_name || "-"),
      t("ops.retryTitle"));
    await api.post(`/ops/jobs/${row.id}/retry`);
    ElMessage.success(t("ops.requeued"));
    await load();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

async function ack(row) {
  try {
    await api.post(`/ops/alerts/${row.id}/ack`);
    ElMessage.success(t("ops.acked"));
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function close(row) {
  try {
    await ElMessageBox.confirm(
      t("ops.closeConfirm").replace("{title}", row.title), t("ops.closeTitle"));
    await api.post(`/ops/alerts/${row.id}/close`);
    ElMessage.success(t("ops.closed"));
    await load();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

watch(auto, (on) => {
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
  if (on) timer = setInterval(load, 30000);
});
watch(tab, (name) => {
  if (name === "audit") loadAudit();
});

onMounted(load);
onBeforeUnmount(() => {
  if (timer) clearInterval(timer);
});
</script>

<style scoped>
.ops-page { background: #f8fafc; border: 1px solid #e5e7eb;
            border-radius: 0; padding: 14px; }
.toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.spacer { flex: 1; }
.updated { font-size: 11px; color: #6b7280; }
.cards { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px;
         margin-bottom: 12px; }
.card { background: #fff; border: 1px solid #e5e7eb; border-radius: 0;
        padding: 12px 14px; border-left: 3px solid #cbd5e1; }
.card.red { border-left-color: #ef4444; }
.card.amber { border-left-color: #f59e0b; }
.card.blue { border-left-color: #3b82f6; }
.card-value { font-size: 24px; font-weight: 700; color: #0f172a;
              line-height: 1.2; }
.card-label { font-size: 11px; color: #64748b; margin-top: 2px; }
.panel :deep(.el-card__body) { padding: 8px 14px 14px; }
.filters { display: flex; gap: 8px; align-items: center; margin-bottom: 10px;
           flex-wrap: wrap; }
.section-title { font-size: 13px; font-weight: 600; color: #334155;
                 margin: 6px 0 8px; }
.kind { display: inline-block; font-size: 11px; color: #64748b;
        background: #f1f5f9; border-radius: 0; padding: 1px 6px;
        margin-right: 6px; }
.target { margin-left: 8px; font-size: 11px; color: #6b7280; }
@media (max-width: 1100px) {
  .cards { grid-template-columns: repeat(3, 1fr); }
}
</style>
