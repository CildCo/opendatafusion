<template>
  <div class="page-header">
    <entity-icon v-if="icon" :type="icon" :size="34" />
    <div class="text">
      <h2>{{ title }}</h2>
      <p v-if="intro">{{ intro }}</p>
      <p v-else-if="$slots.sub" class="sub"><slot name="sub" /></p>
    </div>
    <div class="actions">
      <a class="help" :href="helpUrl" target="_blank" rel="noopener"
         :title="t('common.help')" :aria-label="t('common.help')">?</a>
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";
import { locale, t } from "../i18n";
import EntityIcon from "./EntityIcon.vue";

const route = useRoute();
const BASE = "https://github.com/CildCo/opendatafusion/blob/main/docs/";
const SECTIONS = {
  "/dashboard": "2-overview",
  "/ops": "3-operations-centre",
  "/datasources": "4-data-sources",
  "/catalog": "5-catalog",
  "/workbench": "6-sql-workbench",
  "/files": "7-files",
  "/pipelines": "8-pipelines",
  "/engines": "9-engines",
  "/cdc": "10-change-data-capture",
  "/datasets": "12-data-models",
  "/metrics": "12-data-models",
  "/dashboards": "13-dashboards",
  "/apps": "14-apps",
  "/grants": "16-access-control",
  "/webhooks": "17-webhooks",
  "/quality": "18-data-quality",
  "/alerts": "19-alerts",
  "/changes": "20-changes",
  "/tools": "21-ai-tools",
  "/users": "22-users-and-members",
  "/workspace": "23-workspace-settings",
  "/security": "24-account-security",
  "/audit": "25-audit",
};

const helpUrl = computed(() => {
  const entry = Object.keys(SECTIONS)
    .sort((a, b) => b.length - a.length)
    .find((path) => route.path === path || route.path.startsWith(path + "/"));
  if (locale.value === "zh") {
    return BASE + "USER_GUIDE.zh-CN.md";
  }
  const section = entry ? SECTIONS[entry] : "";
  return BASE + "USER_GUIDE.md" + (section ? "#" + section : "");
});

defineProps({
  icon: { type: String, default: "" },
  title: { type: String, required: true },
  intro: { type: String, default: "" },
});
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 4px 2px 14px;
  border-bottom: 1px solid #eef2f6;
  margin-bottom: 14px;
}
.text { min-width: 0; }
h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 650;
  color: #0f172a;
  letter-spacing: -0.01em;
}
p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}
.actions { margin-left: auto; display: flex; align-items: center;
           gap: 8px; }
.help {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 1px solid #dbe3ee;
  color: #64748b;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  text-decoration: none;
}
.help:hover { border-color: #bfd3ff; color: #1d4ed8; }
</style>
