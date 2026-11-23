<template>
  <teleport to="body">
    <div v-if="modelValue" class="cmd-overlay" @click.self="close">
      <div class="cmd-panel" role="dialog" aria-label="Search">
        <div class="cmd-input">
          <el-icon><Search /></el-icon>
          <input ref="input" v-model="query" :placeholder="t('search.placeholder')"
                 @keydown.down.prevent="move(1)"
                 @keydown.up.prevent="move(-1)"
                 @keydown.enter.prevent="choose()"
                 @keydown.esc.prevent="close" />
          <kbd>Esc</kbd>
        </div>
        <div ref="list" class="cmd-list">
          <template v-for="group in groups" :key="group.label">
            <div class="cmd-group">{{ group.label }}</div>
            <button v-for="item in group.items" :key="item.route + item.label"
                    type="button" class="cmd-item"
                    :class="{ active: item === current }"
                    @mouseenter="active = item"
                    @click="open(item)">
              <entity-icon :type="item.type" :size="20" />
              <span class="label">{{ item.label }}</span>
              <span class="sub">{{ item.sub }}</span>
            </button>
          </template>
          <div v-if="!groups.length" class="cmd-empty">
            {{ t("search.empty") }}
          </div>
        </div>
        <div class="cmd-foot">{{ t("search.hint") }}</div>
      </div>
    </div>
  </teleport>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { Search } from "@element-plus/icons-vue";
import { api } from "../api";
import { t } from "../i18n";
import { loadRecent, pushRecent } from "../recent";
import EntityIcon from "./EntityIcon.vue";

const props = defineProps({ modelValue: { type: Boolean, default: false } });
const emit = defineEmits(["update:modelValue"]);

const router = useRouter();
const query = ref("");
const input = ref(null);
const list = ref(null);
const active = ref(0);
const current = ref(null);
const lists = ref(null);
const catalog = ref({ tables: [], columns: [] });
const recent = ref([]);
let timer = null;

const TYPE_LABEL = {
  table: "search.group.table",
  dataset: "search.group.dataset",
  metric: "search.group.metric",
  pipeline: "search.group.pipeline",
  flow: "search.group.flow",
  interface: "search.group.interface",
  api: "search.group.api",
  dashboard: "search.group.dashboard",
  app: "search.group.app",
  job: "search.group.job",
};
const ORDER = ["table", "dataset", "metric", "pipeline", "flow", "interface",
               "api", "dashboard", "app", "job"];

function close() {
  emit("update:modelValue", false);
}

async function loadLists() {
  if (lists.value) return lists.value;
  const names = ["datasets", "metrics", "interfaces", "flows", "pipelines",
                 "dashboards", "apps", "apis"];
  const results = await Promise.allSettled(
    names.map((name) => api.get(`/${name}`)));
  const data = {};
  names.forEach((name, index) => {
    const result = results[index];
    data[name] = result.status === "fulfilled" && Array.isArray(result.value)
      ? result.value : [];
  });
  try {
    data.jobs = await api.get("/ops/jobs?limit=100");
  } catch {
    data.jobs = [];
  }
  lists.value = data;
  return data;
}

function itemsFrom(list) {
  const out = [];
  for (const row of list.datasets || []) {
    out.push({ type: "dataset", label: row.name, sub: row.key || "",
               route: `/datasets/${row.id}` });
  }
  for (const row of list.metrics || []) {
    out.push({ type: "metric", label: row.name, sub: row.key || "",
               route: `/metrics/${row.id}` });
  }
  for (const row of list.pipelines || []) {
    out.push({ type: "pipeline", label: row.name, sub: row.cron || "",
               route: `/pipelines/${row.id}` });
  }
  for (const row of list.flows || []) {
    out.push({ type: "flow", label: row.name, sub: row.cron || "",
               route: `/flows/${row.id}` });
  }
  for (const row of list.interfaces || []) {
    out.push({ type: "interface", label: row.name, sub: row.key || "",
               route: "/interfaces" });
  }
  for (const row of list.apis || []) {
    out.push({ type: "api", label: row.name, sub: row.key || "",
               route: `/apis/${row.id}` });
  }
  for (const row of list.dashboards || []) {
    out.push({ type: "dashboard", label: row.name, sub: "",
               route: `/dashboards/${row.id}/run` });
  }
  for (const row of list.apps || []) {
    out.push({ type: "app", label: row.name, sub: "",
               route: `/apps/${row.id}/run` });
  }
  for (const row of list.jobs || []) {
    out.push({ type: "job", label: row.name || row.target_name || "",
               sub: row.status || "", route: "/ops" });
  }
  return out;
}

