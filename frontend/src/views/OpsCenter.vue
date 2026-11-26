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
                    :empty-text="t('ops.emptyFailures')"
                    @row-click="openJob">
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
                           @click.stop="retry(row)">
                  {{ t("ops.retry") }}
                </el-button>
                <el-button v-if="targetPath(row)" link @click.stop="openTarget(row)">
                  {{ t("ops.view") }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="t('ops.tabHealth')" name="health">
          <div class="filters">
            <el-select v-model="healthDays" size="small" style="width: 120px"
                       @change="loadHealth">
              <el-option :value="7" :label="t('ops.matrix7')" />
              <el-option :value="30" :label="t('ops.matrix30')" />
              <el-option :value="90" :label="t('ops.matrix90')" />
            </el-select>
            <span class="updated">{{ t("ops.healthHint") }}</span>
            <div class="spacer" />
            <el-button size="small" :loading="healthLoading"
                       @click="loadHealth">{{ t("ops.refresh") }}</el-button>
          </div>
          <el-table :data="health.items || []" size="small"
                    :empty-text="t('ops.healthEmpty')"
                    v-loading="healthLoading">
            <el-table-column prop="name" :label="t('ops.target')"
                             min-width="190">
              <template #default="{ row }">
                <b>{{ row.name }}</b>
                <div class="muted">{{ row.type }}</div>
              </template>
            </el-table-column>
            <el-table-column :label="t('ops.healthScore')" width="120">
              <template #default="{ row }">
                <div class="health-score">
                  <el-progress :percentage="row.health_score"
                               :stroke-width="6" :show-text="false"
                               :color="healthColor(row.health_score)" />
                  <b>{{ row.health_score }}</b>
                </div>
              </template>
            </el-table-column>
            <el-table-column :label="t('ops.successRate')" width="100">
              <template #default="{ row }">
                {{ row.success_rate === null ? "-" : row.success_rate + "%" }}
              </template>
            </el-table-column>
            <el-table-column :label="t('ops.avgDuration')" width="110">
              <template #default="{ row }">
                {{ row.avg_duration_seconds === null ? "-"
                  : row.avg_duration_seconds + "s" }}
              </template>
            </el-table-column>
            <el-table-column :label="t('ops.p95Duration')" width="110">
              <template #default="{ row }">
                {{ row.p95_duration_seconds === null ? "-"
                  : row.p95_duration_seconds + "s" }}
              </template>
            </el-table-column>
            <el-table-column prop="sla_breaches"
                             :label="t('ops.slaBreaches')" width="100" />
            <el-table-column prop="priority" :label="t('ops.priority')"
                             width="90" />
            <el-table-column :label="t('ops.lastStatus')" width="100">
              <template #default="{ row }">
                <el-tag v-if="row.last_status" size="small"
                        :type="jobTone(row.last_status)">
                  {{ row.last_status }}
                </el-tag>
                <span v-else class="muted">-</span>
              </template>
            </el-table-column>
            <el-table-column :label="t('ops.lastRun')" width="180">
              <template #default="{ row }">{{ fmt(row.last_run_at) }}</template>
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
          <el-table :data="jobs" size="small" :empty-text="t('ops.emptyJobs')"
                    @row-click="openJob">
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
            <el-table-column :label="t('ops.actions')" width="190">
              <template #default="{ row }">
                <el-button v-if="canOperate && row.status === 'failed'"
                           link type="primary" @click.stop="retry(row)">
                  {{ t("ops.retry") }}
                </el-button>
                <el-button v-if="canOperate
                               && ['queued', 'running'].includes(row.status)"
                           link type="warning" @click.stop="cancel(row)">
                  {{ t("ops.cancel") }}
                </el-button>
                <el-button v-if="targetPath(row)" link @click.stop="openTarget(row)">
                  {{ t("ops.view") }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="t('ops.tabMatrix')" name="matrix">
          <div class="filters">
            <el-select v-model="matrixDays" size="small" style="width: 120px"
                       @change="loadMatrix">
              <el-option :value="7" :label="t('ops.matrix7')" />
              <el-option :value="14" :label="t('ops.matrix14')" />
              <el-option :value="30" :label="t('ops.matrix30')" />
            </el-select>
            <span class="updated">{{ t("ops.matrixHint") }}</span>
            <div class="spacer" />
            <el-button size="small" :loading="matrixLoading"
                       @click="loadMatrix">{{ t("ops.refresh") }}</el-button>
          </div>
          <el-table :data="matrix.rows" size="small"
                    :empty-text="t('ops.matrixEmpty')" border
                    v-loading="matrixLoading">
            <el-table-column prop="name" :label="t('ops.target')"
                             min-width="190" fixed="left">
              <template #default="{ row }">
                <b>{{ row.name }}</b>
                <div class="muted">{{ row.asset_type }}</div>
              </template>
            </el-table-column>
            <el-table-column v-for="day in matrix.days" :key="day"
                             :label="day.slice(5)" width="82"
                             align="center">
              <template #default="{ row }">
                <el-tooltip v-if="row.cells[day]" placement="top"
                            :content="`${row.cells[day].count} ${t('ops.matrixRuns')}`">
                  <span class="matrix-cell" :class="row.cells[day].status">
                    {{ row.cells[day].count }}
                  </span>
                </el-tooltip>
                <span v-else class="matrix-empty">·</span>
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

        <el-tab-pane :label="t('ops.tabPerf')" name="perf">
          <div class="filters">
            <el-select v-model="perfDays" size="small" style="width: 120px"
                       @change="loadPerf">
              <el-option :value="7" :label="t('ops.perf7')" />
              <el-option :value="30" :label="t('ops.perf30')" />
            </el-select>
            <el-button size="small" @click="loadPerf">{{ t("ops.query") }}</el-button>
            <span class="updated">{{ t("ops.perfHint") }}</span>
          </div>
          <div class="perf-cards">
            <div class="perf-card">
              <b>{{ perf.total || 0 }}</b><span>{{ t("ops.perfTotal") }}</span>
            </div>
            <div class="perf-card">
              <b>{{ perf.p50_ms || 0 }}</b><span>{{ t("ops.perfP50") }}</span>
            </div>
            <div class="perf-card">
              <b>{{ perf.p95_ms || 0 }}</b><span>{{ t("ops.perfP95") }}</span>
            </div>
            <div class="perf-card">
              <b>{{ perf.avg_ms || 0 }}</b><span>{{ t("ops.perfAvg") }}</span>
            </div>
            <div class="perf-card">
              <b class="danger">{{ perf.errors || 0 }}</b>
              <span>{{ t("ops.perfErrors") }}</span>
            </div>
          </div>
          <div class="section-title">{{ t("ops.perfBySource") }}</div>
          <el-table :data="perf.by_source || []" size="small"
                    :empty-text="t('ops.perfEmpty')">
            <el-table-column prop="source" :label="t('ops.perfSource')" min-width="120" />
            <el-table-column prop="count" :label="t('ops.perfCount')" width="90" />
            <el-table-column prop="errors" :label="t('ops.error')" width="90" />
            <el-table-column prop="avg_ms" :label="t('ops.perfAvgMs')" width="110" />
          </el-table>
          <div class="section-title">{{ t("ops.perfByDatasource") }}</div>
          <el-table :data="perf.by_datasource || []" size="small"
                    :empty-text="t('ops.perfEmpty')">
            <el-table-column prop="datasource_name" :label="t('ops.perfDatasource')" min-width="180">
              <template #default="{ row }">{{ row.datasource_name || "-" }}</template>
            </el-table-column>
            <el-table-column prop="count" :label="t('ops.perfCount')" width="90" />
            <el-table-column prop="errors" :label="t('ops.error')" width="90" />
            <el-table-column prop="avg_ms" :label="t('ops.perfAvgMs')" width="110" />
          </el-table>
          <div class="section-title">{{ t("ops.perfSlowest") }}</div>
          <el-table :data="perf.slowest || []" size="small"
                    :empty-text="t('ops.perfEmpty')">
            <el-table-column prop="ms" label="ms" width="80" />
            <el-table-column prop="source" :label="t('ops.perfSource')" width="110" />
            <el-table-column prop="datasource_name" :label="t('ops.perfDatasource')" width="140" />
            <el-table-column prop="sql_preview" :label="t('ops.perfSql')" min-width="300"
                             show-overflow-tooltip />
            <el-table-column prop="actor" :label="t('ops.perfActor')" width="120" />
            <el-table-column :label="t('ops.perfTime')" width="180">
              <template #default="{ row }">{{ fmt(row.created_at) }}</template>
            </el-table-column>
          </el-table>
          <div class="section-title">{{ t("ops.perfByActor") }}</div>
          <el-table :data="perf.by_actor || []" size="small"
                    :empty-text="t('ops.perfEmpty')">
            <el-table-column prop="actor" :label="t('ops.perfActor')" min-width="140" />
            <el-table-column prop="count" :label="t('ops.perfCount')" width="90" />
            <el-table-column prop="errors" :label="t('ops.error')" width="90" />
            <el-table-column prop="avg_ms" :label="t('ops.perfAvgMs')" width="110" />
          </el-table>
          <div class="section-title">{{ t("ops.perfTemplates") }}</div>
          <el-table :data="perf.templates || []" size="small"
                    :empty-text="t('ops.perfEmpty')">
            <el-table-column prop="statement" :label="t('ops.perfStatement')"
                             min-width="320" show-overflow-tooltip />
            <el-table-column prop="count" :label="t('ops.perfCount')" width="90" />
            <el-table-column prop="errors" :label="t('ops.error')" width="90" />
            <el-table-column prop="avg_ms" :label="t('ops.perfAvgMs')" width="110" />
            <el-table-column prop="slowest_ms" :label="t('ops.perfSlowestMs')"
                             width="130" />
            <el-table-column prop="variants" :label="t('ops.perfVariants')"
                             width="110" />
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="t('ops.tabCalendar')" name="calendar">
          <div class="filters">
            <span class="updated">{{ t("ops.calendarHint") }}</span>
            <div class="spacer" />
            <el-button size="small" :loading="matrixLoading"
                       @click="loadMatrix">{{ t("ops.refresh") }}</el-button>
          </div>
          <div class="calendar-grid">
            <div v-for="day in calendarCells" :key="day.key"
                 class="calendar-cell" :class="[day.status, { empty: day.blank }]">
              <template v-if="!day.blank">
                <b>{{ day.label }}</b>
                <span v-if="day.total">
                  {{ day.total }} {{ t("ops.calendarJobs") }}
                </span>
                <span v-else class="muted">-</span>
              </template>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane :label="t('ops.tabSchedules')" name="schedules">
          <div class="filters">
            <span class="updated">{{ t("ops.schedulesHint") }}</span>
            <div class="spacer" />
            <el-button size="small" :loading="scheduleLoading"
                       @click="loadSchedules">{{ t("ops.refresh") }}</el-button>
          </div>
          <el-table :data="schedules" size="small"
                    :empty-text="t('ops.emptySchedules')"
                    v-loading="scheduleLoading">
            <el-table-column prop="name" :label="t('ops.target')"
                             min-width="190" />
            <el-table-column prop="type" :label="t('ops.type')" width="100" />
            <el-table-column prop="cron" :label="t('ops.cron')" width="140" />
            <el-table-column :label="t('ops.nextRun')" width="180">
              <template #default="{ row }">{{ fmt(row.next_run) }}</template>
            </el-table-column>
            <el-table-column :label="t('ops.lastStatus')" width="110">
              <template #default="{ row }">
                <el-tag v-if="row.last_status" size="small"
                        :type="jobTone(row.last_status)">
                  {{ row.last_status }}
                </el-tag>
                <span v-else class="muted">-</span>
              </template>
            </el-table-column>
            <el-table-column :label="t('ops.lastRun')" width="180">
              <template #default="{ row }">{{ fmt(row.last_run_at) }}</template>
            </el-table-column>
            <el-table-column :label="t('ops.enabled')" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="row.enabled ? 'success' : 'info'">
                  {{ row.enabled ? t("ops.on") : t("ops.off") }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="t('ops.actions')" width="90">
              <template #default="{ row }">
                <el-button link @click.stop="openTarget(row)">
                  {{ t("ops.view") }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="t('ops.tabPolicies')" name="policies">
          <div class="filters">
            <span class="updated">{{ t("ops.policiesHint") }}</span>
            <div class="spacer" />
            <el-button size="small" :loading="policyLoading"
                       @click="loadPolicies">{{ t("ops.refresh") }}</el-button>
          </div>
          <el-table :data="policies" size="small"
                    :empty-text="t('ops.emptyPolicies')"
                    v-loading="policyLoading">
            <el-table-column prop="name" :label="t('ops.target')"
                             min-width="190" />
            <el-table-column prop="type" :label="t('ops.type')" width="100" />
            <el-table-column :label="t('ops.maxAttempts')" width="150">
              <template #default="{ row }">
                <el-input-number v-model="row.max_attempts" :min="1" :max="10"
                                 size="small" :controls="false"
                                 :disabled="!canOperate" style="width: 80px" />
              </template>
            </el-table-column>
            <el-table-column :label="t('ops.retryBackoff')" width="170">
              <template #default="{ row }">
                <el-input-number v-model="row.retry_backoff_seconds" :min="0"
                                 :max="3600" size="small" :controls="false"
                                 :disabled="!canOperate" style="width: 100px" />
                <span class="unit">{{ t("ops.seconds") }}</span>
              </template>
            </el-table-column>
            <el-table-column :label="t('ops.priority')" width="130">
              <template #default="{ row }">
                <el-input-number v-model="row.priority" :min="0" :max="100"
                                 size="small" :controls="false"
                                 :disabled="!canOperate" style="width: 80px" />
              </template>
            </el-table-column>
            <el-table-column :label="t('ops.maxDuration')" width="170">
              <template #default="{ row }">
                <el-input-number v-model="row.max_duration_seconds" :min="0"
                                 :max="86400" size="small" :controls="false"
                                 :disabled="!canOperate" style="width: 100px" />
                <span class="unit">{{ t("ops.seconds") }}</span>
              </template>
            </el-table-column>
            <el-table-column :label="t('ops.lastStatus')" width="110">
              <template #default="{ row }">
                <el-tag v-if="row.last_status" size="small"
                        :type="jobTone(row.last_status)">
                  {{ row.last_status }}
                </el-tag>
                <span v-else class="muted">-</span>
              </template>
            </el-table-column>
            <el-table-column :label="t('ops.actions')" width="110">
              <template #default="{ row }">
                <el-button v-if="canOperate" link type="primary"
                           :loading="row.saving" @click.stop="savePolicy(row)">
                  {{ t("ops.save") }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="t('ops.tabDead')" name="dead">
          <div class="filters">
            <el-select v-model="deadType" clearable size="small"
                       style="width: 170px" @change="loadDead"
                       :placeholder="t('ops.allTypes')">
              <el-option v-for="type in deadTypes" :key="type"
                         :value="type" :label="type" />
            </el-select>
            <span class="updated">{{ t("ops.deadIntro") }}</span>
            <div class="spacer" />
            <el-button size="small" type="primary"
                       :disabled="!deadSelected.length" @click="replayDead">
              {{ t("ops.deadSelected").replace("{n}", deadSelected.length) }}
            </el-button>
            <el-button size="small" @click="loadDead">{{ t("ops.refresh") }}</el-button>
          </div>
          <el-table :data="deadJobs" size="small"
                    :empty-text="t('ops.deadEmpty')"
                    @selection-change="deadSelected = $event">
            <el-table-column type="selection" width="42" />
            <el-table-column prop="id" :label="t('ops.job')" width="80" />
            <el-table-column prop="target_name" :label="t('ops.target')"
                             min-width="180" />
            <el-table-column prop="asset_type" :label="t('ops.assetType')"
                             width="120" />
            <el-table-column prop="attempts" :label="t('ops.attempts')"
                             width="90" />
            <el-table-column prop="last_error" :label="t('ops.error')"
                             min-width="240" show-overflow-tooltip />
            <el-table-column :label="t('ops.finishedAt')" width="180">
              <template #default="{ row }">{{ fmt(row.finished_at) }}</template>
            </el-table-column>
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

    <el-drawer v-model="detailOpen" :title="`Job #${detail.id || ''}`"
               size="680px">
      <div v-loading="detailLoading">
        <el-descriptions :column="2" border>
          <el-descriptions-item :label="t('ops.target')">
            {{ detail.target_name || "-" }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('ops.status')">
            <el-tag size="small" :type="jobTone(detail.status)">
              {{ detail.status }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="t('ops.attempts')">
            {{ detail.attempts }}/{{ detail.max_attempts }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('ops.retryBackoff')">
            {{ detail.retry_backoff_seconds }} {{ t("ops.seconds") }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('ops.createdAt')">
            {{ fmt(detail.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('ops.finishedAt')">
            {{ fmt(detail.finished_at) }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('ops.worker')" :span="2">
            {{ detail.locked_by || "-" }}
          </el-descriptions-item>
        </el-descriptions>
        <el-alert v-if="detail.last_error" :title="detail.last_error"
                  type="error" :closable="false" style="margin-top: 10px" />
        <div class="drawer-actions" v-if="canOperate">
          <el-button v-if="detail.status === 'failed'" size="small"
                     type="primary" @click="retry(detail)">
            {{ t("ops.retry") }}
          </el-button>
          <el-button v-if="['queued', 'running'].includes(detail.status)"
                     size="small" type="warning" @click="cancel(detail)">
            {{ t("ops.cancel") }}
          </el-button>
        </div>

        <h4>{{ t("ops.nodeRuns") }}</h4>
        <el-table :data="detail.nodes || []" size="small"
                  :empty-text="t('ops.noNodeRuns')">
          <el-table-column prop="node_id" :label="t('ops.node')" min-width="120" />
          <el-table-column prop="status" :label="t('ops.status')" width="90" />
          <el-table-column prop="in_num" :label="t('ops.inRows')" width="90" />
          <el-table-column prop="out_num" :label="t('ops.outRows')" width="90" />
          <el-table-column prop="ms" :label="t('ops.duration')" width="90" />
          <el-table-column prop="error" :label="t('ops.error')" min-width="160"
                           show-overflow-tooltip />
        </el-table>

        <h4>{{ t("ops.compareTitle") }}</h4>
        <p v-if="!compare.previous" class="muted">{{ t("ops.noPrevious") }}</p>
        <template v-else>
          <div class="compare-head">
            <span>{{ t("ops.previousJob") }} #{{ compare.previous.id }}</span>
            <span>{{ fmt(compare.previous.finished_at) }}</span>
            <span v-if="compare.totals">
              {{ t("ops.compareTotals") }}
              {{ compare.totals.previous_ms }} → {{ compare.totals.ms }} ms
            </span>
          </div>
          <el-table :data="compare.nodes || []" size="small">
            <el-table-column prop="node_id" :label="t('ops.node')"
                             min-width="120" />
            <el-table-column :label="t('ops.duration')" width="150">
              <template #default="{ row }">
                {{ row.ms }} ms
                <span v-if="row.ms_delta !== null && row.ms_delta !== undefined"
                      :class="row.ms_delta > 0 ? 'delta-up' : 'delta-down'">
                  ({{ row.ms_delta > 0 ? "+" : "" }}{{ row.ms_delta }})
                </span>
              </template>
            </el-table-column>
            <el-table-column :label="t('ops.outRows')" width="150">
              <template #default="{ row }">
                {{ row.out_num }}
                <span v-if="row.out_delta !== null && row.out_delta !== undefined"
                      :class="row.out_delta > 0 ? 'delta-up' : 'delta-down'">
                  ({{ row.out_delta > 0 ? "+" : "" }}{{ row.out_delta }})
                </span>
              </template>
            </el-table-column>
          </el-table>
        </template>
      </div>
    </el-drawer>
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
const timeline = ref([]);
const apiStats = ref([]);
const perf = ref({});
const deadJobs = ref([]);
const deadSelected = ref([]);
const deadType = ref("");
const deadTypes = ["pipeline", "model", "pipeline_backfill",
                   "dashboard_report", "lakehouse_maintenance"];
const matrix = ref({ days: [], rows: [] });
const matrixDays = ref(7);
const matrixLoading = ref(false);
const perfDays = ref(7);
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
const schedules = ref([]);
const scheduleLoading = ref(false);
const policies = ref([]);
const health = ref({ items: [] });
const healthLoading = ref(false);
const healthDays = ref(30);
const calendarCells = computed(() => {
  const days = matrix.value.days || [];
  const cells = [];
  if (days.length) {
    const first = new Date(days[0] + "T00:00:00");
    for (let i = 0; i < first.getDay(); i += 1) {
      cells.push({ key: "blank-" + i, blank: true });
    }
  }
  for (const key of days) {
    let total = 0;
    let status = "";
    const order = ["failed", "running", "queued", "success", "skipped",
                   "cancelled"];
    const seen = new Set();
    for (const row of matrix.value.rows || []) {
      const cell = (row.cells || {})[key];
      if (!cell) continue;
      total += cell.count;
      seen.add(cell.status);
    }
    status = order.find((name) => seen.has(name)) || "";
    cells.push({ key, label: key.slice(5), total, status });
  }
  return cells;
});
const policyLoading = ref(false);
const detailOpen = ref(false);
const detailLoading = ref(false);
const detail = ref({});
const compare = ref({ previous: null, nodes: [], totals: null });
let timer = null;

const cards = computed(() => {
  const j = summary.value.jobs || {};
  const a = summary.value.alerts || {};
  const assets = summary.value.assets || {};
  return [
    { label: t("ops.cardQueued"), value: j.queued || 0, tone: "blue",
      values: hourly() },
    { label: t("ops.cardRunning"), value: j.running || 0, tone: "blue" },
    { label: t("ops.cardFailed"), value: j.failed || 0, tone: "red",
      values: hourly("failed") },
    { label: t("ops.cardOpenAlerts"), value: a.open || 0, tone: "amber" },
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
  const type = row.asset_type || row.target_type || row.type || "";
  return { pipeline: "/pipelines", api: "/apis",
           dashboard: "/dashboards", app: "/apps", dataset: "/datasets",
           metric: "/metrics", model: "/models", lakehouse: "/lakehouse" }[type] || "";
}

function openTarget(row) {
  const base = targetPath(row);
  if ((row.target_type || row.asset_type) === "lakehouse") {
    router.push(base);
    return;
  }
  const assetId = row.asset_id || row.target_id;
  router.push(assetId ? `${base}/${assetId}` : base);
}
function severityTone(s) {
  return { critical: "danger", warning: "warning", info: "info",
           ok: "success" }[s] || "info";
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
async function loadTimeline() {
  timeline.value = await api.get("/ops/timeline");
}
async function loadApiStats() {
  apiStats.value = await api.get("/api-stats");
}
async function loadMatrix() {
  matrixLoading.value = true;
  try {
    matrix.value = await api.get(`/ops/run-matrix?days=${matrixDays.value}`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    matrixLoading.value = false;
  }
}

async function loadDead() {
  try {
    const query = deadType.value
      ? `?asset_type=${encodeURIComponent(deadType.value)}` : "";
    deadJobs.value = await api.get("/ops/dead-letters" + query);
    deadSelected.value = [];
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function replayDead() {
  try {
    await ElMessageBox.confirm(
      t("ops.deadSelected").replace("{n}", deadSelected.value.length),
      t("ops.tabDead"));
    const result = await api.post("/ops/dead-letters/replay",
      { ids: deadSelected.value.map((row) => row.id) });
    ElMessage.success(
      t("ops.deadReplayed").replace("{n}", result.replayed.length));
    if (result.skipped.length) {
      ElMessage.warning(
        t("ops.deadSkipped").replace("{n}", result.skipped.length));
    }
    await loadDead();
    await loadSummary();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

async function loadPerf() {
  try {
    perf.value = await api.get(`/query-runs/summary?days=${perfDays.value}`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
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
      loadSummary(), loadJobs(), loadAlerts(),
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

async function loadSchedules() {
  scheduleLoading.value = true;
  try {
    schedules.value = await api.get("/ops/schedules");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    scheduleLoading.value = false;
  }
}

async function loadHealth() {
  healthLoading.value = true;
  try {
    health.value = await api.get(`/ops/run-health?days=${healthDays.value}`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    healthLoading.value = false;
  }
}

function healthColor(score) {
  if (score >= 90) return "#15803d";
  if (score >= 70) return "#2563eb";
  if (score >= 50) return "#d97706";
  return "#dc2626";
}

async function loadPolicies() {
  policyLoading.value = true;
  try {
    policies.value = await api.get("/ops/run-policies");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    policyLoading.value = false;
  }
}

async function savePolicy(row) {
  row.saving = true;
  try {
    await api.put(`/ops/run-policies/${row.id}`, {
      max_attempts: row.max_attempts,
      retry_backoff_seconds: row.retry_backoff_seconds,
      priority: row.priority || 0,
      max_duration_seconds: row.max_duration_seconds || 0,
    });
    ElMessage.success(t("ops.policySaved"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    row.saving = false;
  }
}

async function openJob(row) {
  if (!row?.id) return;
  detailOpen.value = true;
  detailLoading.value = true;
  detail.value = { ...row, nodes: [] };
  compare.value = { previous: null, nodes: [], totals: null };
  try {
    const [one, diff] = await Promise.all([
      api.get(`/ops/jobs/${row.id}/detail`),
      api.get(`/ops/jobs/${row.id}/compare`),
    ]);
    detail.value = one;
    compare.value = diff;
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    detailLoading.value = false;
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

async function cancel(row) {
  try {
    await ElMessageBox.confirm(
      t("ops.cancelConfirm")
        .replace("{id}", row.id)
        .replace("{name}", row.target_name || "-"),
      t("ops.cancelTitle"));
    await api.post(`/ops/jobs/${row.id}/cancel`);
    ElMessage.success(t("ops.cancelled"));
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
  if (name === "perf") loadPerf();
  if (name === "dead") loadDead();
  if (name === "matrix") loadMatrix();
  if (name === "schedules") loadSchedules();
  if (name === "policies") loadPolicies();
  if (name === "health") loadHealth();
  if (name === "calendar") {
    matrixDays.value = 30;
    loadMatrix();
  }
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
.perf-cards { display: grid; grid-template-columns: repeat(5, 1fr);
              gap: 10px; margin: 4px 0 12px; }
.perf-card { background: #fff; border: 1px solid #e5e7eb;
             border-radius: 6px; padding: 10px 12px;
             display: flex; flex-direction: column; gap: 2px; }
.perf-card b { font-size: 22px; color: #0f172a; }
.perf-card b.danger { color: #dc2626; }
.perf-card span { font-size: 11px; color: #64748b; }
.matrix-cell {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 26px; height: 22px; border-radius: 4px; font-size: 11px;
  font-weight: 600; color: #fff; background: #94a3b8;
}
.matrix-cell.success { background: #16a34a; }
.matrix-cell.failed { background: #dc2626; }
.matrix-cell.running { background: #d97706; }
.matrix-cell.queued { background: #2563eb; }
.matrix-cell.skipped { background: #94a3b8; }
.matrix-cell.cancelled { background: #64748b; }
.matrix-empty { color: #cbd5e1; }
.muted { font-size: 11px; color: #94a3b8; }
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
.health-score { display: flex; align-items: center; gap: 6px; }
.health-score :deep(.el-progress) { width: 54px; }
.calendar-grid { display: grid; grid-template-columns: repeat(7, 1fr);
                 gap: 5px; }
.calendar-cell { min-height: 62px; border: 1px solid #e5e7eb;
                 border-radius: 7px; padding: 6px; display: flex;
                 flex-direction: column; gap: 3px; font-size: 12px;
                 background: #fff; }
.calendar-cell.empty { background: transparent; border-color: transparent; }
.calendar-cell.failed { border-color: #fecaca; background: #fef2f2; }
.calendar-cell.success { border-color: #bbf7d0; background: #f0fdf4; }
.calendar-cell.running { border-color: #bfdbfe; background: #eff6ff; }
.calendar-cell.queued { border-color: #fde68a; background: #fffbeb; }
</style>
