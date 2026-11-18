<template>
  <div class="page">
    <div class="toolbar">
      <el-select v-model="status" clearable :placeholder="t('eng.allStatus')" style="width: 150px"
                 @change="load">
        <el-option value="pending" :label="t('eng.pending')" />
        <el-option value="running" :label="t('eng.running')" />
        <el-option value="succeeded" :label="t('eng.succeeded')" />
        <el-option value="failed" :label="t('eng.failed')" />
        <el-option value="cancelled" :label="t('eng.cancelled')" />
      </el-select>
      <el-select v-model="engine" clearable :placeholder="t('eng.allEngines')" style="width: 140px"
                 @change="load">
        <el-option value="spark" label="Spark" />
        <el-option value="flink" label="Flink" />
      </el-select>
      <div class="spacer" />
      <el-button type="primary" @click="openSubmit">{{ t("eng.submitJob") }}</el-button>
      <el-button @click="openSql">{{ t("eng.runSql") }}</el-button>
      <el-button @click="showProfile">{{ t("eng.engineConfig") }}</el-button>
      <el-button :loading="loading" @click="load">{{ t("eng.refresh") }}</el-button>
    </div>

    <el-card class="card" shadow="never">
      <el-table :data="rows" size="small" v-loading="loading"
                @row-click="showDetail" row-class-name="clickable">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" :label="t('eng.job')" min-width="200" />
        <el-table-column prop="engine" :label="t('eng.engine')" width="90" />
        <el-table-column prop="status" :label="t('eng.status')" width="110">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="attempts" :label="t('eng.attempts')" width="80" />
        <el-table-column prop="submitted_by" :label="t('eng.submittedBy')" width="120" />
        <el-table-column prop="created_at" :label="t('eng.createdAt')" width="200" />
        <el-table-column :label="t('eng.actions')" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link :disabled="!active(row)" @click.stop="cancel(row)">
              {{ t("eng.cancel") }}
            </el-button>
            <el-button v-if="row.engine === 'flink' && active(row)" link
                       @click.stop="savepoint(row)">{{ t("eng.savepoint") }}</el-button>
            <el-button link @click.stop="showDetail(row)">{{ t("eng.details") }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !rows.length" :description="t('eng.empty')" />
    </el-card>

    <el-dialog v-model="submitOpen" :title="t('eng.submitDialogTitle')" width="620px">
      <el-form label-width="120px">
        <el-form-item :label="t('eng.engine')">
          <el-radio-group v-model="form.engine">
            <el-radio value="spark">Spark</el-radio>
            <el-radio value="flink">Flink SQL</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item :label="t('eng.jobName')">
          <el-input v-model="form.name" :placeholder="t('eng.namePlaceholder')" />
        </el-form-item>
        <template v-if="form.engine === 'spark'">
          <el-form-item :label="t('eng.image')">
            <el-input v-model="form.image" />
          </el-form-item>
          <el-form-item :label="t('eng.mainApp')">
            <el-input v-model="form.main_application_file"
                      placeholder="local:///opt/spark/work-dir/job.py" />
          </el-form-item>
          <el-form-item :label="t('eng.args')">
            <el-input v-model="form.args" :placeholder="t('eng.argsPlaceholder')" />
          </el-form-item>
          <el-form-item label="Executor">
            <el-input-number v-model="form.executor_instances" :min="1" :max="100" />
            <span class="hint">{{ t("eng.instances") }}</span>
            <el-input v-model="form.executor_memory" style="width: 110px" />
            <span class="hint">{{ t("eng.memory") }}</span>
          </el-form-item>
        </template>
        <template v-else>
          <el-form-item label="SQL">
            <el-input v-model="form.statement" type="textarea" :rows="8" />
          </el-form-item>
          <el-form-item :label="t('eng.execMode')">
            <el-switch v-model="form.attached" :active-text="t('eng.attached')"
                       :inactive-text="t('eng.detached')" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="submitOpen = false">{{ t("eng.cancel") }}</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">
          {{ t("eng.submit") }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="sqlOpen" title="Flink SQL" width="680px">
      <el-input v-model="sql.statement" type="textarea" :rows="10"
                :placeholder="t('eng.sqlPlaceholder')" />
      <pre v-if="sql.result" class="detail">{{ JSON.stringify(sql.result, null, 2) }}</pre>
      <template #footer>
        <el-button @click="sqlOpen = false">{{ t("eng.close") }}</el-button>
        <el-button type="primary" :loading="sql.running" @click="runSql">
          {{ t("eng.execute") }}
        </el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="profileOpen" :title="t('eng.engineConfig')" size="560px">
      <el-descriptions :column="1" border>
        <el-descriptions-item :label="t('eng.lakehouse')">
          {{ profile.lakehouse_enabled ? t("eng.enabled") : t("eng.disabled") }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('eng.defaultImage')">
          {{ profile.spark && profile.spark.image }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('eng.sqlGateway')">
          {{ profile.flink && profile.flink.sql_gateway ? t("eng.configured") : t("eng.notConfigured") }}
        </el-descriptions-item>
        <el-descriptions-item label="Flink REST">
          {{ profile.flink && profile.flink.rest ? t("eng.configured") : t("eng.notConfigured") }}
        </el-descriptions-item>
      </el-descriptions>
      <h4>{{ t("eng.defaultSparkConf") }}</h4>
      <pre class="detail">{{ JSON.stringify(profile.spark && profile.spark.spark_conf, null, 2) }}</pre>
    </el-drawer>

    <el-drawer v-model="drawer" :title="current.name || t('eng.jobDetail')" size="560px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="ID">{{ current.id }}</el-descriptions-item>
        <el-descriptions-item :label="t('eng.engine')">{{ current.engine }}</el-descriptions-item>
        <el-descriptions-item :label="t('eng.status')">{{ statusLabel(current.status) }}</el-descriptions-item>
        <el-descriptions-item :label="t('eng.externalId')">{{ current.external_id || "-" }}</el-descriptions-item>
        <el-descriptions-item :label="t('eng.started')">{{ current.started_at || "-" }}</el-descriptions-item>
        <el-descriptions-item :label="t('eng.finished')">{{ current.finished_at || "-" }}</el-descriptions-item>
      </el-descriptions>
      <h4>{{ t("eng.spec") }}</h4>
      <pre class="detail">{{ JSON.stringify(current.spec, null, 2) }}</pre>
      <template v-if="current.error">
        <h4>{{ t("eng.error") }}</h4>
        <pre class="detail">{{ current.error }}</pre>
      </template>
      <template v-if="hasResult">
        <h4>{{ t("eng.result") }}</h4>
        <pre class="detail">{{ JSON.stringify(current.result, null, 2) }}</pre>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../api";
import { t } from "../i18n";

const rows = ref([]);
const loading = ref(false);
const status = ref("");
const engine = ref("");
const drawer = ref(false);
const current = ref({});
const submitOpen = ref(false);
const submitting = ref(false);
const sqlOpen = ref(false);
const profileOpen = ref(false);
const profile = ref({});

const blankForm = () => ({
  engine: "spark",
  name: "",
  image: "apache/spark:3.5.1",
  main_application_file: "local:///opt/spark/work-dir/job.py",
  args: "",
  executor_instances: 1,
  executor_memory: "1g",
  statement: "",
  attached: true,
});
const form = ref(blankForm());
const sql = ref({ statement: "", result: null, running: false });

const hasResult = computed(() => {
  const r = current.value.result;
  return r && Object.keys(r).length > 0;
});

const ACTIVE = ["pending", "running"];

function active(row) {
  return ACTIVE.includes(row.status);
}

function statusLabel(s) {
  return {
    pending: t("eng.pending"), running: t("eng.running"),
    succeeded: t("eng.succeeded"), failed: t("eng.failed"),
    cancelled: t("eng.cancelled"), unknown: t("eng.unknown"),
  }[s] || s;
}

function statusType(s) {
  return {
    pending: "info", running: "warning", succeeded: "success",
    failed: "danger", cancelled: "info",
  }[s] || "info";
}

async function load() {
  loading.value = true;
  try {
    const q = [];
    if (status.value) q.push("status=" + encodeURIComponent(status.value));
    if (engine.value) q.push("engine=" + encodeURIComponent(engine.value));
    rows.value = await api.get("/engine/jobs" + (q.length ? "?" + q.join("&") : ""));
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

function openSubmit() {
  form.value = blankForm();
  submitOpen.value = true;
}

async function showProfile() {
  try {
    profile.value = await api.get("/engine/profiles");
    profileOpen.value = true;
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

function openSql() {
  sql.value = { statement: "", result: null, running: false };
  sqlOpen.value = true;
}

async function submit() {
  submitting.value = true;
  try {
    const f = form.value;
    let spec;
    if (f.engine === "spark") {
      spec = {
        image: f.image,
        main_application_file: f.main_application_file,
        args: f.args ? f.args.split(/\s+/).filter(Boolean) : [],
        executor_instances: f.executor_instances,
        executor_memory: f.executor_memory,
      };
    } else {
      spec = { statement: f.statement, attached: f.attached };
    }
    const job = await api.post("/engine/jobs", {
      engine: f.engine, name: f.name, spec,
    });
    ElMessage.success(t("eng.submitted").replace("{name}", job.name));
    submitOpen.value = false;
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    submitting.value = false;
  }
}

async function runSql() {
  sql.value.running = true;
  try {
    const out = await api.post("/engine/sql", { statement: sql.value.statement });
    sql.value.result = out.result;
    ElMessage.success(t("eng.executed"));
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    sql.value.running = false;
  }
}

async function savepoint(row) {
  let target;
  try {
    const { value } = await ElMessageBox.prompt(
      t("eng.savepointPrompt"), t("eng.savepointTitle"), {
        inputPlaceholder: "s3://warehouse/savepoints",
        confirmButtonText: t("eng.saveContinue"),
        cancelButtonText: t("eng.cancel"),
      });
    target = value || "";
  } catch (e) {
    return;
  }
  try {
    const out = await api.post(`/engine/jobs/${row.id}/savepoint`,
                               { target_directory: target });
    ElMessage.success(out.location
      ? t("eng.savedTo").replace("{location}", out.location)
      : t("eng.savepointStatus").replace("{status}", out.status || t("eng.triggered")));
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function cancel(row) {
  try {
    await ElMessageBox.confirm(
      t("eng.cancelConfirm").replace("{name}", row.name), t("eng.cancelTitle"),
      { type: "warning" });
  } catch (e) {
    return;
  }
  try {
    await api.del(`/engine/jobs/${row.id}`);
    ElMessage.success(t("eng.cancelledMsg"));
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

onMounted(load);
</script>

<style scoped>
.hint {
  margin: 0 8px 0 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
