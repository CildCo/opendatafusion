<template>
  <div class="runtime">
    <h3 v-if="page.title">{{ page.title }}</h3>
    <ParamBar :params="page.params || []" :value="values" resettable
              @update:value="setValues" @refresh="$emit('refresh')"
              @reset="resetValues" />

    <AppCanvas v-if="hasLayout" :page="page" :data="data" :params="values"
               :component-state="componentState" :on-submit="onSubmit"
               @navigate="$emit('navigate', $event)"
               @row="onRow" @action="runActions"
               @component-change="onComponentChange" />

    <template v-else>
      <div v-for="c in page.components" v-show="visible(c)" :key="c.id"
           class="component" :class="toneFor(c)"
           :style="visualStyle(c)">
        <div class="title">{{ c.title || c.type }}</div>
        <AppComponent :component="c" :entry="data?.[c.id]" :params="values"
                      :component-state="componentState" :on-submit="onSubmit"
                      @navigate="$emit('navigate', $event)"
                      @row="onRow({ componentId: c.id, row: $event })"
                      @action="runActions"
                      @change="onComponentChange(c.id, $event)" />
      </div>
    </template>

    <el-empty v-if="!page.components?.length"
              :description="t('acomp.noComponents')" />
    <el-drawer v-model="detailOpen" :title="t('acomp.detail')" size="420px">
      <el-descriptions :column="1" border>
        <el-descriptions-item v-for="(v, k) in detailRow" :key="k"
                              :label="k">{{ v }}</el-descriptions-item>
      </el-descriptions>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { getRole } from "../../api";
import { t } from "../../i18n";
import AppCanvas from "./AppCanvas.vue";
import AppComponent from "./AppComponent.vue";
import ParamBar from "../shared/ParamBar.vue";
import { highlightTone, isVisible, visualStyle } from "./bindings";

const props = defineProps({
  page: { type: Object, required: true },
  data: { type: Object, default: () => ({}) },
  params: { type: Object, default: () => ({}) },
  onSubmit: { type: Function, default: null },
});
const emit = defineEmits(["update:params", "refresh", "navigate"]);
const values = reactive({ ...props.params });
const componentState = reactive({});
const detailOpen = ref(false);
const detailRow = ref({});
const hasLayout = computed(() =>
  (props.page?.components || []).some((c) => c.layout));

watch(() => props.params, (next) => {
  Object.keys(values).forEach((k) => delete values[k]);
  Object.assign(values, next || {});
}, { deep: true });

function setValues(next) {
  Object.assign(values, next);
  emit("update:params", { ...values });
}

function resetValues() {
  const defaults = {};
  for (const param of props.page.params || []) {
    if (param.name) defaults[param.name] = param.default ?? "";
  }
  Object.assign(values, defaults);
  emit("update:params", { ...values });
  emit("refresh");
}

function visible(c) {
  return isVisible(c, values, getRole() || "viewer");
}

function toneFor(c) {
  const tone = highlightTone(c, values);
  return tone ? `tone-${tone}` : "";
}

function onComponentChange(componentId, next) {
  componentState[componentId] = {
    ...(componentState[componentId] || {}),
    values: next,
  };
}

function onRow({ componentId, row }) {
  componentState[componentId] = {
    ...(componentState[componentId] || {}),
    selectedRow: row,
  };
  openDetail(row);
}

function runActions(actions) {
  let changed = false;
  let refresh = false;
  for (const action of actions || []) {
    if (action.type === "navigate") {
      emit("navigate", action.page);
    } else if (action.type === "url") {
      window.open(action.url, "_blank", "noopener,noreferrer");
    } else if (action.type === "set_param") {
      values[action.param] = action.value;
      changed = true;
    } else if (action.type === "refresh") {
      refresh = true;
    } else if (action.type === "message") {
      ElMessage.info(action.text);
    }
  }
  if (changed) emit("update:params", { ...values });
  if (refresh) emit("refresh");
}

function openDetail(row) {
  detailRow.value = row;
  detailOpen.value = true;
}
</script>

<style scoped>
.runtime { padding: 4px; }
.filters { display: flex; gap: 10px; align-items: flex-end; flex-wrap: wrap;
           margin-bottom: 14px; padding: 10px; background: #f8fafc;
           border: 1px solid #e5e7eb; border-radius: 0; }
.filter { display: flex; flex-direction: column; gap: 4px;
          font-size: 12px; color: #475569; }
.component { background: #fff; border: 1px solid #e5e7eb;
             border-radius: 0; padding: 12px; margin-bottom: 12px; }
.title { font-weight: 600; font-size: 13px; margin-bottom: 8px;
         color: #0f172a; }
.component.tone-info { border-color: #93c5fd; background: #eff6ff; }
.component.tone-success { border-color: #86efac; background: #f0fdf4; }
.component.tone-warning { border-color: #fcd34d; background: #fffbeb; }
.component.tone-danger { border-color: #fca5a5; background: #fef2f2; }
</style>
