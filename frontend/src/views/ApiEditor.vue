<template>
  <div class="api-page">
    <div class="head">
      <el-button link @click="$router.push('/apis')">←</el-button>
      <el-input v-model="name" size="small" style="width: 240px"
                @change="rename" />
      <el-tag size="small" :type="enabled ? 'success' : 'info'">
        {{ enabled ? t("aed.published") : t("aed.draft") }}
      </el-tag>
      <span class="key mono">{{ key }}</span>
      <div class="spacer" />
      <el-button size="small" @click="save">{{ t("aed.save") }}</el-button>
      <el-button size="small" @click="validate">{{ t("aed.validate") }}</el-button>
      <el-button size="small" @click="preview?.run()">{{ t("aed.preview") }}</el-button>
      <el-button size="small" @click="test">{{ t("aed.test") }}</el-button>
      <el-button size="small" type="primary" @click="publish">{{ t("aed.publish") }}</el-button>
      <el-button size="small" @click="versionsOpen = true">{{ t("aed.versions") }}</el-button>
      <el-button size="small" @click="openStats">{{ t("aed.stats") }}</el-button>
      <el-button size="small" @click="docsOpen = true">{{ t("aed.docs") }}</el-button>
      <el-button size="small" @click="toggle">
        {{ enabled ? t("aed.offline") : t("aed.enable") }}
      </el-button>
    </div>

    <div class="body">
      <aside class="left">
        <AssetTree :items="items" :active-id="id" :title="t('aed.interfaces')"
                   @select="openOther" />
      </aside>
      <main class="center">
        <div v-if="content.mode === 'sql'" class="sql-ds">
          <span>{{ t("aed.datasource") }}</span>
          <el-select v-model="content.query.datasource_id" size="small"
                     style="width: 220px">
            <el-option v-for="d in datasources" :key="d.id" :value="d.id"
                       :label="d.name" />
          </el-select>
        </div>
        <el-radio-group v-model="content.mode" size="small" class="mode">
          <el-radio-button value="visual">{{ t("aed.visual") }}</el-radio-button>
          <el-radio-button value="sql">{{ t("aed.sql") }}</el-radio-button>
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

    <el-drawer v-model="versionsOpen" :title="t('aed.versions')" size="480px"
               @open="openVersions">
      <el-table :data="versions" size="small">
        <el-table-column prop="version" :label="t('aed.version')" width="70" />
        <el-table-column prop="status" :label="t('aed.status')" width="100" />
        <el-table-column prop="created_by" :label="t('aed.createdBy')" />
        <el-table-column :label="t('aed.actions')" width="90">
          <template #default="{ row }">
            <el-button link :disabled="row.current || row.status === 'draft'"
                       @click="rollback(row)">{{ t("aed.rollback") }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>
    <ApiDocs v-model="docsOpen" :asset-id="id" />

    <el-drawer v-model="statsOpen" :title="t('aed.stats')" size="560px">
      <div class="stat-row">
        <div class="stat">
          <span>{{ t("aed.calls") }}</span>
          <b>{{ stats.total.count }}</b>
        </div>
        <div class="stat">
          <span>{{ t("aed.errors") }}</span>
          <b>{{ stats.total.errors }}</b>
        </div>
        <div class="stat">
          <span>{{ t("aed.avgLatency") }}</span>
          <b>{{ stats.total.avg_ms }} ms</b>
        </div>
      </div>
      <h4>{{ t("aed.byDay") }}</h4>
      <el-table :data="stats.days" size="small">
        <el-table-column prop="day" :label="t('aed.day')" />
        <el-table-column prop="count" :label="t('aed.calls')" width="100" />
        <el-table-column prop="errors" :label="t('aed.errors')" width="90" />
        <el-table-column :label="t('aed.avgLatency')" width="120">
          <template #default="{ row }">{{ row.avg_ms }} ms</template>
        </el-table-column>
      </el-table>
      <h4>{{ t("aed.byKey") }}</h4>
      <el-table :data="stats.keys" size="small">
        <el-table-column prop="ak" label="AK" />
        <el-table-column prop="count" :label="t('aed.calls')" width="100" />
        <el-table-column prop="errors" :label="t('aed.errors')" width="90" />
        <el-table-column :label="t('aed.avgLatency')" width="120">
          <template #default="{ row }">{{ row.avg_ms }} ms</template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!stats.total.count" :description="t('aed.noStats')"
                :image-size="60" />
    </el-drawer>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, errMsg } from "../api";
import { t } from "../i18n";
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
const statsOpen = ref(false);
const stats = ref({ total: { count: 0, errors: 0, avg_ms: 0 },
                    days: [], keys: [] });
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
    ElMessage.success(t("aed.draftSaved"));
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
    if (r.valid) ElMessage.success(t("aed.validated"));
    else ElMessage.error(r.errors.map((x) => x.message).join("; "));
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function test() {
  try {
    const r = await api.post(`/apis/${id}/test`, { params: {} });
    ElMessage.success(t("aed.testSuccess").replace("{count}", r.row_count));
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
    ElMessage.success(t("aed.publishedMsg"));
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

async function openStats() {
  statsOpen.value = true;
  try {
    stats.value = await api.get(`/apis/${id}/stats?days=30`);
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function rollback(row) {
  try {
    await ElMessageBox.confirm(
      t("aed.rollbackConfirm").replace("{version}", row.version),
      t("aed.rollbackTitle"));
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
.stat-row { display: flex; gap: 12px; margin-bottom: 8px; }
.stat { flex: 1; border: 1px solid #e5e7eb; border-radius: 8px;
        padding: 10px 12px; display: flex; flex-direction: column;
        gap: 4px; background: #fff; }
.stat span { color: #6b7280; font-size: 12px; }
.stat b { font-size: 20px; color: #0f172a; }
.body { flex: 1; display: grid; grid-template-columns: 210px 1fr 360px;
        min-height: 0; }
.left { background: #fff; border-right: 1px solid #e5e7eb; overflow: auto; }
.center { min-width: 0; overflow: auto; background: #fff; }
.right { background: #fff; border-left: 1px solid #e5e7eb; overflow: auto; }
.mode { padding: 10px 12px; }
.sql-ds { display: flex; gap: 8px; align-items: center; padding: 10px 12px 0;
          font-size: 13px; }
</style>
