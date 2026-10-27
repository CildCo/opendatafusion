<template>
  <div class="page">
    <div class="toolbar">
      <el-select v-model="status" clearable placeholder="全部状态" style="width: 150px"
                 @change="load">
        <el-option value="pending" label="等待中" />
        <el-option value="running" label="运行中" />
        <el-option value="succeeded" label="成功" />
        <el-option value="failed" label="失败" />
        <el-option value="cancelled" label="已取消" />
      </el-select>
      <el-select v-model="engine" clearable placeholder="全部引擎" style="width: 140px"
                 @change="load">
        <el-option value="spark" label="Spark" />
        <el-option value="flink" label="Flink" />
      </el-select>
      <div class="spacer" />
      <el-button type="primary" @click="openSubmit">提交作业</el-button>
      <el-button @click="openSql">运行 SQL</el-button>
      <el-button @click="showProfile">引擎配置</el-button>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </div>

    <el-card class="card" shadow="never">
      <el-table :data="rows" size="small" v-loading="loading"
                @row-click="showDetail" row-class-name="clickable">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="作业" min-width="200" />
        <el-table-column prop="engine" label="引擎" width="90" />
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="attempts" label="尝试" width="80" />
        <el-table-column prop="submitted_by" label="提交人" width="120" />
        <el-table-column prop="created_at" label="创建时间" width="200" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link :disabled="!active(row)" @click.stop="cancel(row)">
              取消
            </el-button>
            <el-button v-if="row.engine === 'flink' && active(row)" link
                       @click.stop="savepoint(row)">存点</el-button>
            <el-button link @click.stop="showDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !rows.length" description="暂无作业" />
    </el-card>

    <el-dialog v-model="submitOpen" title="提交计算作业" width="620px">
      <el-form label-width="120px">
        <el-form-item label="引擎">
          <el-radio-group v-model="form.engine">
            <el-radio value="spark">Spark</el-radio>
            <el-radio value="flink">Flink SQL</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="作业名称">
          <el-input v-model="form.name" placeholder="小写字母、数字和短横线" />
        </el-form-item>
        <template v-if="form.engine === 'spark'">
          <el-form-item label="镜像">
            <el-input v-model="form.image" />
          </el-form-item>
          <el-form-item label="主程序">
            <el-input v-model="form.main_application_file"
                      placeholder="local:///opt/spark/work-dir/job.py" />
          </el-form-item>
          <el-form-item label="参数">
            <el-input v-model="form.args" placeholder="空格分隔" />
          </el-form-item>
          <el-form-item label="Executor">
            <el-input-number v-model="form.executor_instances" :min="1" :max="100" />
            <span class="hint">实例数</span>
            <el-input v-model="form.executor_memory" style="width: 110px" />
            <span class="hint">内存</span>
          </el-form-item>
        </template>
        <template v-else>
          <el-form-item label="SQL">
            <el-input v-model="form.statement" type="textarea" :rows="8" />
          </el-form-item>
          <el-form-item label="执行模式">
            <el-switch v-model="form.attached" active-text="同步"
                       inactive-text="后台运行" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="submitOpen = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">
          提交
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="sqlOpen" title="Flink SQL" width="680px">
      <el-input v-model="sql.statement" type="textarea" :rows="10"
                placeholder="仅允许 SELECT / WITH / SHOW / DESCRIBE / EXPLAIN" />
      <pre v-if="sql.result" class="detail">{{ JSON.stringify(sql.result, null, 2) }}</pre>
      <template #footer>
        <el-button @click="sqlOpen = false">关闭</el-button>
        <el-button type="primary" :loading="sql.running" @click="runSql">
          执行
        </el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="profileOpen" title="引擎配置" size="560px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="湖仓模式">
          {{ profile.lakehouse_enabled ? "已启用" : "未启用" }}
        </el-descriptions-item>
        <el-descriptions-item label="默认镜像">
          {{ profile.spark && profile.spark.image }}
        </el-descriptions-item>
        <el-descriptions-item label="SQL 网关">
          {{ profile.flink && profile.flink.sql_gateway ? "已配置" : "未配置" }}
        </el-descriptions-item>
        <el-descriptions-item label="Flink REST">
          {{ profile.flink && profile.flink.rest ? "已配置" : "未配置" }}
        </el-descriptions-item>
      </el-descriptions>
      <h4>默认 Spark 配置</h4>
      <pre class="detail">{{ JSON.stringify(profile.spark && profile.spark.spark_conf, null, 2) }}</pre>
    </el-drawer>

    <el-drawer v-model="drawer" :title="current.name || '作业详情'" size="560px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="ID">{{ current.id }}</el-descriptions-item>
        <el-descriptions-item label="引擎">{{ current.engine }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ statusLabel(current.status) }}</el-descriptions-item>
        <el-descriptions-item label="外部 ID">{{ current.external_id || "-" }}</el-descriptions-item>
        <el-descriptions-item label="开始">{{ current.started_at || "-" }}</el-descriptions-item>
        <el-descriptions-item label="结束">{{ current.finished_at || "-" }}</el-descriptions-item>
      </el-descriptions>
      <h4>规格</h4>
      <pre class="detail">{{ JSON.stringify(current.spec, null, 2) }}</pre>
      <template v-if="current.error">
        <h4>错误</h4>
        <pre class="detail">{{ current.error }}</pre>
      </template>
      <template v-if="hasResult">
        <h4>结果</h4>
        <pre class="detail">{{ JSON.stringify(current.result, null, 2) }}</pre>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../api";

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
    pending: "等待中", running: "运行中", succeeded: "成功",
    failed: "失败", cancelled: "已取消", unknown: "未知",
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
    ElMessage.success("已提交：" + job.name);
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
    ElMessage.success("已执行");
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
      "目标目录（可留空，使用集群默认）", "触发保存点", {
        inputPlaceholder: "s3://warehouse/savepoints",
        confirmButtonText: "保存并继续",
        cancelButtonText: "取消",
      });
    target = value || "";
  } catch (e) {
    return;
  }
  try {
    const out = await api.post(`/engine/jobs/${row.id}/savepoint`,
                               { target_directory: target });
    ElMessage.success(out.location
      ? "已保存到 " + out.location
      : "保存点状态：" + (out.status || "已触发"));
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function cancel(row) {
  try {
    await ElMessageBox.confirm(`取消作业 ${row.name}？`, "取消作业",
      { type: "warning" });
  } catch (e) {
    return;
  }
  try {
    await api.del(`/engine/jobs/${row.id}`);
    ElMessage.success("已取消");
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
