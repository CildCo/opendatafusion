<template>
  <el-button size="small" :disabled="!published" @click="open">
    分享
  </el-button>
  <el-dialog v-model="visible" title="只读分享链接" width="600px">
    <div class="row">
      <span class="hint">有效期</span>
      <el-select v-model="days" size="small" style="width: 120px">
        <el-option :value="1" label="1 天" />
        <el-option :value="7" label="7 天" />
        <el-option :value="30" label="30 天" />
      </el-select>
      <div class="spacer" />
      <el-button size="small" type="primary" :loading="creating"
                 @click="create">生成链接</el-button>
    </div>
    <el-alert v-if="createdUrl" type="success" :closable="false"
              title="链接已生成，关闭后仍可在下方查看状态">
      <el-input :model-value="createdUrl" readonly size="small">
        <template #append>
          <el-button @click="copy">复制</el-button>
        </template>
      </el-input>
    </el-alert>
    <el-table :data="shares" size="small" empty-text="还没有分享链接"
              style="margin-top: 12px">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="创建时间" width="170">
        <template #default="{ row }">{{ fmt(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="过期时间" width="170">
        <template #default="{ row }">{{ fmt(row.expires_at) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="row.active ? 'success' : 'info'">
            {{ row.active ? "有效" : "失效" }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="90">
        <template #default="{ row }">
          <el-button v-if="row.active" link type="danger"
                     @click="revoke(row)">撤销</el-button>
        </template>
      </el-table-column>
    </el-table>
    <p class="hint">
      链接为只读访问，不包含表单；令牌只显示一次，请妥善保管。
    </p>
  </el-dialog>
</template>

<script setup>
import { ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../../api";

const props = defineProps({
  kind: { type: String, required: true },
  assetId: { type: Number, required: true },
  published: Boolean,
});
const visible = ref(false);
const days = ref(7);
const creating = ref(false);
const createdUrl = ref("");
const shares = ref([]);

function fmt(v) {
  if (!v) return "-";
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? v : d.toLocaleString("zh-CN");
}

async function load() {
  try {
    shares.value = await api.get(`/${props.kind}/${props.assetId}/shares`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

function open() {
  visible.value = true;
  createdUrl.value = "";
  load();
}

async function create() {
  creating.value = true;
  try {
    const r = await api.post(`/${props.kind}/${props.assetId}/share`,
                             { expires_days: days.value });
    createdUrl.value =
      `${location.origin}${location.pathname}#/share/${r.token}`;
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    creating.value = false;
  }
}

async function copy() {
  try {
    await navigator.clipboard.writeText(createdUrl.value);
    ElMessage.success("已复制");
  } catch (e) {
    ElMessage.error("复制失败，请手动选择链接");
  }
}

async function revoke(row) {
  try {
    await ElMessageBox.confirm("撤销后该链接立即失效，继续？", "撤销分享");
    await api.post(`/${props.kind}/${props.assetId}/shares/${row.id}/revoke`);
    ElMessage.success("已撤销");
    await load();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}
</script>

<style scoped>
.row { display: flex; gap: 8px; align-items: center; }
.spacer { flex: 1; }
.hint { font-size: 12px; color: #6b7280; }
</style>
