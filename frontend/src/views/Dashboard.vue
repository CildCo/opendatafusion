<template>
  <div class="dash">
    <header class="dash-head">
      <p class="lede">
        {{ welcome.text || "Default 工作区的数据流动、作业状态与待处理事项。" }}
      </p>
      <div class="clock">
        <span>本地时间</span>
        <strong>{{ clock }}</strong>
        <small>{{ dateLabel }}</small>
      </div>
    </header>

    <section class="ledger" aria-label="运营数字">
      <div v-for="s in primaryStats" :key="s.key" class="ledger-cell">
        <span class="cell-label">{{ s.label }}</span>
        <strong :class="{ alert: s.key === 'failed_24h' && s.value > 0 }">
          {{ s.value }}
        </strong>
        <span class="cell-note">{{ s.note }}</span>
      </div>
    </section>

    <div class="board">
      <section class="panel runs-panel">
        <header class="panel-head">
          <div>
            <h3>运行记录</h3>
            <span>按时间倒序，点击行进入运维中心</span>
          </div>
          <button class="text-action" type="button" @click="load">刷新</button>
        </header>
        <div class="filter-tabs">
          <button v-for="t in runTabs" :key="t.key" type="button"
                  :class="{ active: runFilter === t.key }"
                  @click="runFilter = t.key">
            {{ t.label }} <span>{{ t.count }}</span>
          </button>
        </div>
        <el-table :data="filteredRuns" size="small" v-loading="loading"
                  empty-text="当前筛选下没有运行记录"
                  @row-click="openRun">
          <el-table-column label="时间" width="104">
            <template #default="{ row }">
              <span class="mono">{{ timeOnly(row.started_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="flow" label="作业" min-width="180">
            <template #default="{ row }">
              <div class="name-cell">
                <span class="status-dot" :class="runClass(row.status)"></span>
                <span>{{ row.flow }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="96">
            <template #default="{ row }">
              <span class="state" :class="runClass(row.status)">
                {{ runLabel(row.status) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="in" label="输入" width="82" />
          <el-table-column prop="out" label="输出" width="82" />
          <el-table-column prop="err" label="错误" width="70" />
        </el-table>
      </section>

      <aside class="side">
        <section class="panel exception-panel">
          <header class="panel-head">
            <div>
              <h3>需要处理</h3>
              <span>{{ alerts.length }} 条未处理告警</span>
            </div>
            <button class="text-action" type="button"
                    @click="$router.push('/alerts')">全部</button>
          </header>
          <template v-if="exception">
            <div class="exception-copy">
              <span class="exception-mark" :class="alertClass(exception.severity)"></span>
              <div>
                <span class="exception-label">{{ alertLabel(exception.severity) }}</span>
                <h4>{{ exception.title }}</h4>
                <p v-if="exception.detail && Object.keys(exception.detail).length">
                  {{ alertDetail(exception) }}
                </p>
              </div>
            </div>
            <div class="exception-actions">
              <button class="inline-action" type="button"
                      @click="$router.push('/ops')">打开运维中心 →</button>
              <button v-if="alerts.length > 1" class="quiet-action"
                      type="button" @click="$router.push('/alerts')">
                另有 {{ alerts.length - 1 }} 条
              </button>
            </div>
          </template>
          <div v-else class="quiet-state">没有未处理告警</div>
        </section>

        <section class="panel schedule-panel">
          <header class="panel-head">
            <div>
              <h3>计划窗口</h3>
              <span>已启用 cron 的管道</span>
            </div>
            <button class="text-action" type="button"
                    @click="$router.push('/pipelines')">全部</button>
          </header>
          <div v-if="scheduled.length" class="schedule-list">
            <router-link v-for="p in scheduled" :key="p.id"
                         :to="`/pipelines/${p.id}`" class="schedule-row">
              <span class="schedule-name">{{ p.name }}</span>
              <span class="mono">{{ p.cron }}</span>
            </router-link>
          </div>
          <div v-else class="quiet-state">暂无启用调度的管道</div>
        </section>
      </aside>
    </div>

    <footer class="inventory-line">
      <span>资产概览</span>
      <span v-for="s in secondaryStats" :key="s.key">
        {{ s.label }} <b>{{ s.value }}</b>
      </span>
    </footer>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { useRouter } from "vue-router";
import { api, errMsg } from "../api";

const router = useRouter();
const loading = ref(false);
const alerts = ref([]);
const recent = ref([]);
const scheduled = ref([]);
const welcome = ref({ title: "", text: "" });
const now = ref(new Date());
const runFilter = ref("all");
let timer = null;

const stats = ref([
  { key: "running_runs", label: "运行中", value: 0, note: "当前作业" },
  { key: "failed_24h", label: "今日失败", value: 0, note: "最近 24 小时" },
  { key: "open_alerts", label: "未处理告警", value: 0, note: "需要关注" },
  { key: "runs_24h", label: "24h 运行", value: 0, note: "全部流程" },
  { key: "datasources", label: "数据源", value: 0, note: "已连接" },
  { key: "flows", label: "流程", value: 0, note: "已定义" },
  { key: "interfaces", label: "接口", value: 0, note: "已发布" },
  { key: "quality_rules", label: "质量规则", value: 0, note: "已启用" },
]);

const primaryStats = computed(() => stats.value.slice(0, 4));
const secondaryStats = computed(() => stats.value.slice(4));
const exception = computed(() => alerts.value[0] || null);

const clock = computed(() => now.value.toLocaleTimeString("zh-CN", {
  hour12: false,
}));
const dateLabel = computed(() => now.value.toLocaleDateString("zh-CN", {
  year: "numeric", month: "2-digit", day: "2-digit",
}));

const runTabs = computed(() => {
  const count = (status) => status === "all"
    ? recent.value.length
    : recent.value.filter((r) => r.status === status).length;
  return [
    { key: "all", label: "全部", count: count("all") },
    { key: 1, label: "运行中", count: count(1) },
    { key: 3, label: "失败", count: count(3) },
    { key: 2, label: "成功", count: count(2) },
  ];
});

const filteredRuns = computed(() => runFilter.value === "all"
  ? recent.value
  : recent.value.filter((r) => r.status === runFilter.value));

function runClass(s) {
  return s === 2 ? "ok" : s === 3 ? "bad" : s === 1 ? "warn" : "neutral";
}
function runLabel(s) {
  return { 0: "排队", 1: "运行中", 2: "成功", 3: "失败", 4: "跳过" }[s] || s;
}
function alertClass(severity) {
  return severity === "critical" ? "bad" : "warn";
}
function alertLabel(severity) {
  return severity === "critical" ? "严重" : "警告";
}
function fmtSec(v) {
  if (v === null || v === undefined) return "-";
  if (v < 60) return v + "s";
  if (v < 3600) return Math.round(v / 60) + "m";
  return (v / 3600).toFixed(1) + "h";
}
function alertDetail(a) {
  const d = a.detail || {};
  if (d.message || d.error || d.impact) {
    return d.message || d.error || d.impact;
  }
  const parts = [];
  if (d.flow_id !== undefined) parts.push("流程 #" + d.flow_id);
  if (d.lag_s !== undefined) parts.push("滞后 " + fmtSec(d.lag_s));
  if (d.cursor_age_s !== undefined) {
    parts.push("游标年龄 " + fmtSec(d.cursor_age_s));
  }
  return parts.join(" · ") || "打开运维中心查看详情";
}
function timeOnly(value) {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value).slice(11, 19);
  return d.toLocaleTimeString("zh-CN", { hour12: false });
}
function openRun(row) {
  if (row.asset_id) {
    router.push(`/pipelines/${row.asset_id}`);
    return;
  }
  router.push("/ops");
}

async function load() {
  loading.value = true;
  try {
    const d = await api.get("/dashboard");
    stats.value = stats.value.map((s) => ({ ...s, value: d[s.key] ?? 0 }));
    recent.value = d.recent_runs || [];
    alerts.value = await api.get("/alerts?status=open");
    const pipelines = await api.get("/pipelines");
    scheduled.value = (pipelines || [])
      .filter((p) => p.cron && p.enabled !== false).slice(0, 4);
    const portal = await api.get("/portal");
    welcome.value = { title: portal.welcome_title || "",
                      text: portal.welcome_text || "" };
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  load();
  timer = setInterval(() => { now.value = new Date(); }, 1000);
});
onBeforeUnmount(() => clearInterval(timer));
</script>

<style scoped>
.dash {
  padding: 22px 26px 34px;
  min-height: 100%;
}

.dash-head {
  position: relative;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  border-bottom: 1px solid var(--odf-rule);
  padding-bottom: 13px;
}

.dash-head::after {
  content: "";
  position: absolute;
  left: 0;
  bottom: -1px;
  width: 96px;
  height: 2px;
  background: var(--odf-primary);
}

.lede {
  margin: 0;
  max-width: 68ch;
  color: #4b5563;
  font-size: 12px;
  line-height: 1.6;
}

.clock {
  text-align: right;
  flex: none;
}

.clock span {
  display: block;
  color: var(--odf-muted);
  font-size: 9px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.clock strong {
  display: block;
  margin-top: 2px;
  font-size: 24px;
  font-weight: 600;
  letter-spacing: -0.03em;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.clock small {
  display: block;
  margin-top: 3px;
  color: var(--odf-muted);
  font-family: var(--odf-mono);
  font-size: 9px;
}

.ledger {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  border: 1px solid var(--odf-rule);
  border-top: 0;
  background: var(--odf-rule);
  gap: 1px;
  margin-bottom: 16px;
}

.ledger-cell {
  background: #fff;
  padding: 13px 14px 12px;
  min-width: 0;
}

.cell-label {
  display: block;
  color: var(--odf-muted);
  font-size: 10px;
  font-weight: 500;
}

.ledger-cell strong {
  display: block;
  margin-top: 5px;
  font-size: 31px;
  line-height: 0.95;
  letter-spacing: -0.05em;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}

.ledger-cell strong.alert {
  color: var(--odf-red);
}

.cell-note {
  display: block;
  margin-top: 5px;
  color: var(--odf-muted);
  font-size: 10px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.board {
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(270px, 0.9fr);
  gap: 14px;
  align-items: start;
}

.panel {
  background: #fff;
  border: 1px solid var(--odf-rule);
  min-width: 0;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--odf-rule);
}

.panel-head h3 {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.panel-head span {
  display: block;
  margin-top: 2px;
  color: var(--odf-muted);
  font-size: 10px;
}

.text-action {
  border: 0;
  background: transparent;
  padding: 0;
  color: var(--odf-accent);
  font: inherit;
  font-size: 10px;
  cursor: pointer;
  white-space: nowrap;
}

.text-action:hover {
  text-decoration: underline;
  text-underline-offset: 3px;
}

.filter-tabs {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 6px 12px;
  border-bottom: 1px solid var(--odf-rule-soft);
}

.filter-tabs button {
  border: 0;
  background: transparent;
  color: var(--odf-muted);
  font: inherit;
  font-size: 10px;
  padding: 4px 7px;
  cursor: pointer;
}

.filter-tabs button span {
  margin-left: 3px;
  color: #9ca3af;
  font-family: var(--odf-mono);
  font-size: 9px;
}

.filter-tabs button.active {
  background: var(--odf-ink);
  color: #fff;
}

.filter-tabs button.active span {
  color: #d1d5db;
}

.name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
  flex: none;
  background: #9ca3af;
}

.status-dot.ok { background: var(--odf-green); }
.status-dot.warn { background: var(--odf-amber); }
.status-dot.bad { background: var(--odf-red); }

.state { font-size: 10px; font-weight: 500; }
.state.ok { color: var(--odf-green); }
.state.warn { color: var(--odf-amber); }
.state.bad { color: var(--odf-red); }
.state.neutral { color: var(--odf-muted); }

.side {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.exception-copy {
  display: flex;
  gap: 11px;
  padding: 14px;
}

.exception-mark {
  width: 8px;
  height: 8px;
  margin-top: 5px;
  flex: none;
  background: var(--odf-amber);
}

.exception-mark.bad {
  background: var(--odf-red);
}

.exception-label {
  color: var(--odf-red);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.08em;
}

.exception-copy h4 {
  margin: 4px 0 0;
  font-size: 14px;
  line-height: 1.35;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.exception-copy p {
  margin: 6px 0 0;
  color: var(--odf-muted);
  font-size: 11px;
  line-height: 1.55;
}

.exception-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 9px 14px;
  border-top: 1px solid var(--odf-rule-soft);
}

.inline-action {
  border: 0;
  background: transparent;
  padding: 0;
  color: var(--odf-accent);
  font: inherit;
  font-size: 10px;
  cursor: pointer;
}

.quiet-action {
  border: 0;
  background: transparent;
  color: var(--odf-muted);
  font: inherit;
  font-size: 10px;
  cursor: pointer;
}

.schedule-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  padding: 9px 14px;
  border-bottom: 1px solid var(--odf-rule-soft);
  color: var(--odf-ink);
  text-decoration: none;
}

.schedule-row:last-child { border-bottom: 0; }

.schedule-row:hover {
  background: var(--odf-accent-soft);
}

.schedule-name {
  font-size: 11px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.schedule-row .mono {
  flex: none;
  color: var(--odf-muted);
  font-size: 9px;
}

.quiet-state {
  padding: 22px 14px;
  color: var(--odf-muted);
  font-size: 11px;
}

.inventory-line {
  display: flex;
  align-items: baseline;
  gap: 18px;
  margin-top: 14px;
  padding-top: 10px;
  border-top: 1px solid var(--odf-rule);
  color: var(--odf-muted);
  font-size: 10px;
}

.inventory-line > span:first-child {
  color: var(--odf-ink);
  font-weight: 600;
}

.inventory-line b {
  color: var(--odf-ink);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.mono {
  font-family: var(--odf-mono);
  font-size: 10px;
  color: var(--odf-muted);
}

@media (max-width: 980px) {
  .board {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .dash { padding: 16px 14px 26px; }
  .dash-head { display: block; }
  .clock { text-align: left; margin-top: 12px; }
  .ledger { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .inventory-line { flex-wrap: wrap; gap: 9px 14px; }
}
</style>
