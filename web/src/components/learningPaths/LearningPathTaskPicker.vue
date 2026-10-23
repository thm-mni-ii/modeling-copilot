<template>
  <v-dialog :model-value="modelValue" max-width="720" @update:model-value="emit('update:modelValue', $event)">
    <v-card class="task-picker">
      <v-card-title class="d-flex align-center">Add tasks<v-spacer /><v-btn icon="mdi-close" variant="text" aria-label="Close task picker" @click="emit('update:modelValue', false)" /></v-card-title>
      <v-card-text>
        <p class="text-body-2 text-medium-emphasis mb-4">Select tasks to add in one go. Each uses its latest published release. You can change the release later.</p>
        <v-text-field v-model="query" label="Search tasks" prepend-inner-icon="mdi-magnify" variant="outlined" density="compact" clearable hide-details autofocus />
        <v-progress-linear v-if="loading" indeterminate class="mt-3" />
        <div class="picker-results mt-3">
          <v-list aria-label="Available tasks">
            <v-list-item
              v-for="task in filtered"
              :key="task.id"
              :disabled="!task.latestReleaseId"
              :title="task.name"
              :subtitle="!task.latestReleaseId ? 'Publish a release before adding this task' : usedCount(task.id) ? `Already used ${usedCount(task.id)} time(s) · can be added again` : task.visibility !== 'published' ? 'Private task · publish it before publishing this path' : 'Latest release'"
              @click="toggle(task.id)"
            >
              <template #prepend><v-checkbox-btn :model-value="selected.includes(task.id)" :disabled="!task.latestReleaseId" :aria-label="`Select ${task.name}`" @click.stop="toggle(task.id)" /></template>
              <template #append><v-icon v-if="usedCount(task.id)" size="18" color="primary">mdi-repeat</v-icon></template>
            </v-list-item>
          </v-list>
          <p v-if="!filtered.length && !loading" class="text-center text-medium-emphasis pa-8">No tasks match your search.</p>
        </div>
      </v-card-text>
      <v-card-actions class="px-6 pb-5"
        ><span class="text-body-2 text-medium-emphasis">{{ selected.length }} selected</span><v-spacer /><v-btn @click="emit('update:modelValue', false)">Cancel</v-btn><v-btn color="primary" variant="flat" :disabled="!selected.length || loading" @click="emit('add', [...selected])">Add {{ selected.length || '' }} {{ selected.length === 1 ? 'task' : 'tasks' }}</v-btn></v-card-actions
      >
    </v-card>
  </v-dialog>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Task } from '@/services/api/types/task'
import type { PathStep } from '@/services/learningPaths'
const props = defineProps<{ modelValue: boolean; tasks: Task[]; steps: PathStep[]; loading: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; add: [ids: string[]] }>()
const selected = ref<string[]>([]),
  query = ref('')
const filtered = computed(() => props.tasks.filter((task) => task.name.toLocaleLowerCase('en').includes((query.value ?? '').toLocaleLowerCase('en'))))
const usedCount = (id: string) => props.steps.filter((step) => step.taskVersion.taskId === id).length
const toggle = (id: string) => {
  if (!props.tasks.find((task) => task.id === id)?.latestReleaseId) return
  selected.value = selected.value.includes(id) ? selected.value.filter((value) => value !== id) : [...selected.value, id]
}
watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      selected.value = []
      query.value = ''
    }
  }
)
</script>
<style scoped>
.picker-results {
  max-height: 45vh;
  overflow-y: auto;
}
</style>
