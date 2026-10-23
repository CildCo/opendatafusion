<template>
  <div class="params">
    <div class="head">
      <span>参数</span>
      <el-button link type="primary" @click="params.push(newParam())">
        + 参数
      </el-button>
    </div>
    <div v-for="(p, i) in params" :key="i" class="param">
      <el-input v-model="p.name" placeholder="名称" size="small" />
      <el-select v-model="p.type" size="small" style="width: 92px">
        <el-option value="string" label="字符串" />
        <el-option value="number" label="数字" />
        <el-option value="date" label="日期" />
        <el-option value="bool" label="布尔" />
      </el-select>
      <el-checkbox v-model="p.required" size="small">必填</el-checkbox>
      <el-input v-model="p.default" placeholder="默认值" size="small" />
      <el-input v-model="p.example" placeholder="示例" size="small" />
      <el-button link type="danger" @click="params.splice(i, 1)">×</el-button>
    </div>
    <el-empty v-if="!params.length" description="还没有参数" :image-size="50" />
  </div>
</template>

<script setup>
defineProps({ params: { type: Array, required: true } });
function newParam() {
  return { name: "", type: "string", required: false,
           default: null, example: "" };
}
</script>

<style scoped>
.params { padding: 10px; }
.head { display: flex; justify-content: space-between; align-items: center;
        font-weight: 600; font-size: 13px; margin-bottom: 8px; }
.param { display: grid; grid-template-columns: 1fr 92px 58px 1fr 1fr 20px;
         gap: 4px; margin-bottom: 6px; align-items: center; }
</style>
