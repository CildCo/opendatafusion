<template>
  <div class="app-form">
    <el-form label-position="top" size="small">
      <el-form-item v-for="f in component.fields || []" :key="f.column"
                    :label="f.widget === 'checkbox' ? '' : (f.label || f.column)"
                    :required="Boolean(f.required)">
        <el-input v-if="f.widget === 'input'" v-model="values[f.column]"
                  :placeholder="f.placeholder || ''" />
        <el-input v-else-if="f.widget === 'textarea'"
                  v-model="values[f.column]" type="textarea" :rows="3" />
        <el-input-number v-else-if="f.widget === 'number'"
                         v-model="values[f.column]" style="width: 100%"
                         :controls="false" />
        <el-date-picker v-else-if="f.widget === 'date'"
                        v-model="values[f.column]" type="date"
                        value-format="YYYY-MM-DD" style="width: 100%" />
        <el-select v-else-if="f.widget === 'select'"
                   v-model="values[f.column]" style="width: 100%"
                   clearable filterable>
          <el-option v-for="o in f.options || []" :key="o" :value="o"
                     :label="o" />
        </el-select>
        <el-checkbox v-else-if="f.widget === 'checkbox'"
                     v-model="values[f.column]">
          {{ f.label || f.column }}
        </el-checkbox>
      </el-form-item>
    </el-form>
    <el-alert v-if="!allowed" title="当前角色无提交权限" type="info"
              :closable="false" />
    <el-button v-else :type="component.mode === 'delete' ? 'danger' : 'primary'"
               size="small" :loading="loading" @click="submit">
      {{ component.submit_text || (component.mode === "delete" ? "删除" : "提交") }}
    </el-button>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { getRole } from "../../api";

const props = defineProps({
  component: { type: Object, required: true },
  onSubmit: { type: Function, default: null },
});
const values = reactive({});
const loading = ref(false);
const role = getRole() || "viewer";
const allowed = computed(() => {
  const roles = props.component.allow_roles;
  return !roles?.length || roles.includes(role);
});

function reset() {
  Object.keys(values).forEach((k) => delete values[k]);
  for (const f of props.component.fields || []) {
    if (!f.column) continue;
    const fallback = f.widget === "checkbox" ? false
      : (f.widget === "number" ? null : "");
    if (props.component.mode === "insert" && f.default !== undefined
        && f.default !== null && f.default !== "") {
      if (f.widget === "checkbox") {
        values[f.column] = f.default === true || ["1", "true", "yes", "y"]
          .includes(String(f.default).toLowerCase());
      } else {
        values[f.column] = f.default;
      }
    } else {
      values[f.column] = fallback;
    }
  }
}

watch(() => props.component.id, reset, { immediate: true });
watch(() => props.component.fields, reset, { deep: true });

async function submit() {
  for (const f of props.component.fields || []) {
    const v = values[f.column];
    if (f.required && (v === "" || v === null || v === undefined)) {
      ElMessage.error(`请填写 ${f.label || f.column}`);
      return;
    }
    if (f.widget === "select" && v && !(f.options || []).includes(v)) {
      ElMessage.error(`${f.label || f.column} 选项无效`);
      return;
    }
  }
  if (!props.onSubmit || !allowed.value || loading.value) return;
  loading.value = true;
  if (props.component.mode === "delete") {
    try {
      await ElMessageBox.confirm("确认删除这条记录？此操作不可撤销。",
                                 "删除确认", { type: "warning" });
    } catch (e) {
      loading.value = false;
      return;
    }
  }
  try {
    await props.onSubmit(props.component.id, { ...values });
    ElMessage.success(props.component.success_message || "提交成功");
    reset();
  } catch (e) {
    ElMessage.error(e?.message || "提交失败");
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.app-form { max-width: 520px; }
</style>
