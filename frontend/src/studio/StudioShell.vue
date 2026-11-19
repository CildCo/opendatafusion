<template>
  <div class="studio">
    <header class="studio-head">
      <div class="left">
        <el-button link @click="$router.push('/pipelines')":aria-label="t('common.back')">←</el-button>
        <el-input :model-value="title" size="small" style="width: 200px"
                  @update:model-value="$emit('rename', $event)"
                  @change="$emit('rename-save', $event)" />
        <el-input :model-value="cron" size="small" style="width: 140px"
                  :placeholder="t('shell.cronPlaceholder')"
                  @change="$emit('schedule', $event)" />
        <el-tag size="small" :type="published ? 'success' : 'info'">
          {{ published ? t("shell.published") : t("shell.draft") }}
        </el-tag>
      </div>
      <div class="right">
        <el-button size="small" :loading="saving" @click="$emit('save')">{{ t("shell.save") }}</el-button>
        <el-button size="small" @click="$emit('validate')">{{ t("shell.validate") }}</el-button>
        <el-button size="small" @click="$emit('preview')">{{ t("shell.preview") }}</el-button>
        <el-button size="small" @click="$emit('run')">{{ t("shell.run") }}</el-button>
        <el-button size="small" @click="$emit('backfill')">{{ t("shell.backfill") }}</el-button>
        <el-button size="small" @click="$emit('cursors')">{{ t("shell.cursors") }}</el-button>
        <el-button size="small" @click="$emit('toggle')">
          {{ enabled ? t("shell.disable") : t("shell.enable") }}
        </el-button>
        <el-button size="small" type="primary" @click="$emit('publish')">{{ t("shell.publish") }}</el-button>
        <el-button size="small" @click="$emit('versions')">{{ t("shell.versions") }}</el-button>
      </div>
    </header>
    <div class="studio-body">
      <aside class="tree"><slot name="tree" /></aside>
      <main class="canvas"><slot /></main>
      <aside class="config"><slot name="config" /></aside>
    </div>
    <footer class="console"><slot name="console" /></footer>
  </div>
</template>

<script setup>
import { t } from "../i18n";

defineProps({
  title: { type: String, default: "" },
  cron: { type: String, default: "" },
  published: Boolean,
  enabled: Boolean,
  saving: Boolean,
});
defineEmits(["save", "validate", "preview", "run", "backfill", "cursors",
             "toggle", "publish", "versions", "rename", "rename-save",
             "schedule"]);
</script>

<style scoped>
.studio {
  height: calc(100vh - 96px);
  margin: 16px 20px;
  display: flex;
  flex-direction: column;
  background: var(--odf-paper);
  border: 1px solid var(--odf-rule);
  border-radius: 0;
  overflow: hidden;
}
.studio-head {
  height: 48px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 12px;
  background: #fff;
  border-bottom: 1px solid var(--odf-rule);
}
.left, .right { display: flex; align-items: center; gap: 6px; min-width: 0; }
.left :deep(.el-input__wrapper) { min-height: 28px; }
.studio-body {
  flex: 1;
  display: grid;
  grid-template-columns: 218px minmax(0, 1fr) 318px;
  min-height: 0;
}
.tree, .config { background: #fff; overflow: auto; }
.tree { border-right: 1px solid var(--odf-rule); }
.config { border-left: 1px solid var(--odf-rule); }
.canvas { min-width: 0; position: relative; background: #f8f9fb; }
.console {
  height: 214px;
  flex: none;
  background: #fff;
  border-top: 1px solid var(--odf-rule);
  overflow: auto;
}
@media (max-width: 1180px) {
  .studio { margin: 10px; height: calc(100vh - 84px); }
  .studio-body { grid-template-columns: 180px minmax(0, 1fr) 280px; }
}
@media (max-width: 900px) {
  .studio { margin: 8px; height: auto; min-height: calc(100vh - 80px); }
  .studio-head { height: auto; padding: 8px 10px; flex-wrap: wrap; }
  .studio-body { grid-template-columns: 1fr; }
  .tree, .config { display: none; }
  .console { height: 180px; }
}
</style>
