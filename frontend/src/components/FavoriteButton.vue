<template>
  <el-tooltip :content="tooltip" placement="bottom">
    <el-button link class="fav-button" :aria-label="tooltip"
               :loading="loading" @click="toggle">
      <el-icon :class="{ on: favorite }">
        <StarFilled v-if="favorite" />
        <Star v-else />
      </el-icon>
    </el-button>
  </el-tooltip>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { Star, StarFilled } from "@element-plus/icons-vue";
import { api, errMsg } from "../api";
import { t } from "../i18n";

const props = defineProps({
  type: { type: String, required: true },
  id: { type: Number, required: true },
});
const emit = defineEmits(["change"]);

const favorite = ref(false);
const loading = ref(false);
const tooltip = computed(() =>
  favorite.value ? t("fav.remove") : t("fav.add"));

async function load() {
  if (!props.id) return;
  try {
    const out = await api.get(
      `/favorites/check?object_type=${encodeURIComponent(props.type)}`
      + `&object_id=${props.id}`);
    favorite.value = Boolean(out.favorite);
  } catch {
    favorite.value = false;
  }
}

async function toggle() {
  if (!props.id || loading.value) return;
  loading.value = true;
  try {
    if (favorite.value) {
      await api.del(`/favorites/${props.type}/${props.id}`);
      favorite.value = false;
      ElMessage.success(t("fav.removed"));
    } else {
      await api.post("/favorites", {
        object_type: props.type, object_id: props.id,
      });
      favorite.value = true;
      ElMessage.success(t("fav.added"));
    }
    emit("change", favorite.value);
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

watch(() => [props.type, props.id], load);
onMounted(load);
</script>

<style scoped>
.fav-button { padding: 2px; }
.fav-button .el-icon { font-size: 17px; color: #94a3b8; }
.fav-button .el-icon.on { color: #f59e0b; }
</style>
