<template>
  <div class="syntax-editor-form">
    <MultiplicityForm v-if="rule.ruleType === 'multiplicity'" :config="rule.config" :element-options="elementOptions" :connection-options="connectionOptions" @update="updateAll">
      <slot />
    </MultiplicityForm>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import MultiplicityForm from '@/components/modeling/form/MultiplicityForm.vue'
import type { DiagramSyntax } from '@/model/DiagramLanguage'
import { useDiagramLanguages } from '@/composables/useDiagramLanguages'

interface Props {
  selectedRule: DiagramSyntax
}

const props = defineProps<Props>()
const emit = defineEmits<{
  update: []
}>()

const store = useDiagramLanguages()
const rule = computed(() => props.selectedRule)

const elementOptions = computed(() => {
  const elements = store.definition?.elements || []
  return elements.map((el) => el.type)
})

const connectionOptions = computed(() => {
  const connections = store.definition?.connections || []
  return [...new Set(connections.map((conn) => conn.type))]
})

const updateAll = () => {
  emit('update')
}
</script>
