import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { onBeforeRouteLeave } from "vue-router";

export function useDraftSafety({ content, save, delay = 2500 }) {
  const dirty = ref(false);
  const saving = ref(false);
  let timer = null;
  let armed = false;
  let ignoreUntil = 0;

  function onBeforeUnload(event) {
    if (!dirty.value) return;
    event.preventDefault();
    event.returnValue = "";
  }

  async function flush() {
    if (!dirty.value || saving.value) return true;
    saving.value = true;
    try {
      const ok = await save(true);
      if (ok) dirty.value = false;
      return ok;
    } finally {
      saving.value = false;
    }
  }

  watch(content, () => {
    if (!armed || Date.now() < ignoreUntil) return;
    dirty.value = true;
    if (timer) clearTimeout(timer);
    timer = setTimeout(flush, delay);
  }, { deep: true });

  onMounted(() => {
    armed = true;
    window.addEventListener("beforeunload", onBeforeUnload);
  });

  onBeforeUnmount(() => {
    if (timer) clearTimeout(timer);
    window.removeEventListener("beforeunload", onBeforeUnload);
  });

  onBeforeRouteLeave(async () => {
    if (!dirty.value) return true;
    if (timer) clearTimeout(timer);
    return flush();
  });

  function reset() {
    dirty.value = false;
    ignoreUntil = Date.now() + 500;
    if (timer) clearTimeout(timer);
    timer = null;
  }

  return { dirty, saving, flush, reset };
}
