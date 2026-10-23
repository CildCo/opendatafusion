<template>
  <div class="api-page">
    <div class="head">
      <el-button link @click="$router.push('/apis')">←</el-button>
      <el-input v-model="name" size="small" style="width: 240px"
                @change="rename" />
      <el-tag size="small" :type="enabled ? 'success' : 'info'">
        {{ enabled ? "已发布" : "草稿" }}
      </el-tag>
      <span class="key mono">{{ key }}</span>
      <div class="spacer" />
      <el-button size="small" @click="save">保存</el-button>
      <el-button size="small" @click="validate">校验</el-button>
      <el-button size="small" @click="preview?.run()">预览</el-button>
      <el-button size="small" @click="test">测试</el-button>
      <el-button size="small" type="primary" @click="publish">发布</el-button>
      <el-button size="small" @click="versionsOpen = true">版本</el-button>
      <el-button size="small" @click="docsOpen = true">文档</el-button>
      <el-button size="small" @click="toggle">
        {{ enabled ? "下线" : "启用" }}
      </el-button>
    </div>

    <div class="body">
      <aside class="left">
        <AssetTree :items="items" :active-id="id" title="数据接口"
                   @select="openOther" />
      </aside>
      <main class="center">
        <div v-if="content.mode === 'sql'" class="sql-ds">
          <span>数据源</span>
          <el-select v-model="content.query.datasource_id" size="small"
                     style="width: 220px">
            <el-option v-for="d in datasources" :key="d.id" :value="d.id"
                       :label="d.name" />
          </el-select>
        </div>
        <el-radio-group v-model="content.mode" size="small" class="mode">
          <el-radio-button value="visual">可视化</el-radio-button>
          <el-radio-button value="sql">SQL</el-radio-button>
        </el-radio-group>
        <VisualBuilder v-if="content.mode === 'visual'"
                       :content="content" :datasources="datasources" />
        <SqlEditor v-else v-model="content.sql" />
      </main>
      <aside class="right">
        <ParamsPanel :params="content.params" />
        <el-divider />
        <ApiPreview ref="preview" :asset-id="id" :params="content.params"
                    :content="content" />
      </aside>
    </div>

    <el-drawer v-model="versionsOpen" title="版本" size="480px"
               @open="openVersions">
      <el-table :data="versions" size="small">
        <el-table-column prop="version" label="版本" width="70" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="created_by" label="创建人" />
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button link :disabled="row.current || row.status === 'draft'"
                       @click="rollback(row)">回滚</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>
    <ApiDocs v-model="docsOpen" :asset-id="id" />
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../api";
import AssetTree from "../studio/AssetTree.vue";
import VisualBuilder from "../studio/api/VisualBuilder.vue";
import SqlEditor from "../studio/api/SqlEditor.vue";
import ParamsPanel from "../studio/api/ParamsPanel.vue";
import ApiPreview from "../studio/api/ApiPreview.vue";
import ApiDocs from "../studio/api/ApiDocs.vue";
import { normalizeContent } from "../studio/api/content";

const route = useRoute();
const router = useRouter();
const id = Number(route.params.id);
const name = ref("");
const key = ref("");
const enabled = ref(false);
const content = ref(normalizeContent(null));
const datasources = ref([]);
const items = ref([]);
const versions = ref([]);
const versionsOpen = ref(false);
const docsOpen = ref(false);
const preview = ref(null);

async function load() {
  const a = await api.get(`/apis/${id}`);
  name.value = a.name;
  key.value = a.key;
  enabled.value = a.enabled;
  content.value = normalizeContent(a.draft);
  items.value = await api.get("/apis");
  datasources.value = await api.get("/datasources");
}

function openOther(p) {
  if (p.id !== id) router.push(`/apis/${p.id}`);
}

async function save() {
  try {
    await api.put(`/apis/${id}/draft`, { content: content.value });
    ElMessage.success("已保存草稿");
    return true;
  } catch (e) {
    ElMessage.error(errMsg(e));
    return false;
  }
}

async function rename() {
  try {
    await api.put(`/apis/${id}`, { name: name.value });
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function validate() {
  try {
    const r = await api.post(`/apis/${id}/validate`,
                             { content: content.value });
    if (r.valid) ElMessage.success("校验通过");
    else ElMessage.error(r.errors.map((x) => x.message).join("; "));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function test() {
  try {
    const r = await api.post(`/apis/${id}/test`, { params: {} });
    ElMessage.success(`测试成功：${r.row_count} 行`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function publish() {
  try {
    const ok = await save();
    if (!ok) return;
    await api.applyChange("publish_api", id);
    await load();
    ElMessage.success("已发布");
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function toggle() {
  try {
    await api.applyChange(enabled.value ? "revoke_api" : "enable_api", id);
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function openVersions() {
  versions.value = await api.get(`/apis/${id}/versions`);
}

async function rollback(row) {
  try {
    await ElMessageBox.confirm(`回滚到版本 ${row.version}？`, "回滚确认");
    await api.applyChange("rollback_api", id, { version: row.version });
    await load();
    await openVersions();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(errMsg(e));
  }
}

onMounted(load);
</script>

<style scoped>
.api-page { height: calc(100vh - 104px); display: flex; flex-direction: column;
            background: #f8fafc; border: 1px solid #e5e7eb;
            border-radius: 10px; overflow: hidden; }
.head { height: 52px; display: flex; align-items: center; gap: 8px;
        padding: 0 12px; background: #fff; border-bottom: 1px solid #e5e7eb; }
.spacer { flex: 1; }
.key { font-size: 12px; color: #6b7280; }
.mono { font-family: ui-monospace, monospace; }
.body { flex: 1; display: grid; grid-template-columns: 210px 1fr 360px;
        min-height: 0; }
.left { background: #fff; border-right: 1px solid #e5e7eb; overflow: auto; }
.center { min-width: 0; overflow: auto; background: #fff; }
.right { background: #fff; border-left: 1px solid #e5e7eb; overflow: auto; }
.mode { padding: 10px 12px; }
.sql-ds { display: flex; gap: 8px; align-items: center; padding: 10px 12px 0;
          font-size: 13px; }
</style>
