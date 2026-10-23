<template>
  <div ref="host" class="sql-editor"></div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { EditorView, basicSetup } from "codemirror";
import { sql } from "@codemirror/lang-sql";

const props = defineProps({ modelValue: { type: String, default: "" } });
const emit = defineEmits(["update:modelValue"]);
const host = ref(null);
let view = null;

onMounted(() => {
  view = new EditorView({
    doc: props.modelValue || "",
    extensions: [
      basicSetup,
      sql(),
      EditorView.updateListener.of((u) => {
        if (u.docChanged) emit("update:modelValue", u.state.doc.toString());
      }),
    ],
    parent: host.value,
  });
});

watch(() => props.modelValue, (v) => {
  if (view && v !== view.state.doc.toString()) {
    view.dispatch({ changes: {
      from: 0, to: view.state.doc.length, insert: v || "",
    } });
  }
});

onBeforeUnmount(() => view?.destroy());
</script>

<style scoped>
.sql-editor { height: 100%; min-height: 320px; }
.sql-editor :deep(.cm-editor) { height: 100%; font-size: 13px; }
.sql-editor :deep(.cm-scroller) { font-family: ui-monospace, monospace; }
</style>
