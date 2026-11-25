<template>
  <el-dialog :model-value="modelValue" :title="t('gallery.title')"
             width="720px" @update:model-value="close">
    <el-input v-model="query" :placeholder="t('gallery.search')" clearable
              style="margin-bottom: 12px" />
    <div class="gallery">
      <button v-for="item in filtered" :key="item.type" type="button"
              class="tile" @click="choose(item.type)">
        <span class="preview" :class="item.type">
          <span class="shape" />
        </span>
        <b>{{ t(item.label) }}</b>
        <small>{{ t(item.note) }}</small>
      </button>
    </div>
    <el-empty v-if="!filtered.length" :description="t('gallery.empty')" />
    <template #footer>
      <el-button @click="close(false)">{{ t("common.cancel") }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref } from "vue";
import { t } from "../../i18n";

defineProps({ modelValue: Boolean });
const emit = defineEmits(["update:modelValue", "select"]);
const query = ref("");

const items = [
  { type: "card", label: "dedit.typeCard", note: "gallery.noteCard" },
  { type: "line", label: "dedit.typeLine", note: "gallery.noteTrend" },
  { type: "bar", label: "dedit.typeBar", note: "gallery.noteCompare" },
  { type: "area", label: "dedit.typeArea", note: "gallery.noteTrend" },
  { type: "pie", label: "dedit.typePie", note: "gallery.noteShare" },
  { type: "pivot", label: "dedit.typePivot", note: "gallery.noteMatrix" },
  { type: "table", label: "dedit.typeTable", note: "gallery.noteRows" },
  { type: "map", label: "dedit.typeMap", note: "gallery.noteGeo" },
  { type: "text", label: "dedit.text", note: "gallery.noteText" },
];

const filtered = computed(() => {
  const needle = query.value.trim().toLowerCase();
  if (!needle) return items;
  return items.filter((item) =>
    `${t(item.label)} ${t(item.note)} ${item.type}`
      .toLowerCase().includes(needle));
});

function close(value) {
  emit("update:modelValue", value);
}

function choose(type) {
  emit("select", type);
  close(false);
}
</script>

<style scoped>
.gallery {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;
}
.tile {
  display: flex; flex-direction: column; align-items: flex-start;
  gap: 3px; padding: 10px; border: 1px solid #e5e7eb; border-radius: 8px;
  background: #fff; cursor: pointer; text-align: left;
}
.tile:hover { border-color: #2563eb; }
.tile b { font-size: 13px; color: #0f172a; }
.tile small { font-size: 11px; color: #64748b; }
.preview {
  width: 100%; height: 58px; border-radius: 6px; background: #f8fafc;
  display: flex; align-items: flex-end; justify-content: center;
  gap: 4px; padding: 6px; margin-bottom: 4px;
}
.shape { display: block; background: #2563eb; border-radius: 2px; }
.card .shape { width: 54%; height: 22px; align-self: center; }
.line .shape, .area .shape {
  width: 70%; height: 30px; clip-path: polygon(0 70%, 25% 40%, 50% 60%,
    75% 15%, 100% 25%, 100% 100%, 0 100%);
}
.bar .shape { width: 60%; height: 32px;
  background: repeating-linear-gradient(90deg, #2563eb 0 8px,
    transparent 8px 14px); }
.pie .shape { width: 34px; height: 34px; border-radius: 50%;
  background: conic-gradient(#2563eb 0 60%, #93c5fd 60% 100%); }
.pivot .shape, .table .shape { width: 64%; height: 34px;
  background: repeating-linear-gradient(#2563eb 0 2px, transparent 2px 9px),
    repeating-linear-gradient(90deg, #2563eb 0 2px, transparent 2px 12px); }
.map .shape { width: 60%; height: 34px; clip-path: polygon(10% 20%, 40% 5%,
  70% 20%, 95% 10%, 90% 70%, 60% 95%, 25% 80%, 5% 45%); }
.text .shape { width: 64%; height: 30px;
  background: repeating-linear-gradient(#94a3b8 0 3px, transparent 3px 9px); }
</style>
