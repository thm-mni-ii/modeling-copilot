<template>
  <div class="json-result-viewer">
    <div class="json-result-viewer__toolbar">
      <button type="button" class="json-result-viewer__toggle" @click="expanded = !expanded">
        <v-icon size="14">{{ expanded ? 'mdi-chevron-down' : 'mdi-chevron-right' }}</v-icon>
        {{ expanded ? 'Einklappen' : 'Ausklappen' }}
      </button>
      <v-spacer />
      <v-btn icon size="x-small" variant="text" :title="copied ? 'Kopiert!' : 'Als JSON kopieren'" @click="copy">
        <v-icon size="14">{{ copied ? 'mdi-check' : 'mdi-content-copy' }}</v-icon>
      </v-btn>
      <v-btn v-if="isLarge" icon size="x-small" variant="text" title="Groß anzeigen" @click="dialog = true">
        <v-icon size="14">mdi-arrow-expand</v-icon>
      </v-btn>
    </div>
    <pre v-if="expanded" class="json-result-viewer__pre">{{ formatted }}</pre>
    <v-dialog v-model="dialog" max-width="900">
      <v-card>
        <v-card-title class="d-flex align-center ga-2">
          <span class="text-body-1">JSON-Ergebnis</span>
          <v-spacer />
          <v-btn icon size="small" variant="text" :title="copied ? 'Kopiert!' : 'Als JSON kopieren'" @click="copy"
            ><v-icon size="16">{{ copied ? 'mdi-check' : 'mdi-content-copy' }}</v-icon></v-btn
          >
        </v-card-title>
        <v-card-text>
          <pre class="json-result-viewer__pre json-result-viewer__pre--dialog">{{ formatted }}</pre>
        </v-card-text>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { JsonObject } from '@/services/api/types/common'

const props = defineProps<{ data: JsonObject }>()
const formatted = computed(() => JSON.stringify(props.data, null, 2))
const isLarge = computed(() => formatted.value.length > 400)
const expanded = ref(false)
const dialog = ref(false)
const copied = ref(false)
let copiedTimer: ReturnType<typeof setTimeout> | null = null

const copy = async () => {
  try {
    await navigator.clipboard.writeText(formatted.value)
    copied.value = true
    if (copiedTimer) clearTimeout(copiedTimer)
    copiedTimer = setTimeout(() => {
      copied.value = false
    }, 1500)
  } catch {
    // clipboard API unavailable; silently ignore
  }
}
</script>

<style scoped>
.json-result-viewer__toolbar {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-bottom: 2px;
}
.json-result-viewer__toggle {
  display: flex;
  align-items: center;
  gap: 2px;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.7rem;
  color: rgba(var(--v-theme-on-surface), 0.6);
  padding: 0;
}
.json-result-viewer__pre {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 0.75rem;
  background: rgba(var(--v-theme-on-surface), 0.04);
  border-radius: 4px;
  padding: 6px 8px;
  max-height: 260px;
  overflow: auto;
}
.json-result-viewer__pre--dialog {
  max-height: 70vh;
}
</style>
