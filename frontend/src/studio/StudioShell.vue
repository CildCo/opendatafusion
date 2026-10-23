<template>
  <div class="studio">
    <header class="studio-head">
      <div class="left">
        <el-button link @click="$router.push('/pipelines')">←</el-button>
        <el-input :model-value="title" size="small" style="width: 200px"
                  @update:model-value="$emit('rename', $event)"
                  @change="$emit('rename-save', $event)" />
        <el-input :model-value="cron" size="small" style="width: 140px"
                  placeholder="cron（可选）"
                  @change="$emit('schedule', $event)" />
        <el-tag size="small" :type="published ? 'success' : 'info'">
          {{ published ? "已发布" : "草稿" }}
        </el-tag>
      </div>
      <div class="right">
        <el-button size="small" :loading="saving" @click="$emit('save')">保存</el-button>
        <el-button size="small" @click="$emit('validate')">校验</el-button>
        <el-button size="small" @click="$emit('preview')">预览</el-button>
        <el-button size="small" @click="$emit('run')">运行</el-button>
        <el-button size="small" @click="$emit('backfill')">回填</el-button>
        <el-button size="small" @click="$emit('cursors')">游标</el-button>
        <el-button size="small" @click="$emit('toggle')">
          {{ enabled ? "停用" : "启用" }}
        </el-button>
        <el-button size="small" type="primary" @click="$emit('publish')">发布</el-button>
        <el-button size="small" @click="$emit('versions')">版本</el-button>
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
