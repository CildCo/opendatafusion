import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";

export function useHistory(source, { limit = 80, debounce = 350 } = {}) {
  const past = ref([]);
  const future = ref([]);
  let last = JSON.stringify(source.value);
  let applying = false;
  let paused = false;
  let timer = null;

  function commit() {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    const now = JSON.stringify(source.value);
    if (now === last) return;
    past.value.push(last);
    if (past.value.length > limit) past.value.shift();
    last = now;
    future.value = [];
  }

  watch(source, () => {
    if (applying || paused) return;
    if (timer) clearTimeout(timer);
    timer = setTimeout(commit, debounce);
  }, { deep: true });

  function pause() {
    paused = true;
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
  }

  function resume() {
    paused = false;
  }

  function apply(value) {
    applying = true;
    source.value = JSON.parse(value);
    nextTick(() => { applying = false; });
  }

  function undo() {
    commit();
    if (!past.value.length) return false;
    future.value.push(last);
    last = past.value.pop();
    apply(last);
    return true;
  }

  function redo() {
    if (!future.value.length) return false;
    past.value.push(last);
    last = future.value.pop();
    apply(last);
    return true;
  }

  function reset() {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    past.value = [];
    future.value = [];
    last = JSON.stringify(source.value);
    applying = true;
    nextTick(() => { applying = false; });
  }

  const canUndo = computed(() => past.value.length > 0);
  const canRedo = computed(() => future.value.length > 0);
  return { undo, redo, reset, commit, pause, resume, canUndo, canRedo };
}

export function bindHistoryKeys(history) {
  function onKey(event) {
    if (!(event.ctrlKey || event.metaKey)) return;
    const key = String(event.key || "").toLowerCase();
    if (key !== "z" && key !== "y") return;
    const target = event.target;
    if (target && target.closest &&
        target.closest('input, textarea, select, [contenteditable="true"], '
                       + '.cm-editor, .el-select__input')) {
      return;
    }
    const redo = key === "y" || (key === "z" && event.shiftKey);
    if (redo ? history.redo() : history.undo()) {
      event.preventDefault();
    }
  }
  window.addEventListener("keydown", onKey);
  onBeforeUnmount(() => window.removeEventListener("keydown", onKey));
}
