<template>
  <div ref="host" class="sql-editor"></div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { EditorView, basicSetup } from "codemirror";
import { sql } from "@codemirror/lang-sql";

const props = defineProps({
  modelValue: { type: String, default: "" },
  schema: { type: Object, default: null },
});
const emit = defineEmits(["update:modelValue"]);
const host = ref(null);
let view = null;

function build() {
  const doc = props.modelValue || "";
  const cursor = view ? view.state.selection.main.head : null;
  if (view) view.destroy();
  view = new EditorView({
    doc,
    selection: cursor === null ? undefined
      : { anchor: Math.min(cursor, doc.length) },
    extensions: [
      basicSetup,
      sql(props.schema && Object.keys(props.schema).length
        ? { schema: props.schema } : {}),
      EditorView.updateListener.of((u) => {
        if (u.docChanged) emit("update:modelValue", u.state.doc.toString());
      }),
    ],
    parent: host.value,
  });
}

onMounted(build);
watch(() => props.schema, build, { deep: true });

watch(() => props.modelValue, (v) => {
  if (view && v !== view.state.doc.toString()) {
    view.dispatch({ changes: {
      from: 0, to: view.state.doc.length, insert: v || "",
    } });
  }
});

defineExpose({
  insert(text) {
    if (!view) return;
    const pos = view.state.selection.main.head;
    view.dispatch({
      changes: { from: pos, insert: text },
      selection: { anchor: pos + text.length },
    });
    view.focus();
  },
});

onBeforeUnmount(() => view?.destroy());
</script>

<style scoped>
.sql-editor { height: 100%; min-height: 320px; }
.sql-editor :deep(.cm-editor) { height: 100%; font-size: 13px; }
.sql-editor :deep(.cm-scroller) { font-family: ui-monospace, monospace; }
</style>
