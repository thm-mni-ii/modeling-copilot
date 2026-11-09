<template>
  <v-autocomplete :model-value="modelValue" v-model:search="search" :items="items" item-value="id" :item-title="userTitle" :label="label" multiple chips closable-chips :loading="busy" :error-messages="error" no-filter clearable @update:model-value="emit('update:modelValue', $event ?? [])" />
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { submissions, submissionError } from '@/services/submissions'
import type { DirectoryUser } from '@/services/api/types/submission'
const props = defineProps<{ modelValue: string[]; label: string; runId?: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()
const search = ref('')
const items = ref<DirectoryUser[]>([])
const busy = ref(false)
const error = ref('')
const userTitle = (user: DirectoryUser) => `${user.name} (${user.id})`
let timer: ReturnType<typeof setTimeout> | undefined
let generation = 0
watch(
  [search, () => props.runId],
  () => {
    clearTimeout(timer)
    const current = ++generation
    timer = setTimeout(async () => {
      busy.value = true
      try {
        const found = (await submissions.users(search.value ?? '', props.runId)).data.items
        if (current === generation) {
          items.value = [...items.value.filter((u) => props.modelValue.includes(u.id)), ...found.filter((u) => !props.modelValue.includes(u.id) || !items.value.some((i) => i.id === u.id))]
          error.value = ''
        }
      } catch (cause) {
        if (current === generation) error.value = submissionError(cause)
      } finally {
        if (current === generation) busy.value = false
      }
    }, 250)
  },
  { immediate: true }
)
onBeforeUnmount(() => {
  clearTimeout(timer)
  generation++
})
</script>
