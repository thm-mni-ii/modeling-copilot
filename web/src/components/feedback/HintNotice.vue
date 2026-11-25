<template>
  <v-alert v-if="count" type="info" variant="tonal" class="my-3" aria-live="polite">
    <strong>{{ count === 1 ? 'Bei der Auswertung blieb eine Zuordnung offen.' : `Bei der Auswertung blieben ${count} Zuordnungen offen.` }}</strong>
    <p class="text-body-2 mt-1 mb-2">Hilfst du uns kurz, die gemeinten Begriffe zu klären?</p>
    <v-btn color="info" variant="flat" size="small" @click="emit('open')">Hinweise ansehen</v-btn>
  </v-alert>
</template>

<script setup lang="ts">
defineProps<{ count: number }>()
const emit = defineEmits<{ open: [] }>()
</script>
