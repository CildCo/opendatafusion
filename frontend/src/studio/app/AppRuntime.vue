<template>
  <div class="runtime">
    <h3 v-if="page.title">{{ page.title }}</h3>
    <div v-if="page.params?.length" class="filters">
      <div v-for="p in page.params" :key="p.name" class="filter">
        <span>{{ p.name }}</span>
        <el-select v-if="p.type === 'bool'" v-model="values[p.name]"
                   size="small" style="width: 110px"
                   @change="$emit('update:params', { ...values })">
          <el-option :label="t('acomp.all')" :value="''" />
          <el-option :label="t('acomp.yes')" :value="true" />
          <el-option :label="t('acomp.no')" :value="false" />
        </el-select>
        <el-input v-else v-model="values[p.name]" size="small"
                  style="width: 150px"
                  :placeholder="p.example || p.type"
                  @change="$emit('update:params', { ...values })" />
      </div>
      <el-button type="primary" size="small" @click="$emit('refresh')">
        {{ t("acomp.query") }}
      </el-button>
    </div>

    <AppCanvas v-if="hasLayout" :page="page" :data="data" :params="values"
               :on-submit="onSubmit" @navigate="$emit('navigate', $event)"
               @row="openDetail" />

    <template v-else>
      <div v-for="c in page.components" v-show="visible(c)" :key="c.id"
           class="component">
        <div class="title">{{ c.title || c.type }}</div>
        <AppComponent :component="c" :entry="data?.[c.id]" :params="values"
                      :on-submit="onSubmit"
                      @navigate="$emit('navigate', $event)"
                      @row="openDetail" />
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
import { t } from "../../i18n";
import AppCanvas from "./AppCanvas.vue";
import AppComponent from "./AppComponent.vue";
import { isVisible } from "./bindings";

const props = defineProps({
  page: { type: Object, required: true },
  data: { type: Object, default: () => ({}) },
  params: { type: Object, default: () => ({}) },
  onSubmit: { type: Function, default: null },
});
defineEmits(["update:params", "refresh", "navigate"]);
const values = reactive({ ...props.params });
const detailOpen = ref(false);
const detailRow = ref({});
const hasLayout = computed(() =>
  (props.page?.components || []).some((c) => c.layout));

watch(() => props.params, (next) => {
  Object.keys(values).forEach((k) => delete values[k]);
  Object.assign(values, next || {});
}, { deep: true });

function visible(c) {
  return isVisible(c, values);
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
</style>
