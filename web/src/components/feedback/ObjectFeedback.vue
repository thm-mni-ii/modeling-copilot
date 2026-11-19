<template>
  <ul class="object-feedback">
    <li v-for="object in entry.objects ?? []" :key="object.cellId" class="object-feedback__item">
      <div class="d-flex align-center ga-2">
        <strong class="object-feedback__name">{{ object.label || 'Unbeschriftetes Objekt' }}</strong>
        <v-spacer />
        <v-chip v-if="object.verdict" :color="statusColors[object.verdict]" size="x-small" variant="tonal" label>{{ statusLabels[object.verdict] }}</v-chip>
        <v-btn icon="mdi-crosshairs-gps" size="x-small" variant="text" :aria-label="`${object.label || 'Objekt'} im Modell zeigen`" @click="emit('select', [object.cellId])" />
      </div>
      <p class="object-feedback__identity">{{ identityLabels[object.identity] }}</p>
      <template v-if="object.example?.xml || object.example?.definition">
        <ModelExcerptPreview v-if="object.example.xml" :xml="object.example.xml" :label="`Ausschnitt der Musterlösung um ${object.example.label || object.example.typeName}`" />
        <ConnectionPreviewItem v-else-if="object.example.kind === 'connection'" :connection="(object.example.definition as unknown as DiagramConnection)" :width="220" :height="60" />
        <DiagramPreviewItem v-else :element="({ ...object.example.definition, defaultLabel: object.example.label } as unknown as DiagramElement)" :width="220" :height="110" />
        <p class="object-feedback__hint">Musterlösung: „{{ object.example.label || 'ohne Beschriftung' }}“ · {{ object.example.typeName }}</p>
      </template>
      <ul v-if="object.checks.length" class="object-feedback__checks">
        <li v-for="check in object.checks" :key="check.area">
          <v-icon :color="statusColors[check.status]" size="14">{{ statusIcons[check.status] }}</v-icon>
          <span>{{ check.text }}</span>
          <span v-if="check.certainty === 'conditional'" class="object-feedback__hint"> (vorläufig)</span>
        </li>
      </ul>
      <p v-if="object.notEvaluated" class="object-feedback__hint">{{ object.notEvaluated }} {{ object.notEvaluated === 1 ? 'Eigenschaft konnte' : 'Eigenschaften konnten' }} nicht geprüft werden.</p>
    </li>
  </ul>
</template>

<script setup lang="ts">
import DiagramPreviewItem from '@/components/modeling/canvas/DiagramPreviewItem.vue'
import ConnectionPreviewItem from '@/components/modeling/canvas/ConnectionPreviewItem.vue'
import ModelExcerptPreview from './ModelExcerptPreview.vue'
import type { DiagramConnection, DiagramElement } from '@/model/DiagramLanguage'
import type { HelpFeedbackEntry } from '@/services/api/types/evaluation'

defineProps<{ entry: HelpFeedbackEntry }>()
const emit = defineEmits<{ select: [cellIds: string[]] }>()
const statusLabels: Record<string, string> = { matches: 'passt', differs: 'weicht ab', unclear: 'unklar', not_evaluated: 'nicht geprüft' }
const statusColors: Record<string, string> = { matches: 'success', differs: 'warning', unclear: 'info', not_evaluated: 'grey' }
const statusIcons: Record<string, string> = { matches: 'mdi-check-circle-outline', differs: 'mdi-alert-circle-outline', unclear: 'mdi-help-circle-outline' }
const identityLabels: Record<string, string> = {
  recognized: 'Eindeutig einem Element der Musterlösung zugeordnet.', provisional: 'Vorläufig einem Element der Musterlösung zugeordnet.',
  unassigned: 'Konnte keinem Element der Musterlösung zugeordnet werden.', not_evaluated: 'Wurde nicht ausgewertet.'
}
</script>

<style scoped>
.object-feedback, .object-feedback__checks { list-style: none; padding: 0; }
.object-feedback__item + .object-feedback__item { margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
.object-feedback__name { font-size: 12px; overflow-wrap: anywhere; }
.object-feedback__identity, .object-feedback__hint { font-size: 11px; color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); }
.object-feedback__checks li { display: flex; gap: 4px; align-items: baseline; font-size: 12px; line-height: 1.45; margin-top: 3px; }
</style>