function matches(item, text) {
  if (!text) return true;
  const hay = `${item.label} ${item.sub} ${item.type}`.toLowerCase();
  return hay.includes(text);
}

const groups = computed(() => {
  const text = query.value.trim().toLowerCase();
  const source = lists.value ? itemsFrom(lists.value) : [];
  try {
    for (const row of catalog.value.tables || []) {
      source.push({ type: "table", label: row.table,
                    sub: row.schema || "", route: `/catalog/${row.id}` });
    }
    for (const row of catalog.value.columns || []) {
      source.push({ type: "table", label: row.column,
                    sub: `${row.table}`,
                    route: `/catalog/${row.dataset_id}` });
    }
  } catch { /* ignore */ }

  if (!text) {
    const items = recent.value.slice(0, 8);
    return items.length ? [{ label: t("search.recent"), items }] : [];
  }
  const grouped = new Map();
  for (const item of source) {
    if (!matches(item, text)) continue;
    if (!grouped.has(item.type)) grouped.set(item.type, []);
    if (grouped.get(item.type).length < 6) grouped.get(item.type).push(item);
  }
  const out = [];
  for (const type of ORDER) {
    if (!grouped.has(type)) continue;
    out.push({ label: t(TYPE_LABEL[type]), items: grouped.get(type) });
  }
  return out;
});

const flat = computed(() => groups.value.flatMap((g) => g.items));

watch(flat, () => {
  active.value = 0;
  current.value = flat.value[0] || null;
});

watch(active, () => {
  current.value = flat.value[active.value] || null;
  nextTick(() => {
    const node = list.value?.querySelector(".cmd-item.active");
    node?.scrollIntoView({ block: "nearest" });
  });
});

watch(query, (value) => {
  if (timer) clearTimeout(timer);
  const text = value.trim();
  if (!text) {
    catalog.value = { tables: [], columns: [] };
    return;
  }
  timer = setTimeout(async () => {
    try {
      catalog.value = await api.get(
        `/catalog/search?q=${encodeURIComponent(text)}&limit=20`);
    } catch {
      catalog.value = { tables: [], columns: [] };
    }
  }, 220);
});

watch(() => props.modelValue, async (open) => {
  if (!open) return;
  query.value = "";
  active.value = 0;
  recent.value = loadRecent().map((entry) => ({
    ...entry, label: entry.key ? t(entry.key) : entry.label,
  }));
  await nextTick();
  input.value?.focus();
  await loadLists();
});

function move(delta) {
  if (!flat.value.length) return;
  active.value = (active.value + delta + flat.value.length)
    % flat.value.length;
}

async function choose() {
  if (current.value) open(current.value);
}

function open(item) {
  pushRecent({ type: item.type, label: item.label, sub: item.sub,
               route: item.route });
  close();
  router.push(item.route);
}

onMounted(() => {
  recent.value = loadRecent();
});
</script>

<style scoped>
.cmd-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  z-index: 3000;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 12vh;
}
.cmd-panel {
  width: min(680px, 92vw);
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.3);
  overflow: hidden;
}
.cmd-input {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid #eef2f6;
}
.cmd-input input {
  flex: 1;
  border: 0;
  outline: 0;
  font-size: 15px;
  color: #0f172a;
  background: transparent;
}
.cmd-input kbd {
  font-size: 11px;
  color: #94a3b8;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  padding: 2px 6px;
}
.cmd-list {
  max-height: 52vh;
  overflow: auto;
  padding: 6px 8px 10px;
}
.cmd-group {
  font-size: 11px;
  color: #94a3b8;
  padding: 8px 10px 4px;
  letter-spacing: 0.04em;
}
.cmd-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: 0;
  background: transparent;
  text-align: left;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  color: #1e293b;
}
.cmd-item.active { background: #eff4ff; }
.cmd-item .label { flex: 1; min-width: 0; overflow: hidden;
                   text-overflow: ellipsis; white-space: nowrap; }
.cmd-item .sub { color: #94a3b8; font-size: 11px; }
.cmd-empty { padding: 28px; text-align: center; color: #94a3b8; }
.cmd-foot {
  border-top: 1px solid #eef2f6;
  padding: 8px 16px;
  font-size: 11px;
  color: #94a3b8;
}
</style>
