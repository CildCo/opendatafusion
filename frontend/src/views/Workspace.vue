<template>
  <div class="page">
    <div class="toolbar">
      <el-tag size="small" type="info">按项目生效</el-tag>
      <div class="spacer" />
      <el-button size="small" @click="load" :loading="loading">刷新</el-button>
      <el-button type="primary" size="small" :loading="saving"
                 @click="save">保存</el-button>
    </div>

    <el-card shadow="never">
      <el-form label-width="110px" style="max-width: 680px">
        <el-form-item label="品牌名称">
          <el-input v-model="form.brand_name" maxlength="64" />
        </el-form-item>
        <el-form-item label="主题色">
          <el-color-picker v-model="form.primary_color" />
          <span class="hint" style="margin-left: 10px">
            {{ form.primary_color }}
          </span>
        </el-form-item>
        <el-form-item label="欢迎标题">
          <el-input v-model="form.welcome_title" maxlength="128"
                    placeholder="例如：欢迎使用数据平台" />
        </el-form-item>
        <el-form-item label="欢迎说明">
          <el-input v-model="form.welcome_text" type="textarea" :rows="3"
                    maxlength="1000" show-word-limit />
        </el-form-item>
        <el-form-item label="隐藏菜单">
          <el-checkbox-group v-model="form.hidden_menus" class="menus">
            <el-checkbox v-for="m in menus" :key="m.path" :value="m.path">
              {{ m.title }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="菜单权限">
          <el-checkbox-group v-model="allowedMenus" class="menus">
            <el-checkbox v-for="m in menus" :key="m.path" :value="m.path">
              {{ m.title }}
            </el-checkbox>
          </el-checkbox-group>
          <p class="hint">
            仅对非管理员生效；勾选为空表示不限制。隐藏菜单只影响界面，菜单权限会同时拦截后端接口。
          </p>
        </el-form-item>
      </el-form>
      <p class="hint">
        设置保存后立即应用到侧边栏品牌、主题色和菜单可见性。
      </p>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { api, errMsg } from "../api";

const menus = [
  { path: "/dashboard", title: "概览" },
  { path: "/ops", title: "运维中心" },
  { path: "/datasources", title: "数据源" },
  { path: "/catalog", title: "数据目录" },
  { path: "/workbench", title: "SQL 工作台" },
  { path: "/pipelines", title: "数据管道" },
  { path: "/flows", title: "数据集成" },
  { path: "/apis", title: "数据接口" },
  { path: "/tools", title: "AI 工具" },
  { path: "/datasets", title: "数据模型" },
  { path: "/dashboards", title: "数据看板" },
  { path: "/apps", title: "数据应用" },
  { path: "/quality", title: "数据质量" },
  { path: "/alerts", title: "告警" },
  { path: "/changes", title: "变更" },
  { path: "/grants", title: "接口授权" },
  { path: "/webhooks", title: "事件订阅" },
  { path: "/files", title: "文件" },
  { path: "/workspace", title: "工作区设置" },
  { path: "/security", title: "账号安全" },
];
const form = reactive({ brand_name: "OpenDataFusion",
                        primary_color: "#1d4ed8", welcome_title: "",
                        welcome_text: "", hidden_menus: [] });
const loading = ref(false);
const saving = ref(false);
const allowedMenus = ref([]);

async function load() {
  loading.value = true;
  try {
    const data = await api.get("/portal");
    Object.assign(form, data);
    allowedMenus.value = data.allowed_menus || [];
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    loading.value = false;
  }
}

async function save() {
  saving.value = true;
  try {
    const payload = { ...form,
                      allowed_menus: allowedMenus.value.length
                        ? allowedMenus.value : null };
    Object.assign(form, await api.put("/portal", payload));
    ElMessage.success("已保存，正在刷新");
    setTimeout(() => window.location.reload(), 500);
  } catch (e) {
    ElMessage.error(errMsg(e));
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.toolbar { display: flex; gap: 10px; align-items: center;
           margin-bottom: 12px; }
.title { font-size: 16px; font-weight: 700; color: #0f172a; }
.spacer { flex: 1; }
.hint { color: #6b7280; font-size: 12px; }
.menus { display: grid; grid-template-columns: repeat(3, 1fr); gap: 2px; }
</style>
