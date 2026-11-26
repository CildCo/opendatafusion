<template>
  <param-bar :params="params" :value="value" resettable
             @update:value="$emit('update:value', $event)"
             @refresh="$emit('refresh')" @reset="$emit('reset')" />
</template>

<script setup>
import ParamBar from "../shared/ParamBar.vue";

defineProps({
  params: { type: Array, default: () => [] },
  value: { type: Object, default: () => ({}) },
});
defineEmits(["update:value", "refresh", "reset"]);
</script>
