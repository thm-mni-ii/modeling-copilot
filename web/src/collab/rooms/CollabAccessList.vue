<template>
  <v-list density="compact" border rounded>
    <v-list-item v-for="row in rows" :key="row.id" :title="row.label">
      <template #append>
        <v-select :model-value="levelOf(row.rights)" :items="ACCESS_LEVELS" item-title="title" item-value="value" :placeholder="describeRights(row.rights)" persistent-placeholder density="compact" variant="plain" hide-details class="collab-access__level" @update:model-value="emit('change', row.id, $event)" />
        <v-btn icon="mdi-close" size="small" variant="text" title="Remove access" :loading="busy === row.id" @click="emit('remove', row.id)" />
      </template>
    </v-list-item>
    <v-list-item v-if="rows.length === 0" :subtitle="emptyText" />
  </v-list>
  <div class="d-flex ga-2 mt-2">
    <v-select v-model="candidate" :items="options" :label="addLabel" density="compact" variant="outlined" hide-details />
    <v-select v-model="level" :items="ACCESS_LEVELS" item-title="title" item-value="value" density="compact" variant="outlined" hide-details class="collab-access__level" />
    <v-btn variant="tonal" prepend-icon="mdi-plus" :disabled="!candidate" :loading="busy === 'add'" @click="add">Add</v-btn>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ACCESS_LEVELS, describeRights, levelOf, type AccessLevel } from './access'

/** Access shown from either side: groups of a room, or rooms of a group; the same grants behind both. */
defineProps<{
  rows: { id: string; label: string; rights: string[] }[]
  options: { value: string; title: string }[]
  addLabel: string
  emptyText: string
  busy: string | null
}>()

const emit = defineEmits<{
  change: [id: string, level: AccessLevel]
  remove: [id: string]
  add: [id: string, level: AccessLevel]
}>()

const candidate = ref<string | null>(null)
const level = ref<AccessLevel>('edit')

const add = () => {
  if (!candidate.value) return
  emit('add', candidate.value, level.value)
  candidate.value = null
}
</script>

<style scoped>
.collab-access__level {
  width: 140px;
  flex: 0 0 140px;
}
</style>
