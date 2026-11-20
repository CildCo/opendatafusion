<template>
  <div class="empty-state">
    <svg class="art" width="132" height="96" viewBox="0 0 132 96"
         fill="none" aria-hidden="true">
      <rect x="14" y="18" width="104" height="62" rx="6"
            fill="#f8fafc" stroke="#dbe3ee" />
      <rect x="24" y="30" width="46" height="6" rx="3" fill="#cbd5e1" />
      <rect x="24" y="42" width="72" height="4" rx="2" fill="#e2e8f0" />
      <rect x="24" y="50" width="62" height="4" rx="2" fill="#e2e8f0" />
      <rect x="24" y="58" width="54" height="4" rx="2" fill="#e2e8f0" />
      <circle cx="100" cy="34" r="12" fill="#eff4ff"
              stroke="#bfd3ff" />
      <path d="M100 28v12M94 34h12" stroke="#1d4ed8"
            stroke-width="1.6" stroke-linecap="round" />
      <path d="M26 78c10-10 18-2 26-9s14 2 24-6" stroke="#93c5fd"
            stroke-width="2" stroke-linecap="round" fill="none" />
    </svg>
    <div class="title">{{ title }}</div>
    <p v-if="description" class="desc">{{ description }}</p>
    <slot>
      <el-button v-if="actionText" type="primary" @click="$emit('action')">
        {{ actionText }}
      </el-button>
    </slot>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  description: { type: String, default: "" },
  actionText: { type: String, default: "" },
});
defineEmits(["action"]);
</script>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 36px 20px 40px;
  gap: 6px;
}
.art { margin-bottom: 6px; }
.title { color: #334155; font-size: 14px; font-weight: 600; }
.desc {
  color: #94a3b8;
  font-size: 12px;
  max-width: 420px;
  margin: 0 0 8px;
  line-height: 1.6;
}
</style>
