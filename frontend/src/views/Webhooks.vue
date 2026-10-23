<template>
  <div class="page">
    <div class="toolbar">
      <el-tag size="small" type="info">HMAC Webhook</el-tag>
      <div class="spacer" />
      <el-button size="small" @click="load" :loading="loading">刷新</el-button>
      <el-button v-if="canEdit" type="primary" size="small"
                 @click="openCreate">新建订阅</el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="rows" size="small" empty-text="还没有事件订阅">
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="url" label="地址" min-width="240"
                         show-overflow-tooltip />
        <el-table-column label="事件" min-width="180">
          <template #default="{ row }">
            <span v-if="!row.events?.length" class="hint">全部事件</span>
            <el-tag v-for="e in row.events" :key="e" size="small"
                    style="margin-right: 4px">{{ e }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="row.enabled ? 'success' : 'info'">
              {{ row.enabled ? "启用" : "停用" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近投递" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.last_status" size="small"
                    :type="row.last_status === 'success' ? 'success'
                      : 'danger'">
              {{ row.last_status }}
            </el-tag>
            <span v-else class="hint">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="230">
          <template #default="{ row }">
            <el-button link @click="showDeliveries(row)">记录</el-button>
            <el-button v-if="canEdit" link @click="test(row)">测试</el-button>
            <el-button v-if="canEdit" link @click="openEdit(row)">编辑</el-button>
            <el-button v-if="canEdit" link type="danger"
                       @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialog" :title="form.id ? '编辑订阅' : '新建订阅'"
               width="560px">
      <el-form label-width="90px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="回调地址" required>
          <el-input v-model="form.url"
                    placeholder="https://example.com/hooks/odf" />
        </el-form-item>
        <el-form-item label="事件">
          <el-select v-model="form.events" multiple clearable
                     placeholder="留空订阅全部事件" style="width: 100%">
            <el-option v-for="e in eventOptions" :key="e" :value="e"
                       :label="e" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
        <el-form-item v-if="!form.id" label="签名密钥">
          <el-input v-model="form.secret" placeholder="留空自动生成" />
        </el-form-item>
        <el-form-item v-else label="密钥">
          <el-checkbox v-model="form.rotate_secret">轮换签名密钥</el-checkbox>
        </el-form-item>
      </el-form>
      <el-alert v-if="createdSecret" type="success" :closable="false"
                title="请保存签名密钥，仅显示一次">
        <div class="mono">{{ createdSecret }}</div>
      </el-alert>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">
          保存
        </el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="drawer" title="投递记录" size="620px"
               @open="loadDeliveries">
      <el-table :data="deliveries" size="small" empty-text="没有投递记录">
        <el-table-column prop="event" label="事件" width="150" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'success'
              ? 'success' : (row.status === 'failed' ? 'danger' : 'warning')">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="attempts" label="尝试" width="70" />
        <el-table-column prop="response_status" label="HTTP" width="70" />
        <el-table-column prop="error" label="错误" min-width="160"
                         show-overflow-tooltip />
        <el-table-column label="时间" width="160">
          <template #default="{ row }">{{ fmt(row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg, getRole } from "../api";

const canEdit = ["editor", "approver", "admin"].includes(getRole());
const rows = ref([]);
const eventOptions = ref([]);
const loading = ref(false);
const saving = ref(false);
const dialog = ref(false);
const drawer = ref(false);
const deliveries = ref([]);
const current = ref(null);
const createdSecret = ref("");
const form = reactive({ id: null, name: "", url: "", events: [],
                        enabled: true, secret: "", rotate_secret: false });

function fmt(v) {
  if (!v) return "-";
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? v : d.toLocaleString("zh-CN");
}

async function load() {
  loading.value = true;
  try {
    rows.value = await api.get("/webhooks");
    eventOptions.value = await api.get("/webhooks/events");
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

function reset() {
  Object.assign(form, { id: null, name: "", url: "", events: [],
                        enabled: true, secret: "", rotate_secret: false });
  createdSecret.value = "";
}

function openCreate() {
  reset();
  dialog.value = true;
}

function openEdit(row) {
  reset();
  Object.assign(form, { id: row.id, name: row.name, url: row.url,
                        events: [...(row.events || [])],
                        enabled: row.enabled });
  dialog.value = true;
}

async function save() {
  if (!form.name.trim() || !form.url.trim()) {
    ElMessage.error("名称和地址必填");
    return;
  }
  saving.value = true;
  try {
    let r;
    if (form.id) {
      r = await api.put(`/webhooks/${form.id}`, {
        name: form.name, url: form.url, events: form.events,
        enabled: form.enabled, rotate_secret: form.rotate_secret,
      });
    } else {
      r = await api.post("/webhooks", {
        name: form.name, url: form.url, events: form.events,
        enabled: form.enabled, secret: form.secret || null,
      });
    }
    if (r?.secret) {
      createdSecret.value = r.secret;
      form.id = r.id;
      form.rotate_secret = false;
    } else {
      dialog.value = false;
    }
    ElMessage.success("已保存");
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

async function test(row) {
  try {
    await api.post(`/webhooks/${row.id}/test`);
    ElMessage.success("测试事件已排队");
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`删除订阅「${row.name}」？`, "删除确认");
    await api.del(`/webhooks/${row.id}`);
    ElMessage.success("已删除");
    await load();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

async function showDeliveries(row) {
  current.value = row;
  drawer.value = true;
}

async function loadDeliveries() {
  if (!current.value) return;
  try {
    deliveries.value = await api.get(
      `/webhooks/${current.value.id}/deliveries`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

onMounted(load);
</script>

<style scoped>
.toolbar { display: flex; gap: 10px; align-items: center;
           margin-bottom: 12px; }
.title { font-size: 16px; font-weight: 700; color: #0f172a; }
.spacer { flex: 1; }
.hint { color: #6b7280; font-size: 12px; }
.mono { font-family: ui-monospace, monospace; font-size: 12px;
        word-break: break-all; }
</style>
