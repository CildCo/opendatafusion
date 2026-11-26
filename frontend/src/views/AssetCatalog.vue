<template>
  <div class="asset-catalog">
    <div class="toolbar">
      <el-input v-model="query" clearable :prefix-icon="Search"
                :placeholder="t('acat.searchPlaceholder')"
                style="width: 280px" @keyup.enter="load" @clear="load" />
      <el-select v-model="type" clearable :placeholder="t('acat.allTypes')"
                 style="width: 130px" @change="load">
        <el-option v-for="item in typeOptions" :key="item.value"
                   :value="item.value" :label="item.label" />
      </el-select>
      <el-select v-model="certification" clearable
                 :placeholder="t('acat.certification')"
                 style="width: 130px" @change="load">
        <el-option value="certified" :label="t('acat.certified')" />
        <el-option value="none" :label="t('acat.uncertified')" />
      </el-select>
      <el-select v-model="lifecycle" clearable
                 :placeholder="t('acat.lifecycle')"
                 style="width: 130px" @change="load">
        <el-option v-for="item in lifecycleOptions" :key="item.value"
                   :value="item.value" :label="item.label" />
      </el-select>
      <el-select v-model="sort" style="width: 130px" @change="load">
        <el-option value="relevance" :label="t('acat.sortRelevance')" />
        <el-option value="trust" :label="t('acat.sortTrust')" />
        <el-option value="usage" :label="t('acat.sortUsage')" />
        <el-option value="recent" :label="t('acat.sortRecent')" />
      </el-select>
      <div class="spacer" />
      <el-button :loading="loading" @click="load">
        {{ t("cat.refresh") }}
      </el-button>
    </div>

    <div v-if="recommended.length" class="recommend">
      <div class="section-title">{{ t("acat.recommended") }}</div>
      <div class="recommend-grid">
        <button v-for="item in recommended" :key="item.id" type="button"
                class="recommend-card" @click="select(item)">
          <span class="rec-head">
            <b>{{ item.name }}</b>
            <el-tag v-if="item.certification === 'certified'" size="small"
                    type="success">{{ t("acat.certified") }}</el-tag>
          </span>
          <span class="rec-meta">
            {{ typeLabel(item.type) }} · {{ item.owner }}
          </span>
          <span class="rec-score">
            <span class="score">{{ item.trust.score }}</span>
            <span class="muted">{{ t("acat.trust") }}</span>
          </span>
        </button>
      </div>
    </div>

    <el-table :data="items" v-loading="loading" size="small" stripe
              class="asset-table" @row-click="select">
      <el-table-column :label="t('acat.trust')" width="150">
        <template #default="{ row }">
          <div class="trust-cell">
            <el-progress :percentage="row.trust.score" :stroke-width="6"
                         :show-text="false"
                         :color="scoreColor(row.trust.score)" />
            <b>{{ row.trust.score }}</b>
            <el-tag size="small" :type="levelType(row.trust.level)">
              {{ levelLabel(row.trust.level) }}
            </el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="name" :label="t('acat.searchPlaceholder')"
                       min-width="180">
        <template #default="{ row }">
          <div class="name-cell">
            <b>{{ row.name }}</b>
            <small>{{ row.key }}</small>
          </div>
        </template>
      </el-table-column>
      <el-table-column :label="t('cat.type')" width="100">
        <template #default="{ row }">{{ typeLabel(row.type) }}</template>
      </el-table-column>
      <el-table-column prop="owner" :label="t('acat.owner')" width="100" />
      <el-table-column :label="t('acat.domain')" width="120">
        <template #default="{ row }">{{ row.domain_name || "-" }}</template>
      </el-table-column>
      <el-table-column :label="t('acat.certification')" width="100">
        <template #default="{ row }">
          <el-tag size="small"
                  :type="row.certification === 'certified'
                    ? 'success' : 'info'">
            {{ row.certification === "certified"
              ? t("acat.certified") : t("acat.uncertified") }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('acat.lifecycle')" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="lifecycleType(row.lifecycle)">
            {{ lifecycleLabel(row.lifecycle) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('acat.usage')" width="90">
        <template #default="{ row }">
          {{ row.trust.usage.total }}
        </template>
      </el-table-column>
      <el-table-column :label="t('acat.updated')" width="150">
        <template #default="{ row }">{{ fmtTime(row.updated_at) }}</template>
      </el-table-column>
      <template #empty>
        <el-empty :description="t('acat.empty')" :image-size="60" />
      </template>
    </el-table>

    <el-drawer v-model="drawer" size="520px"
               :title="selected?.name || t('acat.drawerTitle')">
      <template v-if="selected">
        <div class="trust-head">
          <div class="trust-ring"
               :style="{ borderColor: scoreColor(selected.trust.score) }">
            <b>{{ selected.trust.score }}</b>
            <small>{{ t("acat.trust") }}</small>
          </div>
          <div class="trust-meta">
            <div>
              <el-tag :type="levelType(selected.trust.level)">
                {{ levelLabel(selected.trust.level) }}
              </el-tag>
              <el-tag v-if="selected.certification === 'certified'"
                      type="success" style="margin-left: 6px">
                {{ t("acat.certified") }}
              </el-tag>
              <el-tag :type="lifecycleType(selected.lifecycle)"
                      style="margin-left: 6px">
                {{ lifecycleLabel(selected.lifecycle) }}
              </el-tag>
            </div>
            <p>{{ typeLabel(selected.type) }} · {{ selected.owner }}</p>
            <p class="muted">
              {{ selected.domain_name || t("acat.domain") + " -" }}
            </p>
            <p v-if="selected.lifecycle_note" class="note">
              {{ selected.lifecycle_note }}
            </p>
          </div>
        </div>

        <div class="section-title">{{ t("acat.factors") }}</div>
        <div class="factor-list">
          <div v-for="factor in selected.trust.factors" :key="factor.key"
               class="factor-row" :class="{ ok: factor.ok }">
            <span class="factor-check">{{ factor.ok ? "✓" : "·" }}</span>
            <span class="factor-name">{{ factorLabel(factor.key) }}</span>
            <span class="factor-detail">{{ factor.detail }}</span>
            <b>{{ factor.score }}/{{ factor.weight }}</b>
          </div>
        </div>

        <div class="section-title">{{ t("acat.usage") }}</div>
        <div class="usage-grid">
          <div><b>{{ selected.trust.usage.runs }}</b>
            <span>{{ t("acat.runs") }}</span></div>
          <div><b>{{ selected.trust.usage.api_calls_30d }}</b>
            <span>{{ t("acat.apiCalls") }}</span></div>
          <div><b>{{ selected.trust.usage.downstream }}</b>
            <span>{{ t("acat.downstream") }}</span></div>
        </div>

        <template v-if="canApprove">
          <div class="section-title">{{ t("acat.lifecycleNote") }}</div>
          <el-input v-model="note" type="textarea" :rows="2" size="small"
                    :placeholder="t('acat.note')" />
          <div class="actions">
            <el-button v-if="selected.certification !== 'certified'"
                       type="success" size="small" @click="certify(true)">
              {{ t("acat.certify") }}
            </el-button>
            <el-button v-else size="small" @click="certify(false)">
              {{ t("acat.revokeCert") }}
            </el-button>
            <el-button v-if="selected.lifecycle === 'active'" size="small"
                       @click="changeLifecycle('deprecated')">
              {{ t("acat.deprecate") }}
            </el-button>
            <el-button v-if="selected.lifecycle !== 'archived'" size="small"
                       @click="changeLifecycle('archived')">
              {{ t("acat.archive") }}
            </el-button>
            <el-button v-if="selected.lifecycle !== 'active'" size="small"
                       @click="changeLifecycle('active')">
              {{ t("acat.restore") }}
            </el-button>
            <el-button size="small" @click="openAsset(selected)">
              {{ t("acat.open") }}
            </el-button>
          </div>
        </template>

        <div class="section-title">{{ t("acat.similar") }}</div>
        <div v-if="similarAssets.length" class="similar-list">
          <div v-for="item in similarAssets" :key="item.id" class="similar-row"
               @click="select(item)">
            <span>
              <b>{{ item.name }}</b>
              <small>{{ typeLabel(item.type) }} · {{ item.owner }}</small>
            </span>
            <el-tag size="small">{{ item.trust.score }}</el-tag>
          </div>
        </div>
        <el-empty v-else :description="t('acat.noSimilar')" :image-size="40" />
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { Search } from "@element-plus/icons-vue";
import { api, errMsg, getRole } from "../api";
import { t } from "../i18n";

const router = useRouter();
const loading = ref(false);
const query = ref("");
const type = ref("");
const certification = ref("");
const lifecycle = ref("");
const sort = ref("relevance");
const items = ref([]);
const recommended = ref([]);
const drawer = ref(false);
const selected = ref(null);
const similarAssets = ref([]);
const note = ref("");

const canApprove = computed(() =>
  ["approver", "admin"].includes(getRole()));

const typeOptions = [
  ["dataset", "acat.typeDataset"],
  ["metric", "acat.typeMetric"],
  ["dashboard", "acat.typeDashboard"],
  ["app", "acat.typeApp"],
  ["pipeline", "acat.typePipeline"],
  ["api", "acat.typeApi"],
  ["model", "acat.typeModel"],
].map(([value, key]) => ({ value, label: t(key) }));

const lifecycleOptions = computed(() => [
  { value: "active", label: t("acat.active") },
  { value: "deprecated", label: t("acat.deprecated") },
  { value: "archived", label: t("acat.archived") },
]);

const typeLabels = {
  dataset: "acat.typeDataset", metric: "acat.typeMetric",
  dashboard: "acat.typeDashboard", app: "acat.typeApp",
  pipeline: "acat.typePipeline", api: "acat.typeApi",
  model: "acat.typeModel",
};
const factorLabels = {
  certified: "acat.factorCertified", owner: "acat.factorOwner",
  domain: "acat.factorDomain", contract: "acat.factorContract",
  check: "acat.factorCheck", usage: "acat.factorUsage",
};
const paths = {
  dataset: "/datasets", metric: "/metrics", dashboard: "/dashboards",
  app: "/apps", pipeline: "/pipelines", api: "/apis", model: "/models",
};

function typeLabel(value) {
  return typeLabels[value] ? t(typeLabels[value]) : value;
}

function factorLabel(key) {
  return factorLabels[key] ? t(factorLabels[key]) : key;
}

function levelLabel(level) {
  return t("acat.level" + level[0].toUpperCase() + level.slice(1));
}

function levelType(level) {
  return { trusted: "success", good: "", fair: "warning",
           low: "danger" }[level] || "info";
}

function lifecycleLabel(value) {
  return { active: t("acat.active"), deprecated: t("acat.deprecated"),
           archived: t("acat.archived") }[value] || value;
}

function lifecycleType(value) {
  return { active: "success", deprecated: "warning",
           archived: "info" }[value] || "info";
}

function scoreColor(score) {
  if (score >= 80) return "#15803d";
  if (score >= 60) return "#2563eb";
  if (score >= 40) return "#d97706";
  return "#dc2626";
}

function fmtTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value
    : date.toLocaleString("zh-CN", { hour12: false });
}

async function load() {
  loading.value = true;
  try {
    const params = new URLSearchParams();
    if (query.value.trim()) params.set("q", query.value.trim());
    if (type.value) params.set("type", type.value);
    if (certification.value) {
      params.set("certification", certification.value);
    }
    if (lifecycle.value) params.set("lifecycle", lifecycle.value);
    params.set("sort", sort.value);
    const out = await api.get(`/catalog/assets?${params.toString()}`);
    items.value = out.items || [];
    recommended.value = query.value.trim() ? [] : (out.recommended || []);
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

async function select(item) {
  selected.value = item;
  note.value = "";
  drawer.value = true;
  try {
    similarAssets.value = await api.get(
      `/catalog/assets/${item.id}/similar`);
  } catch {
    similarAssets.value = [];
  }
}

async function certify(value) {
  if (value) {
    try {
      await ElMessageBox.confirm(t("acat.confirmCertify"),
                                 t("acat.certification"));
    } catch {
      return;
    }
  }
  try {
    selected.value = await api.post(
      `/catalog/assets/${selected.value.id}/certification`,
      { certified: value, note: note.value });
    ElMessage.success(t("acat.done"));
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

async function changeLifecycle(value) {
  if (value !== "active" && !note.value.trim()) {
    ElMessage.warning(t("acat.noteRequired"));
    return;
  }
  if (value !== "active") {
    try {
      await ElMessageBox.confirm(
        value === "archived" ? t("acat.confirmArchive")
          : t("acat.confirmDeprecate"),
        t("acat.lifecycle"));
    } catch {
      return;
    }
  }
  try {
    selected.value = await api.post(
      `/catalog/assets/${selected.value.id}/lifecycle`,
      { lifecycle: value, note: note.value });
    ElMessage.success(t("acat.done"));
    await load();
  } catch (e) {
    ElMessage.error(errMsg(e));
  }
}

function openAsset(item) {
  const base = paths[item.type];
  if (base) router.push(`${base}/${item.id}`);
}

onMounted(load);
</script>

<style scoped>
.asset-catalog { display: flex; flex-direction: column; gap: 14px; }
.toolbar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.spacer { flex: 1; }
.recommend { background: #f8fafc; border: 1px solid #e5e7eb;
             border-radius: 10px; padding: 12px; }
.section-title { font-size: 12px; font-weight: 700; color: #475569;
                 margin: 16px 0 8px; }
.recommend .section-title { margin-top: 0; }
.recommend-grid { display: grid; grid-template-columns: repeat(5, 1fr);
                  gap: 8px; }
.recommend-card { text-align: left; border: 1px solid #e5e7eb;
                  background: #fff; border-radius: 8px; padding: 10px;
                  cursor: pointer; display: flex; flex-direction: column;
                  gap: 5px; }
.recommend-card:hover { border-color: #2563eb; }
.rec-head { display: flex; justify-content: space-between; gap: 6px;
            font-size: 13px; color: #0f172a; }
.rec-meta { font-size: 11px; color: #64748b; }
.rec-score { display: flex; align-items: baseline; gap: 4px; }
.rec-score .score { font-size: 20px; font-weight: 700; color: #2563eb; }
.muted { color: #64748b; font-size: 11px; }
.asset-table { border: 1px solid #e5e7eb; border-radius: 10px; }
.trust-cell { display: flex; align-items: center; gap: 6px; }
.trust-cell :deep(.el-progress) { width: 52px; }
.name-cell { display: flex; flex-direction: column; }
.name-cell small { color: #94a3b8; font-size: 10px; }
.trust-head { display: flex; gap: 16px; align-items: center;
              padding-bottom: 8px; }
.trust-ring { width: 92px; height: 92px; border-radius: 50%;
              border: 6px solid #2563eb; display: flex; flex-direction: column;
              align-items: center; justify-content: center; flex: none; }
.trust-ring b { font-size: 26px; color: #0f172a; }
.trust-ring small { font-size: 10px; color: #64748b; }
.trust-meta p { margin: 4px 0; font-size: 12px; color: #475569; }
.trust-meta .note { background: #fff7ed; border-radius: 4px;
                    padding: 4px 6px; color: #9a3412; }
.factor-list { display: flex; flex-direction: column; gap: 4px; }
.factor-row { display: grid; grid-template-columns: 18px 1fr 1fr 50px;
              gap: 6px; align-items: center; font-size: 12px;
              padding: 5px 7px; border-radius: 5px; background: #f8fafc;
              color: #64748b; }
.factor-row.ok { background: #f0fdf4; color: #166534; }
.factor-check { text-align: center; font-weight: 700; }
.factor-detail { overflow: hidden; text-overflow: ellipsis;
                 white-space: nowrap; font-size: 11px; }
.usage-grid { display: grid; grid-template-columns: repeat(3, 1fr);
              gap: 8px; }
.usage-grid div { background: #f8fafc; border-radius: 8px; padding: 10px;
                  display: flex; flex-direction: column; gap: 2px; }
.usage-grid b { font-size: 22px; color: #0f172a; }
.usage-grid span { font-size: 11px; color: #64748b; }
.actions { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.similar-list { display: flex; flex-direction: column; gap: 4px; }
.similar-row { display: flex; justify-content: space-between;
               align-items: center; padding: 7px 8px; border-radius: 6px;
               background: #f8fafc; cursor: pointer; }
.similar-row:hover { background: #eff6ff; }
.similar-row span { display: flex; flex-direction: column; font-size: 12px; }
.similar-row small { color: #64748b; font-size: 10px; }
@media (max-width: 900px) {
  .recommend-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
