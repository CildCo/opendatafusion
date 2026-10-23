<template>
  <div class="ops-page">
    <div class="toolbar">
      <el-tag size="small" effect="plain">{{ projectLabel }}</el-tag>
      <div class="spacer" />
      <span class="updated">更新于 {{ updated || "-" }}</span>
      <el-switch v-model="auto" active-text="自动刷新" size="small" />
      <el-button size="small" :loading="loading" @click="load">刷新</el-button>
    </div>

    <div class="cards">
      <div v-for="c in cards" :key="c.label" class="card"
           :class="c.tone">
        <div class="card-value">{{ c.value }}</div>
        <div class="card-label">{{ c.label }}</div>
      </div>
    </div>

    <el-card shadow="never" class="panel">
      <el-tabs v-model="tab">
        <el-tab-pane label="概览" name="overview">
          <div class="section-title">最近失败任务</div>
          <el-table :data="summary.recent_failures || []" size="small"
                    empty-text="没有失败任务">
            <el-table-column prop="id" label="任务" width="80" />
            <el-table-column prop="target_name" label="对象" min-width="140" />
            <el-table-column prop="target_type" label="类型" width="90" />
            <el-table-column prop="attempts" label="尝试" width="70" />
            <el-table-column prop="last_error" label="错误" min-width="260"
                             show-overflow-tooltip />
            <el-table-column prop="finished_at" label="结束时间" width="180">
              <template #default="{ row }">{{ fmt(row.finished_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="90">
              <template #default="{ row }">
                <el-button v-if="canOperate" link type="primary"
                           @click="retry(row)">
                  重试
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="任务" name="jobs">
          <div class="filters">
            <el-select v-model="jobStatus" clearable placeholder="全部状态"
                       size="small" style="width: 140px" @change="loadJobs">
              <el-option v-for="s in statuses" :key="s" :value="s"
                         :label="s" />
            </el-select>
            <el-button size="small" @click="loadJobs">查询</el-button>
          </div>
          <el-table :data="jobs" size="small" empty-text="没有任务">
            <el-table-column prop="id" label="任务" width="80" />
            <el-table-column prop="target_name" label="对象" min-width="160" />
            <el-table-column prop="asset_type" label="资产类型" width="100" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="jobTone(row.status)">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="尝试" width="90">
              <template #default="{ row }">
                {{ row.attempts }}/{{ row.max_attempts }}
              </template>
            </el-table-column>
            <el-table-column prop="last_error" label="错误" min-width="220"
                             show-overflow-tooltip />
            <el-table-column prop="run_at" label="计划时间" width="180">
              <template #default="{ row }">{{ fmt(row.run_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="90">
              <template #default="{ row }">
                <el-button v-if="canOperate && row.status === 'failed'"
                           link type="primary" @click="retry(row)">
                  重试
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="告警" name="alerts">
          <div class="filters">
            <el-select v-model="alertStatus" clearable placeholder="全部状态"
                       size="small" style="width: 130px"
                       @change="loadAlerts">
              <el-option value="open" label="open" />
              <el-option value="acked" label="acked" />
              <el-option value="closed" label="closed" />
            </el-select>
            <el-select v-model="alertSeverity" clearable placeholder="全部级别"
                       size="small" style="width: 130px"
                       @change="loadAlerts">
              <el-option value="critical" label="critical" />
              <el-option value="warning" label="warning" />
              <el-option value="info" label="info" />
            </el-select>
          </div>
          <el-table :data="alerts" size="small" empty-text="没有告警">
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column label="级别" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="severityTone(row.severity)">
                  {{ row.severity }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="title" label="标题" min-width="240" />
            <el-table-column prop="status" label="状态" width="90" />
            <el-table-column prop="created_at" label="产生时间" width="180">
              <template #default="{ row }">{{ fmt(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="130">
              <template #default="{ row }">
                <el-button v-if="canOperate && row.status === 'open'" link
                           @click="ack(row)">确认</el-button>
                <el-button v-if="canOperate && row.status !== 'closed'" link
                           type="danger" @click="close(row)">关闭</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="健康" name="health">
          <div class="filters">
            <el-tag v-for="(v, k) in health.counts" :key="k" size="small"
                    :type="healthTone(k)">
              {{ k }} {{ v }}
            </el-tag>
            <el-button size="small" @click="loadHealth">刷新</el-button>
          </div>
          <div class="section-title">流程健康</div>
          <el-table :data="health.flows || []" size="small"
                    empty-text="没有流程">
            <el-table-column prop="name" label="流程" min-width="180" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="healthTone(row.status)">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="延迟" width="110">
              <template #default="{ row }">
                {{ row.lag_s == null ? "-" : row.lag_s + "s" }}
              </template>
            </el-table-column>
            <el-table-column prop="empty_rounds" label="空轮次" width="90" />
            <el-table-column label="游标年龄" width="120">
              <template #default="{ row }">
                {{ row.cursor_age_s == null ? "-" : row.cursor_age_s + "s" }}
              </template>
            </el-table-column>
          </el-table>
          <div class="section-title" style="margin-top: 16px">最近健康事件</div>
          <el-table :data="health.events || []" size="small"
                    empty-text="没有健康事件">
            <el-table-column prop="flow_id" label="流程" width="90" />
            <el-table-column prop="kind" label="类型" width="130" />
            <el-table-column label="级别" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="severityTone(row.severity)">
                  {{ row.severity }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="at" label="时间" width="180">
              <template #default="{ row }">{{ fmt(row.at) }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="接口调用" name="api">
          <el-table :data="apiStats" size="small" empty-text="暂无调用">
            <el-table-column prop="api_name" label="接口" min-width="180" />
            <el-table-column prop="key" label="Key" min-width="200" />
            <el-table-column prop="ak" label="AK" min-width="160" />
            <el-table-column prop="count" label="调用" width="80" />
            <el-table-column prop="errors" label="错误" width="80" />
            <el-table-column prop="avg_ms" label="平均耗时" width="100" />
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="时间线" name="timeline">
          <el-timeline v-if="timeline.length">
            <el-timeline-item v-for="(x, i) in timeline" :key="i"
                              :timestamp="fmt(x.at)"
                              :type="severityTone(x.severity)">
              <span class="kind">{{ x.kind }}</span>
              {{ x.title }}
              <span class="target">{{ x.target }}</span>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="没有运维事件" />
        </el-tab-pane>

        <el-tab-pane v-if="isAdmin" label="审计" name="audit">
          <div class="filters">
            <el-input v-model="auditActor" size="small" placeholder="操作人"
                      clearable style="width: 140px" />
            <el-input v-model="auditAction" size="small" placeholder="动作"
                      clearable style="width: 160px" />
            <el-input v-model="auditQ" size="small" placeholder="关键字"
                      clearable style="width: 180px" />
            <el-button size="small" @click="loadAudit">查询</el-button>
          </div>
          <el-table :data="audit" size="small" empty-text="没有审计记录">
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="actor" label="操作人" width="120" />
            <el-table-column prop="action" label="动作" width="170" />
            <el-table-column prop="target" label="对象" width="120" />
            <el-table-column prop="detail" label="详情" min-width="260"
                             show-overflow-tooltip>
              <template #default="{ row }">
                {{ JSON.stringify(row.detail) }}
              </template>
            </el-table-column>
            <el-table-column prop="at" label="时间" width="180">
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
import { api, errMsg, getRole } from "../api";

const role = getRole() || "viewer";
const isAdmin = role === "admin";
const canOperate = ["editor", "approver", "admin"].includes(role);
const projectLabel = "项目 1";
const tab = ref("overview");
const summary = ref({});
const jobs = ref([]);
const alerts = ref([]);
const health = ref({ flows: [], counts: {}, events: [] });
const timeline = ref([]);
const apiStats = ref([]);
const audit = ref([]);
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
    { label: "排队任务", value: j.queued || 0, tone: "blue" },
    { label: "运行中", value: j.running || 0, tone: "blue" },
    { label: "失败任务", value: j.failed || 0, tone: "red" },
    { label: "未处理告警", value: a.open || 0, tone: "amber" },
    { label: "异常流程", value: unhealthy, tone: "amber" },
    { label: "资产总数",
      value: Object.values(assets).reduce((x, y) => x + y, 0), tone: "" },
  ];
});

function fmt(v) {
  if (!v) return "-";
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? v : d.toLocaleString("zh-CN");
}

function jobTone(s) {
  return { failed: "danger", running: "warning", queued: "info",
           success: "success" }[s] || "info";
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
      `重新执行任务 #${row.id}（${row.target_name || "-"}）？`, "重试确认");
    await api.post(`/ops/jobs/${row.id}/retry`);
    ElMessage.success("已重新排队");
    await load();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

async function ack(row) {
  try {
    await api.post(`/ops/alerts/${row.id}/ack`);
    ElMessage.success("已确认");
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function close(row) {
  try {
    await ElMessageBox.confirm(`关闭告警「${row.title}」？`, "关闭确认");
    await api.post(`/ops/alerts/${row.id}/close`);
    ElMessage.success("已关闭");
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
watch(tab, (t) => {
  if (t === "audit") loadAudit();
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
